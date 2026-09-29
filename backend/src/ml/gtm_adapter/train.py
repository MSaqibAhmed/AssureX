"""From-scratch Keras card classifier with the official TM preprocessing interface.
This compatible adapter is not represented as a model trained by the Google web UI.
"""
import json, os, faulthandler, hashlib
from pathlib import Path
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
import numpy as np
from PIL import Image
import tensorflow as tf
from sklearn.metrics import accuracy_score,confusion_matrix,f1_score
from src.ml.features import CLASSES
from src.ml.gtm_adapter.predict import preprocess

def dataset(root,split):
    paths=[]; labels=[]
    for i,label in enumerate(CLASSES):
        for path in sorted((root/'cards'/split/label).glob('*.png')):
            paths.append(path); labels.append(i)
    return np.stack([preprocess(Image.open(p)) for p in paths]),np.array(labels)

def train(root=Path('data'),output=Path('artifacts/gtm')):
    faulthandler.dump_traceback_later(180,repeat=True)
    tf.keras.utils.set_random_seed(42)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    tf.config.threading.set_intra_op_parallelism_threads(4)
    x,y=dataset(root,'train'); vx,vy=dataset(root,'validation')
    model=tf.keras.Sequential([
        tf.keras.layers.Input((224,224,3)),
        tf.keras.layers.Conv2D(16,3,activation='relu',strides=2),
        tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Conv2D(32,3,activation='relu'),tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Flatten(),tf.keras.layers.Dense(96,activation='relu'),
        tf.keras.layers.Dropout(.2),tf.keras.layers.Dense(3,activation='softmax')])
    model.compile(optimizer=tf.keras.optimizers.Adam(.001),loss='sparse_categorical_crossentropy',metrics=['accuracy'])
    history=model.fit(x,y,validation_data=(vx,vy),epochs=30,batch_size=32,
        callbacks=[tf.keras.callbacks.EarlyStopping(patience=5,restore_best_weights=True)],verbose=2)
    tx,ty=dataset(root,'test'); pred=np.argmax(model.predict(tx,verbose=0),axis=1)
    metrics={'accuracy':accuracy_score(ty,pred),'macro_f1':f1_score(ty,pred,average='macro'),
        'confusion_matrix':confusion_matrix(ty,pred,labels=[0,1,2]).tolist(),'class_order':CLASSES,'test_count':len(ty),
        'training_method':'From-scratch compatible Keras card classifier','history':history.history,
        'preprocessing':'RGB center fit 224x224, float32 /127.5 -1'}
    output.mkdir(parents=True,exist_ok=True)
    (output/'labels.json').write_text(json.dumps(CLASSES)); (output/'metrics.json').write_text(json.dumps(metrics,indent=2))
    # Optimizer state is not needed for server inference. Export an uncompiled clone.
    exported=tf.keras.models.clone_model(model)
    exported.set_weights(model.get_weights())
    print('Exporting inference artifact',flush=True)
    exported.save(output/'model.keras')
    (output/'metadata.json').write_text(json.dumps({'dataset_hashes':json.loads((root/'manifest.json').read_text())['hashes'],
        'artifact_sha256':hashlib.sha256((output/'model.keras').read_bytes()).hexdigest(),
        'class_order':CLASSES,'training_method':metrics['training_method']},indent=2))
    faulthandler.cancel_dump_traceback_later()
    print(json.dumps({k:v for k,v in metrics.items() if k!='history'}))

if __name__=='__main__': train()

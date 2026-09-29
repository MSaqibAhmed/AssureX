import json
import numpy as np
from PIL import Image, ImageOps
from src.schemas.evaluation import Probabilities

def preprocess(image):
    # Official Google export: RGB, centered 224x224 fit, float32 /127.5 -1.
    image=ImageOps.fit(image.convert('RGB'),(224,224),Image.Resampling.LANCZOS)
    return np.asarray(image,dtype=np.float32)/127.5-1

class GTMModel:
    def __init__(self,path,labels):
        import tensorflow as tf
        self.model=tf.keras.models.load_model(path,compile=False)
        self.labels=json.loads(open(labels,encoding='utf-8').read())
        if not isinstance(self.labels,list) or len(self.labels)!=3 or set(self.labels)!= {'valid','invalid','manual_review'}:
            raise ValueError('Invalid class mapping')
    def predict(self,image):
        scores=self.model(np.expand_dims(preprocess(image),0),training=False).numpy()[0]
        if np.shape(scores)!=(3,): raise ValueError('Invalid model output shape')
        return Probabilities.model_validate(dict(zip(self.labels,map(float,scores))))

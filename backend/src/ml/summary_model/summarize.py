import hashlib,json,re,time,os
from functools import lru_cache

@lru_cache(maxsize=1)
def load(model_name):
    os.environ.setdefault('USE_TF','0')
    import torch
    # Small CPU model: excessive intra-op threads cause severe oversubscription
    # when classifiers and OCR share the same host. This runs in its own process.
    torch.set_num_threads(2)
    from transformers import AutoTokenizer,AutoModelForSeq2SeqLM
    return (AutoTokenizer.from_pretrained(model_name,local_files_only=True,trust_remote_code=False),
            AutoModelForSeq2SeqLM.from_pretrained(model_name,local_files_only=True,trust_remote_code=False,use_safetensors=True))

def summarize(facts,model_name='google/flan-t5-small'):
    start=time.perf_counter()
    allowed={k:facts.get(k) for k in ['product_category','fault_category','purchase_date','fault_date','serial_status','repair_count']}
    context=json.dumps(allowed,sort_keys=True)
    fallback='; '.join(f'{k}: {v if v is not None else "unknown"}' for k,v in allowed.items())
    source='fallback'; flags=[]; text=fallback
    try:
        tokenizer,model=load(model_name)
        encoded=tokenizer('Summarize only these facts. Do not recommend a decision: '+context,return_tensors='pt')
        result=model.generate(**encoded,do_sample=False,max_new_tokens=80)
        candidate=tokenizer.decode(result[0],skip_special_tokens=True)
        # Conservative grounding: no novel number, capitalized name, or decision language.
        tokens=re.findall(r'\b[\w.-]+\b',candidate.lower())
        permitted=set(re.findall(r'\b[\w.-]+\b',context.lower()))|set('the a an is has was with and of for in on claim product reported unknown'.split())
        if candidate and all(t in permitted for t in tokens): text=candidate; source='local_model'
        else: flags.append('grounding_rejected')
    except Exception:
        flags.append('generation_unavailable')
    return {'model_version':model_name,'prompt_version':'1.0','input_hash':hashlib.sha256(context.encode()).hexdigest(),
        'text':text,'source':source,'quality_flags':flags,'elapsed_ms':round((time.perf_counter()-start)*1000,2)}

def summary_child(connection,facts,model_name):
    try:
        connection.send({'output':summarize(facts,model_name)})
    finally:
        connection.close()

def bounded_summary(facts,model_name,timeout=30):
    from src.ml.inference_process import bounded_call,ModelUnavailable
    try:
        return bounded_call(summary_child,(facts,model_name),timeout)
    except ModelUnavailable:
        allowed={k:facts.get(k) for k in ['product_category','fault_category','purchase_date','fault_date','serial_status','repair_count']}
        context=json.dumps(allowed,sort_keys=True)
        return {'model_version':model_name,'prompt_version':'1.0','input_hash':hashlib.sha256(context.encode()).hexdigest(),
            'text':'; '.join(f'{k}: {v if v is not None else "unknown"}' for k,v in allowed.items()),
            'source':'fallback','quality_flags':['generation_timeout_or_failure'],'elapsed_ms':timeout*1000}

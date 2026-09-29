import asyncio,hashlib,hmac,time
from fastapi import APIRouter,Depends,HTTPException,Request,UploadFile,File,Form,Query
from fastapi.responses import FileResponse,Response
from io import BytesIO
from pdf2image import convert_from_bytes
from src.security.auth import current_user,role
from src.repositories.mongo import uid,now,claim_for,change_claim,audit
from src.api.common import envelope
from src.schemas.requests import Correction
from src.engines.ocr import validate_document,normalize
from src.engines.fault_media import validate_video

router=APIRouter(tags=['documents'])

@router.get('/documents/{id}/preview')
async def preview(id:str,request:Request,page:int=Query(1,ge=1,le=10),user=Depends(current_user)):
    db=request.app.state.db; document=await db.documents.find_one({'_id':id})
    if not document: raise HTTPException(404,'Document not found')
    await claim_for(db,document['claim_id'],user)
    root=request.app.state.settings.evidence_root.resolve(); path=(root/document['object_key']).resolve()
    if path.parent!=root or not path.is_file(): raise HTTPException(404,'Document unavailable')
    headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}
    if document['mime']!='application/pdf': return FileResponse(path,media_type=document['mime'],headers=headers)
    def render():
        pages=convert_from_bytes(path.read_bytes(),first_page=page,last_page=page,dpi=100,size=1100,timeout=8)
        if not pages: raise ValueError('Page unavailable')
        output=BytesIO(); pages[0].save(output,format='PNG'); return output.getvalue()
    try: image=await asyncio.to_thread(render)
    except Exception: raise HTTPException(422,'Preview unavailable. Download the original document instead.')
    return Response(image,media_type='image/png',headers=headers)

@router.get('/claims/{id}/documents')
async def list_documents(id:str,request:Request,user=Depends(current_user)):
    db=request.app.state.db
    await claim_for(db,id,user)
    return envelope(request,await db.documents.find({'claim_id':id}).sort('_id',1).to_list())

@router.post('/claims/{id}/documents',status_code=202)
async def upload(id:str,request:Request,file:UploadFile=File(...),document_type:str=Form(...),
                 version:int=Form(...),status:str=Form(...),user=Depends(current_user)):
    role(user,'customer','service'); db=request.app.state.db; claim=await claim_for(db,id,user)
    if claim['status'] not in ('Draft','Additional Information Required'): raise HTTPException(409,'Evidence is frozen during evaluation and review')
    if document_type not in ('receipt','serial_photo','warranty','diagnostic','supporting','fault_image','fault_video'): raise HTTPException(422,'Unknown document type')
    settings=request.app.state.settings
    data=await file.read(settings.max_upload_bytes+1)
    try:
        if document_type=='fault_video':
            await asyncio.to_thread(validate_video,data,file.filename or '',file.content_type,settings.max_upload_bytes)
        else:
            if document_type=='fault_image' and file.content_type not in ('image/png','image/jpeg'):
                raise ValueError('Fault image must be JPEG or PNG')
            await asyncio.to_thread(validate_document,data,file.filename or '',file.content_type,settings.max_upload_bytes,settings.max_pdf_pages)
    except OverflowError: raise HTTPException(413,'Upload exceeds size limit')
    except Exception: raise HTTPException(422,'Invalid, encrypted, or unsupported document')
    did,jid=uid(),uid(); root=settings.evidence_root.resolve(); root.mkdir(parents=True,exist_ok=True)
    path=root/did; await asyncio.to_thread(path.write_bytes,data)
    async def transaction(session):
        await change_claim(db,claim,version,status,{'updated_at':now()},session)
        await db.documents.insert_one({'_id':did,'claim_id':id,'product_id':claim['product_id'],'object_key':did,
            'sha256':hashlib.sha256(data).hexdigest(),'mime':file.content_type,'name':file.filename,
            'type':document_type,'size':len(data),'job_id':jid},session=session)
        await db.jobs.insert_one({'_id':jid,'claim_id':id,'document_id':did,'status':'queued','stage':'queued'},session=session)
        await db.outbox.insert_one({'_id':jid,'kind':'ocr','target_id':did,'status':'pending','created_at':now()},session=session)
    try:
        async with db.client.start_session() as session: await session.with_transaction(transaction)
    except HTTPException:
        # A rejected optimistic update aborts the transaction definitively. Do not
        # delete on an ambiguous database/network error that may have committed.
        await asyncio.to_thread(path.unlink,missing_ok=True)
        raise
    return envelope(request,{'document_id':did,'job_id':jid},version+1)

@router.get('/documents/{id}/ocr')
async def ocr(id:str,request:Request,download:bool=False,expires:int=0,signature:str='',user=Depends(current_user)):
    db=request.app.state.db; document=await db.documents.find_one({'_id':id})
    if not document: raise HTTPException(404,'Document not found')
    await claim_for(db,document['claim_id'],user)
    settings=request.app.state.settings
    def sign(exp): return hmac.new(settings.session_secret.encode(),f'{id}:{user["_id"]}:{exp}'.encode(),hashlib.sha256).hexdigest()
    if download:
        if not time.time()<=expires<=time.time()+300 or not hmac.compare_digest(signature,sign(expires)):
            raise HTTPException(403,'Download link expired or invalid')
        root=settings.evidence_root.resolve(); path=(root/document['object_key']).resolve()
        if path.parent!=root or not path.is_file(): raise HTTPException(404,'Document unavailable')
        return FileResponse(path,media_type=document['mime'],filename='evidence-'+id,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
    expiry=int(time.time())+120
    return envelope(request,{'document':document,'runs':await db.ocr_runs.find({'document_id':id}).to_list(),
        'fields':await db.ocr_fields.find({'document_id':id}).to_list(),
        'download_url':f'/api/v1/documents/{id}/ocr?download=true&expires={expiry}&signature={sign(expiry)}'})

@router.patch('/ocr-fields/{id}')
async def correct(id:str,body:Correction,request:Request,user=Depends(current_user)):
    role(user,'customer','service'); db=request.app.state.db; field=await db.ocr_fields.find_one({'_id':id})
    if not field: raise HTTPException(404,'Field not found')
    document=await db.documents.find_one({'_id':field['document_id']}); claim=await claim_for(db,document['claim_id'],user)
    if claim['status'] not in ('Draft','Additional Information Required'): raise HTTPException(409,'Submitted evidence is immutable')
    normalized=normalize(field['field'],body.normalized_value)
    if normalized is None: raise HTTPException(422,'Ambiguous or invalid value')
    async def transaction(session):
        await change_claim(db,claim,claim['version'],claim['status'],{'updated_at':now()},session)
        await db.ocr_fields.update_one({'_id':id},{'$set':{'normalized_value':normalized,'corrected':True,'corrected_by':user['_id']}},session=session)
        await audit(db,user['_id'],'ocr_corrected',id,session=session)
    async with db.client.start_session() as session: await session.with_transaction(transaction)
    return envelope(request,await db.ocr_fields.find_one({'_id':id}),claim['version']+1)

import asyncio
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from fastapi.responses import Response
from src.services.pdf_reports import claim_report
from src.schemas.requests import Review
from src.security.auth import current_user,role
from src.repositories.mongo import uid,now,claim_for,change_claim,audit
from src.api.common import envelope

router=APIRouter(tags=['reviews'])

@router.post('/claims/{id}/reviews',status_code=201)
async def review(id:str,body:Review,request:Request,user=Depends(current_user)):
    role(user,'reviewer'); db=request.app.state.db; claim=await claim_for(db,id,user)
    async def transaction(session):
        current=await db.claims.find_one({'_id':id},session=session)
        if current['status']!='Manual Review' or current['latest_evaluation_id']!=body.evaluation_id:
            raise HTTPException(409,'Review requires the current completed evaluation')
        new_status={'approve':'Approved','reject':'Rejected','request_info':'Additional Information Required'}[body.action]
        rid=uid()
        await change_claim(db,current,body.version,body.status,{'status':new_status,'latest_review_id':rid,
            'requested_information':body.reason if body.action=='request_info' else None},session)
        record={'_id':rid,'claim_id':id,'reviewer_id':user['_id'],'action':body.action,'reason':body.reason,
            'evaluation_id':body.evaluation_id,'timestamp':now(),'version':1,'status':'recorded','before':current['status'],'after':new_status}
        await db.reviews.insert_one(record,session=session)
        await audit(db,user['_id'],'review_'+body.action,id,current['status'],new_status,session)
        await db.notifications.insert_one({'_id':uid(),'recipient':current['claimant_id'],'event_type':'review_'+body.action,
            'target_revision':rid,'reminder_window':0,'read':False,'claim_id':id},session=session)
        return record
    async with db.client.start_session() as session: record=await session.with_transaction(transaction)
    return envelope(request,record,body.version+1)

@router.get('/claims/{id}/report')
async def report(id:str,request:Request,evaluation_id:str=Query(...),review_id:str|None=None,user=Depends(current_user)):
    db=request.app.state.db; claim=await claim_for(db,id,user)
    evaluation=await db.evaluation_runs.find_one({'_id':evaluation_id})
    revision=await db.claim_revisions.find_one({'_id':evaluation['claim_revision_id'],'claim_id':id}) if evaluation else None
    if not revision: raise HTTPException(404,'Evaluation not found')
    review=await db.reviews.find_one({'_id':review_id,'claim_id':id,'evaluation_id':evaluation_id}) if review_id else None
    if review_id and not review: raise HTTPException(404,'Review not found')
    output=await asyncio.to_thread(claim_report,claim,revision,evaluation,review)
    return Response(output,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="claim-{id}-{evaluation_id}.pdf"'})

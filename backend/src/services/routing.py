"""Server-owned, category-based routing; never accept assignments from customers."""
from fastapi import HTTPException

async def assignments(db,category):
    config=await db.settings.find_one({'_id':'claim_routing'})
    rules=config['value'] if config else {}
    selected=rules.get(category,rules.get('default',{}))
    center_id=selected.get('center_id')
    reviewer_id=selected.get('reviewer_id')
    if center_id and not await db.service_centers.find_one({'_id':center_id,'active':True}):
        raise HTTPException(503,'Configured service center is unavailable')
    if reviewer_id:
        reviewer=await db.users.find_one({'_id':reviewer_id,'role':'reviewer','active':True})
        if not reviewer: raise HTTPException(503,'Configured reviewer is unavailable')
    else:
        reviewer=await db.users.find_one({'role':'reviewer','active':True},sort=[('_id',1)])
    return {'center_id':center_id,'assigned_reviewer_id':reviewer['_id'] if reviewer else None}

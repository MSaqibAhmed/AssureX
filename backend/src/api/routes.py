"""Requested API surface and route inventory for contract testing."""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix='/api/v1')
ROUTES = {
 '/auth/register':['POST'], '/auth/login':['POST'], '/auth/logout':['POST'], '/me':['GET'],
 '/products':['GET','POST'], '/products/{id}':['GET','PATCH'],
 '/products/{id}/warranty':['GET','PATCH'], '/products/{id}/repairs':['POST'],
 '/products/{id}/replacements':['POST'], '/claims':['POST'], '/claims/{id}':['GET','PATCH'],
 '/claims/{id}/documents':['GET','POST'], '/documents/{id}/ocr':['GET'], '/ocr-fields/{id}':['PATCH'],
 '/claims/{id}/submit':['POST'], '/jobs/{id}':['GET'], '/claims/{id}/evaluations':['GET'],
 '/claims/{id}/assistance':['GET'], '/claims/{id}/summary':['GET'],
 '/claims/{id}/comments':['GET','POST'], '/claims/{id}/reviews':['POST'],
 '/claims/{id}/report':['GET'], '/dashboard':['GET'], '/reports':['GET'],
 '/notifications':['GET'], '/notifications/{id}':['PATCH'],
 '/admin/policies':['POST'], '/admin/model-activations':['POST'],
}

ROUTES.update({'/policies':['GET'],'/policies/{id}':['GET'],'/documents':['GET'],
 '/products/{id}/service-history':['GET'],'/service-history':['GET'],'/claims/{id}/workflow':['GET'],
 '/admin/models':['GET'],'/admin/users':['GET','POST'],'/admin/users/{id}':['PATCH'],
 '/admin/service-centers':['GET'],'/admin/audit':['GET'],'/claims/{id}/assignment':['PATCH']})
ROUTES['/me']=['GET','PATCH']
ROUTES['/documents/{id}/preview']=['GET']
from src.api import auth,products,claims,documents,reviews,admin,dashboard,workspace
for module in (auth,products,claims,documents,reviews,admin,dashboard,workspace):
    router.include_router(module.router)

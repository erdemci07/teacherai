from typing import Annotated
from fastapi import Depends,Header
from fastapi.security.utils import get_authorization_scheme_param
from apps.api.app.core.dependencies import get_container
from apps.api.app.core.container import Container
from .schemas import AuthenticatedUser
class AuthenticationRequired(Exception):pass

def _user(authorization:str|None,container:Container,required:bool):
    scheme,token=get_authorization_scheme_param(authorization)
    if scheme.lower()!="bearer" or not token:
        if required:raise AuthenticationRequired
        return None
    try:return container.token_verifier.verify(token)
    except Exception:
        if required:raise AuthenticationRequired
        return None

def require_user(authorization:Annotated[str|None,Header()]=None,container:Container=Depends(get_container))->AuthenticatedUser:return _user(authorization,container,True)
def optional_user(authorization:Annotated[str|None,Header()]=None,container:Container=Depends(get_container))->AuthenticatedUser|None:return _user(authorization,container,False)

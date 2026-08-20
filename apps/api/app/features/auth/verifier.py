from typing import Protocol,Mapping,Any
from .schemas import AuthenticatedUser
class TokenVerifier(Protocol):
    def verify(self,token:str)->AuthenticatedUser:...
class FirebaseTokenVerifier:
    def __init__(self,project_id:str|None=None):self.project_id=project_id
    def verify(self,token:str)->AuthenticatedUser:
        from firebase_admin import auth
        decoded:Mapping[str,Any]=auth.verify_id_token(token,check_revoked=True)
        return AuthenticatedUser(uid=decoded["uid"],email=decoded.get("email"),name=decoded.get("name"))

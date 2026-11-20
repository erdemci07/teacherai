from typing import Protocol,Mapping,Any
from .schemas import AuthenticatedUser
class TokenVerifier(Protocol):
    def verify(self,token:str)->AuthenticatedUser:...
class FirebaseTokenVerifier:
    def __init__(self,app=None):self.app=app
    def verify(self,token:str)->AuthenticatedUser:
        from firebase_admin import auth
        try:
            decoded: Mapping[str, Any] = auth.verify_id_token(token, app=self.app, check_revoked=True)
        except auth.CertificateFetchError:
            raise RuntimeError("Identity service unavailable") from None
        except (auth.InvalidIdTokenError, auth.UserDisabledError, auth.UserNotFoundError):
            raise ValueError("Invalid identity") from None
        if decoded.get("firebase", {}).get("sign_in_provider") == "anonymous":
            from fastapi import HTTPException
            raise HTTPException(403, "Registered account required.")
        return AuthenticatedUser(uid=decoded["uid"],email=decoded.get("email"),name=decoded.get("name"),auth_time=decoded.get("auth_time"))

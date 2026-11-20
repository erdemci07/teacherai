from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    uid: str
    email: str | None = None
    name: str | None = None
    # Son kimlik doğrulama zamanı (ID token auth_time, Unix saniye). Hesap silme için gerekir.
    auth_time: int | None = None

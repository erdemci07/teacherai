from typing import Annotated
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security.utils import get_authorization_scheme_param
from apps.api.app.core.dependencies import get_container
from apps.api.app.core.container import Container
from .schemas import AuthenticatedUser


class AuthenticationRequired(Exception):
    pass


def _user(authorization: str | None, container: Container, required: bool):
    scheme, token = get_authorization_scheme_param(authorization)
    if scheme.lower() != "bearer" or not token:
        if required:
            raise AuthenticationRequired
        return None
    try:
        return container.token_verifier.verify(token)
    except HTTPException:
        raise
    except (ValueError, AuthenticationRequired):
        raise AuthenticationRequired from None
    except Exception:
        raise HTTPException(503, "Authentication service unavailable.") from None


def require_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    container: Container = Depends(get_container),
) -> AuthenticatedUser:
    if hasattr(request.state, "authenticated_user"):
        return request.state.authenticated_user
    user = _user(authorization, container, True)
    mode = container.settings.app_check_mode
    if mode != "off":
        from firebase_admin import app_check
        import logging

        token = request.headers.get("X-Firebase-AppCheck")
        try:
            if not token:
                raise ValueError("missing")
            app_check.verify_token(
                token, app=getattr(container.token_verifier, "app", None)
            )
        except ValueError:
            logging.getLogger(__name__).warning("app_check_invalid")
            if mode == "enforce":
                raise HTTPException(403, "App attestation required.") from None
        except Exception:
            logging.getLogger(__name__).warning("app_check_unavailable")
            if mode == "enforce":
                raise HTTPException(503, "App attestation unavailable.") from None
    request.state.authenticated_user = user
    return user


def optional_user(
    authorization: Annotated[str | None, Header()] = None,
    container: Container = Depends(get_container),
) -> AuthenticatedUser | None:
    return _user(authorization, container, False)

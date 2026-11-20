from dataclasses import replace
from fastapi.testclient import TestClient
from apps.api.app.features.auth.schemas import AuthenticatedUser


class TestTokenVerifier:
    def verify(self, token):
        if token not in {"student-a", "student-b"}:
            raise ValueError("invalid")
        return AuthenticatedUser(uid=token)


def authenticated_client(app, *, lesson=None, **kwargs):
    app.state.container = replace(app.state.container, token_verifier=TestTokenVerifier())
    if lesson:
        app.state.container.student_service.save_lesson(AuthenticatedUser(uid="student-a"), lesson)
    return TestClient(app, headers={"Authorization": "Bearer student-a"}, **kwargs)

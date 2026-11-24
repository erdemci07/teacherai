"""TA-005B §5: profildeki sınıf → API → ders. Fikstür kayıt ve sahte ders sağlayıcısı; ağ çağrısı yoktur."""

from dataclasses import replace

import pytest
from uuid import uuid4

from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.students.schemas import StudentProfile
from apps.api.app.main import create_app
from apps.api.tests.client import authenticated_client
from apps.api.tests.test_curriculum import CLEAN, Provider, authorize, linear_analysis

PROFILE = "/api/v1/students/me/profile"


@pytest.fixture
def app(monkeypatch):
    authorize(monkeypatch)
    app = create_app()
    service = LessonService(Provider(CLEAN), MathAIService(), BoardPlanner())
    app.state.container = replace(app.state.container, lesson_service=service)
    return app


def generate(app, client, uid="student-a", **body):
    analysis = linear_analysis().model_copy(update={"request_id": f"an_{uuid4().hex}"})
    app.state.container.student_service.save_analysis(AuthenticatedUser(uid=uid), analysis)
    response = client.post("/api/v1/lessons/generate", json={"analysis_id": analysis.request_id, **body})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_profile_grade_flows_into_lesson_and_old_lesson_keeps_its_snapshot(app):
    with authenticated_client(app) as client:
        assert client.get(PROFILE).json()["data"] is None
        saved = client.put(PROFILE, json={"display_name": "Ada", "exam_goal": "LGS", "grade": 8})
        assert saved.status_code == 200 and saved.json()["data"]["grade"] == 8
        assert client.get(PROFILE).json()["data"]["grade"] == 8

        first = generate(app, client)
        assert first["education_context"]["grade"] == {"value": 8, "origin": "profile"}
        assert first["method_check"]["state"] == "passed" and first["curriculum_check"]["state"] == "passed"
        lesson_id = first["lesson"]["lesson_plan_id"]
        record = app.state.container.student_service.repository.get_lesson(lesson_id)
        assert (record.grade, record.grade_origin) == (8, "profile")
        before = client.get(f"/api/v1/lessons/{lesson_id}/v2").json()["data"]["lesson"]["verification"]

        changed = client.put(PROFILE, json={"display_name": "Ada", "exam_goal": "LGS", "grade": 9})
        assert changed.json()["data"]["created_at"] == saved.json()["data"]["created_at"]
        after = client.get(f"/api/v1/lessons/{lesson_id}/v2").json()["data"]["lesson"]["verification"]
        assert after == before and (after["method"], after["curriculum"]) == ("passed", "passed")
        history = {item["lesson_id"]: item for item in client.get("/api/v1/students/me/history").json()["data"]}
        assert (history[lesson_id]["grade"], history[lesson_id]["grade_origin"]) == (8, "profile")

        second = generate(app, client)  # yeni ders yeni sınıfı kullanır; 9. sınıf politikası yok
        assert second["education_context"]["grade"] == {"value": 9, "origin": "profile"}
        assert second["method_check"]["state"] == "not_checked"


def test_declared_grade_wins_and_is_recorded_as_declared(app):
    with authenticated_client(app) as client:
        client.put(PROFILE, json={"display_name": "Ada", "grade": 9})
        result = generate(app, client, grade=8)
        assert result["education_context"]["grade"] == {"value": 8, "origin": "declared"}
        record = app.state.container.student_service.repository.get_lesson(result["lesson"]["lesson_plan_id"])
        assert (record.grade, record.grade_origin) == (8, "declared")


def test_legacy_profile_without_grade_is_not_blocked(app):
    repository = app.state.container.student_service.repository
    legacy = StudentProfile.model_validate({"student_id": "student-a", "display_name": "Eski", "exam_goal": None})
    repository.save_profile(legacy)
    with authenticated_client(app) as client:
        assert client.get(PROFILE).json()["data"]["grade"] is None
        result = generate(app, client)
        assert result["education_context"]["grade"] is None
        assert result["method_check"]["reason"] == "grade_unknown" and result["curriculum_check"]["state"] == "not_checked"
        record = repository.get_lesson(result["lesson"]["lesson_plan_id"])
        assert (record.grade, record.grade_origin) == (None, None)


def test_profile_writes_only_reach_the_authenticated_owner(app):
    repository = app.state.container.student_service.repository
    with authenticated_client(app) as client:
        client.put(PROFILE, json={"display_name": "Ada", "grade": 8})
        other = client.put(PROFILE, json={"display_name": "Başkası", "grade": 12, "student_id": "student-a"},
                           headers={"Authorization": "Bearer student-b"})
        assert other.status_code == 200 and other.json()["data"]["student_id"] == "student-b"
        anonymous = client.put(PROFILE, json={"display_name": "X", "grade": 5}, headers={"Authorization": ""})
        assert anonymous.status_code == 401
        assert client.put(PROFILE, json={"display_name": "Ada", "grade": 4}).status_code == 422
    assert repository.get_profile("student-a").grade == 8 and repository.get_profile("student-a").display_name == "Ada"
    assert repository.get_profile("student-b").grade == 12


def test_web_profile_form_uses_profile_input_contract():
    from pathlib import Path

    api = Path("apps/web/app/lib/student-api.ts").read_text(encoding="utf-8")
    form = Path("apps/web/app/auth/AuthForm.tsx").read_text(encoding="utf-8")
    panel = Path("apps/web/app/dashboard/ProfileGrade.tsx").read_text(encoding="utf-8")
    assert "GRADE_OPTIONS=[5,6,7,8,9,10,11,12]" in api and "({display_name,exam_goal,grade})" in api
    assert "saveProfile(name,goal||null,parseGrade(grade))" in form and '<option value="">Belirtmek istemiyorum</option>' in form
    assert "getProfile()" in panel and "parseGrade(grade)" in panel
    from apps.api.app.features.students.schemas import ProfileInput

    bounds = ProfileInput.model_json_schema()["properties"]["grade"]["anyOf"][0]
    assert (bounds["minimum"], bounds["maximum"]) == (5, 12)

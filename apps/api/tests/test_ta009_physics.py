"""TA-009 fizik: tuzak seti, sözleşme uyumu, bayrak, iki sağlayıcı yolunda kanonik çıktı ve platform sınırları.

Ağ ve ücretli çağrı yoktur. OpenAI yolu sahte istemci, Anthropic yolu ``httpx.MockTransport`` ile çalışır. Sahte
sağlayıcı sonucu sözleşme uyumudur; model kalitesi değildir.
"""

from __future__ import annotations

import json
from dataclasses import replace
from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

import apps.api.app.features.lessons.openai_provider as lesson_module
from apps.api.app.core.settings import Settings
from apps.api.app.core.usage import UsageTracker
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.education.math_adapter import UnsupportedSubjectError
from apps.api.app.features.education.science import ScientificProblemModel
from apps.api.app.features.lessons.exceptions import VerificationContradictionError
from apps.api.app.features.lessons.openai_provider import AnthropicLessonProvider, OpenAILessonProvider
from apps.api.app.features.lessons.schemas import PhysicsLessonDraftResponse
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.physics import circuits, conventions, graphs, laws, mechanics
from apps.api.app.main import create_app
from apps.api.tests.fake_openai import FakeRaw, body, fake_client
from apps.api.tests.test_anthropic_adapter import message, transport
from apps.api.tests.test_global_budget import AnyTokenVerifier, Clock
from apps.api.tests.test_lesson_provider_errors import lesson_payload
from apps.api.tests.test_question_integrity import analysis
from scripts import physics_matrix

TEXT = ("Sürtünmesiz yatay masadaki 6 kg kütleli A cismi, makaradan geçen kütlesi önemsiz iple 4 kg kütleli asılı B "
        "cismine bağlıdır. g = 10 m/s² alınız. Sistemin ivmesi kaç m/s²'dir?")


def quantity(id_, symbol, kind, magnitude, unit, original, provenance="source_text", entity=None):
    return {"id": id_, "symbol": symbol, "kind": kind, "magnitude": magnitude, "unit": unit, "original": original,
            "provenance": provenance, "entity": entity, "state": None, "representation": "unspecified"}


def physics_model():
    return {"domain": "dynamics", "sign_convention": "+ yön: B aşağı",
            "quantities": [quantity("mA", "m_A", "mass", "6", "kg", "6 kg", entity="A"),
                           quantity("mB", "m_B", "mass", "4", "kg", "4 kg", entity="B"),
                           quantity("a", "a", "acceleration", None, "m/s^2", None, "provider_proposed"),
                           quantity("T", "T", "tension", None, "N", None, "provider_proposed")],
            "bodies": [{"entity": "A", "mass": "mA", "surface": "masa"}, {"entity": "B", "mass": "mB", "surface": None}],
            "surfaces": [{"id": "masa", "kind": "horizontal", "angle_deg": None, "friction": "none", "mu_static": None,
                          "mu_kinetic": None, "provenance": "source_text"}],
            "forces": [], "strings": [{"id": "ip", "bodies": ["A", "B"], "over_pulley": True, "provenance": "source_text"}],
            "phases": [], "collisions": [], "circuit": None,
            "laws": [{"law": "dynamics.newton_second", "system": ["A", "B"]}], "equations": [],
            "target": {"quantity": "a", "kind": "acceleration", "entity": None, "state": None,
                       "representation": "unspecified", "unit": "m/s^2", "element": None, "between": []}}


def physics_text(final: str) -> str:
    payload = lesson_payload()
    payload["concept_id"] = "concept_newton_second_law"
    payload["content"].update(known_values=["6 kg", "4 kg"], unknown="ivme", final_answer=final,
                              final_answer_expressions=[{"type": "equation", "latex": final}],
                              steps=[{"id": "step_1", "type": "result", "title": "Sistem", "explanation": "Sistemin ivmesi.",
                                      "expressions": [], "visual_reference": None}])
    payload["content"]["mathematical_model"] = None
    payload["content"]["physics_model"] = physics_model()
    return json.dumps(payload, ensure_ascii=False)


def physics_analysis():
    return analysis(question_text=TEXT, mathematical_expressions=[], answer_choices=[], subject="Fizik")


def provider(name, texts, monkeypatch, calls):
    queue = list(texts)

    def next_text():
        calls.append(1)
        return queue.pop(0) if len(queue) > 1 else queue[0]

    if name == "openai":
        async def parse(**kwargs):
            return FakeRaw(body(text=next_text()))

        monkeypatch.setattr(lesson_module, "AsyncOpenAI",
                            lambda **kw: SimpleNamespace(responses=fake_client(parse).responses, close=AsyncMock()))
        return OpenAILessonProvider("key", "test-model", 5)
    return AnthropicLessonProvider("key", "claude-sonnet-5-5", 5,
                                   transport=httpx.MockTransport(lambda request: message(text=next_text())))


async def run(name, texts, monkeypatch, enabled=True):
    calls: list = []
    service = LessonService(provider(name, texts, monkeypatch, calls), MathAIService(), BoardPlanner(),
                            physics_enabled=enabled)
    try:
        return await service.generate(physics_analysis()), len(calls)
    except VerificationContradictionError:
        return "contradiction", len(calls)


PATHS = pytest.mark.parametrize("path", ["openai", "anthropic"])


# --- tuzak seti ve çözücüler ---------------------------------------------------------------------------------------

def test_original_trap_set_passes_and_every_answer_is_derived():
    results, problems = physics_matrix.run()
    assert problems == [] and len(results) >= 30
    assert {r["origin"] for r in results} == {"derived"}  # bağımsız öğretmen anahtarı yok


def test_problem_convention_takes_precedence_over_standard_constant():
    facts = conventions.read("g = 10 m/s² ve sin 37° = 0,6 alınız.")
    assert conventions.gravity(facts).value == 10 and conventions.gravity(facts).origin == "problem_convention"
    assert conventions.trig_value(facts, "cos", Fraction(53)).value == Fraction(3, 5)
    standard = conventions.gravity(conventions.read("Bir taş bırakılıyor."))
    assert standard.origin == "standard_constant" and "CGPM" in standard.source
    assert conventions.gravity(conventions.read("Kurgusal bir gezegende")) is None
    assert conventions.trig_value(conventions.read(""), "sin", Fraction(37)) is None  # 0,6 uydurulmaz


def test_unknown_condition_is_never_treated_as_satisfied():
    problem = ScientificProblemModel.model_validate({"subject": "physics", "entities": [], "physics": {"domain": "kinematics"}})
    ctx = laws.Context(problem, problem.physics, conventions.read("Bir araç hızlanıyor."), "")
    results = {r.condition: r for r in laws.evaluate("kinematics.constant_acceleration", ctx)}
    assert results["constant_acceleration"].state == "unknown" and results["constant_acceleration"].open
    assert results["one_dimensional"].assumption_tr  # varsayılabilir koşul öğrenciye görünür varsayım olur


def test_kinematics_reports_ambiguous_time_instead_of_guessing():
    with pytest.raises(mechanics.Unsupported, match="ambiguous_time"):
        mechanics.suvat({"v0": Fraction(10), "a": Fraction(-2), "x": Fraction(16)}, "t")
    assert mechanics.suvat({"v0": Fraction(0), "a": Fraction(2), "t": Fraction(3)}, "x")[0] == 9


def test_velocity_time_graph_area_and_constancy():
    problem = ScientificProblemModel.model_validate({"subject": "physics", "figures": [{"id": "f", "kind": "graph"}],
        "graphs": [{"id": "g", "figure": "f", "points_origin": "printed_values", "points": [["0", "4"], ["2", "0"], ["4", "-4"]],
                    "x": {"name": "t", "unit": {"original": "s", "status": "parsed", "canonical": "s",
                                                 "dimension": [0, 0, 1, 0, 0, 0, 0], "scale": "1"}, "scale": "explicit_linear"},
                    "y": {"name": "v", "unit": {"original": "m/s", "status": "parsed", "canonical": "m·s^-1",
                                                 "dimension": [1, 0, -1, 0, 0, 0, 0], "scale": "1"}, "scale": "explicit_linear"}}]})
    facts = graphs.velocity_time(problem.graphs[0])
    assert (facts.displacement, facts.distance, facts.constant_slope) == (0, 8, True)


def test_series_parallel_decision_comes_from_topology_not_proximity():
    from apps.api.app.features.education.science import CircuitModel
    from apps.api.app.features.physics.values import Value

    values = {k: Value(k, None, Fraction(v), (0, 0, 0, 0, 0, 0, 0), "resistance", "source_text", str(v))
              for k, v in {"R1": 3, "R2": 6}.items()}
    parallel = CircuitModel.model_validate({"nodes": ["a", "b"], "elements": [
        {"id": "x", "kind": "resistor", "nodes": ["a", "b"], "value": "R1", "provenance": "source_text"},
        {"id": "y", "kind": "resistor", "nodes": ["a", "b"], "value": "R2", "provenance": "source_text"}]})
    series = CircuitModel.model_validate({"nodes": ["a", "m", "b"], "elements": [
        {"id": "x", "kind": "resistor", "nodes": ["a", "m"], "value": "R1", "provenance": "source_text"},
        {"id": "y", "kind": "resistor", "nodes": ["m", "b"], "value": "R2", "provenance": "source_text"}]})
    assert circuits.equivalent_resistance(parallel, values, "a", "b") == 2
    assert circuits.equivalent_resistance(series, values, "a", "b") == 9


# --- sözleşmeler -------------------------------------------------------------------------------------------------

def test_scientific_problem_model_stays_backward_compatible():
    stored = {"subject": "physics", "known": [{"id": "v", "magnitude": "20", "provenance": "source_text"}]}
    model = ScientificProblemModel.model_validate(stored)
    assert model.physics is None and model.known[0].kind is None and model.known[0].representation == "unspecified"
    with pytest.raises(ValueError):
        ScientificProblemModel.model_validate({"subject": "physics", "entities": [], "physics": {
            "domain": "dynamics", "forces": [{"id": "f", "kind": "applied", "on": "ghost", "direction": "+x",
                                              "provenance": "source_text"}]}})


def test_physics_response_schema_is_sent_only_for_physics_requests():
    from apps.api.app.core.schema_compat import anthropic_projection
    from apps.api.app.features.lessons.context import build_lesson_generation_context

    math = build_lesson_generation_context(analysis(question_text="2x = 8 ise x kaçtır?",
                                                    mathematical_expressions=["2x = 8"], answer_choices=[]))
    assert "physics" not in math.payload
    assert build_lesson_generation_context(physics_analysis()).payload["physics"]["subject_mode"] == "physics"
    projection = anthropic_projection(PhysicsLessonDraftResponse)
    assert projection.removed == ()  # düz tipler: Anthropic'e onaysız kısıt gitmez


# --- bayrak ve hizmet akışı (iki sağlayıcı yolu) ------------------------------------------------------------------

def test_physics_is_closed_to_students_by_default():
    assert Settings().physics_student_enabled is False


@pytest.mark.asyncio
async def test_physics_lesson_is_refused_when_the_flag_is_closed(monkeypatch):
    calls: list = []
    service = LessonService(provider("openai", [physics_text("a = 4 m/s^2")], monkeypatch, calls), MathAIService(),
                            BoardPlanner())
    with pytest.raises(UnsupportedSubjectError):
        await service.generate(physics_analysis())
    assert calls == []  # ücretli çağrı yapılmadan reddedilir


@pytest.mark.asyncio
@PATHS
async def test_verified_physics_lesson_makes_one_call_and_draws_labelled_facts(path, monkeypatch):
    result, calls = await run(path, [physics_text("a = 4 m/s^2")], monkeypatch)
    assert calls == 1 and not result.correction_attempted
    report = result.verification.physics
    assert result.verification.status == "verified" and report.capability == "verified" and report.answer == "matched"
    facts = next(e for e in result.board.elements if e.type == "physics_facts")
    assert "doğrulandı" in facts.text and any("sorunun uzlaşımı" in f for f in facts.facts)
    assert any(f.startswith("Varsayım:") for f in facts.facts)


@pytest.mark.asyncio
@PATHS
async def test_requested_versus_intermediate_triggers_one_correction(path, monkeypatch):
    result, calls = await run(path, [physics_text("T = 24 N"), physics_text("a = 4 m/s^2")], monkeypatch)
    assert calls == 2 and result.correction_attempted and result.verification.physics.answer == "matched"


@pytest.mark.asyncio
@PATHS
async def test_unresolved_physics_contradiction_is_rejected(path, monkeypatch):
    result, calls = await run(path, [physics_text("a = 6 m/s^2")], monkeypatch)
    assert result == "contradiction" and calls == 2


@pytest.mark.asyncio
async def test_both_adapters_yield_the_same_canonical_physics_lesson(monkeypatch):
    first, _ = await run("openai", [physics_text("a = 4 m/s^2")], monkeypatch)
    second, _ = await run("anthropic", [physics_text("a = 4 m/s^2")], monkeypatch)
    assert first.lesson.content.physics_model == second.lesson.content.physics_model
    left = first.verification.model_dump(exclude={"processing_time_ms"})
    right = second.verification.model_dump(exclude={"processing_time_ms"})
    assert left == right


def test_physics_verification_runs_inside_the_isolated_worker():
    from apps.api.app.features.lessons.physics_normalization import normalize_physics_lesson_draft_response
    from apps.api.app.features.lessons.schemas import LessonPlan
    from apps.api.app.features.mathai.isolated import IsolatedMathAI

    draft = normalize_physics_lesson_draft_response(PhysicsLessonDraftResponse.model_validate_json(physics_text("a = 4 m/s^2")))
    plan = LessonPlan(lesson_plan_id="lesson_p", source_analysis=physics_analysis(), learning_objectives=draft.learning_objectives,
                      concept_id=draft.concept_id, content=draft.content, provider="fixture", model="fixture",
                      lesson_generation_ms=1)
    result = IsolatedMathAI(max_processes=1, max_waiting=1).verify(plan)
    assert result.physics is not None and result.physics.capability == "verified"


# --- platform sınırları: çağrı tavanı ve hesap silme -------------------------------------------------------------

def physics_app(monkeypatch, responses, seen, **settings):
    config = Settings(provider_lesson="anthropic", anthropic_api_key="key", anthropic_lesson_model="claude-sonnet-5-5",
                      physics_student_enabled=True, **settings)
    app = create_app(config)
    lesson = AnthropicLessonProvider("key", "claude-sonnet-5-5", 5, transport=transport(*responses, seen=seen))
    app.state.container = replace(app.state.container, token_verifier=AnyTokenVerifier(),
                                  usage_tracker=UsageTracker(config, None, Clock()),
                                  lesson_service=LessonService(lesson, MathAIService(), BoardPlanner(), physics_enabled=True))
    return app


def post(app, uid, monkeypatch=None):
    source = physics_analysis().model_copy(update={"request_id": "analysis_" + uuid4().hex})
    app.state.container.student_service.save_analysis(AuthenticatedUser(uid=uid), source)
    return TestClient(app).post("/api/v1/lessons/generate", json={"analysis_id": source.request_id},
                                headers={"Authorization": f"Bearer {uid}"})


def test_physics_flow_respects_the_logical_call_ceiling(monkeypatch):
    seen: list = []
    wrong = message(text=physics_text("a = 6 m/s^2"))
    app = physics_app(monkeypatch, [wrong, wrong], seen, lesson_max_provider_calls=1)
    response = post(app, "u_" + uuid4().hex)
    assert len(seen) == 1 and response.status_code >= 400  # düzeltme turu tavanı aşamaz


def test_physics_flow_checks_account_deletion_before_any_call(monkeypatch):
    seen: list = []
    app = physics_app(monkeypatch, [message(text=physics_text("a = 4 m/s^2"))], seen)
    monkeypatch.setattr("apps.api.app.core.admission.deletion_started", lambda db, user: True)
    response = post(app, "u_" + uuid4().hex)
    assert (response.status_code, response.json()["error"]) == (409, "account_deletion_in_progress") and seen == []


def test_physics_flow_through_the_endpoint_is_verified(monkeypatch):
    seen: list = []
    app = physics_app(monkeypatch, [message(text=physics_text("a = 4 m/s^2"))], seen)
    response = post(app, "u_" + uuid4().hex)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["verification"]["physics"]["capability"] == "verified" and len(seen) == 1

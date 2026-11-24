"""TA-005B §6: izole MathAI eşzamanlılık sınırı, hata sınıfları ve süreç birleştirme. Ağ çağrısı yoktur."""

import subprocess
import threading
from dataclasses import replace

import pytest

from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai import isolated
from apps.api.app.features.mathai.isolated import IsolatedMathAI, MathAIUnavailable
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.main import create_app
from apps.api.tests.client import authenticated_client
from apps.api.tests.test_lesson_pipeline import AlgebraLessonProvider
from apps.api.tests.test_mathai import plan


def counting(monkeypatch):
    calls = []
    real = subprocess.run

    def spy(argv, **kwargs):
        calls.append(kwargs["input"][:30])
        return real(argv, **kwargs)

    monkeypatch.setattr(isolated.subprocess, "run", spy)
    return calls


def test_reconcile_then_verify_uses_one_process_and_matches_in_process_result(monkeypatch):
    calls = counting(monkeypatch)
    math = IsolatedMathAI()
    source = plan()
    reconciled = math.reconcile_answer_choice(source)
    verified = math.verify(reconciled)
    assert len(calls) == 1 and calls[0].startswith('["reconcile_verify"')
    local = MathAIService()
    expected = local.verify(local.reconcile_answer_choice(source))
    assert verified.model_dump(exclude={"processing_time_ms"}) == expected.model_dump(exclude={"processing_time_ms"})
    assert set(math.last_timing) == {"total_ms", "compute_ms", "startup_ms"} and math.last_timing["startup_ms"] > 0
    math.verify(reconciled)  # önbellek tek kullanımlıktır; ikinci doğrulama yeni süreçtir
    assert len(calls) == 2 and calls[1].startswith('["verify"')


def test_queue_full_is_busy_with_retry_after_and_does_not_spawn(monkeypatch):
    calls = counting(monkeypatch)
    math = IsolatedMathAI(max_processes=1, max_waiting=0)
    math._slots.acquire()  # tek yuva meşgul
    with pytest.raises(MathAIUnavailable) as caught:
        math.check_answer("2x=8", "4", "x")
    assert caught.value.code == "mathai_busy" and caught.value.headers == {"Retry-After": "2"}
    assert calls == []


def test_queue_wait_timeout_is_separate_from_compute_timeout(monkeypatch):
    calls = counting(monkeypatch)
    math = IsolatedMathAI(max_processes=1, max_waiting=2)
    math.queue_timeout_seconds = 0.05
    math._slots.acquire()
    with pytest.raises(MathAIUnavailable) as caught:
        math.check_answer("2x=8", "4", "x")
    assert caught.value.code == "mathai_busy" and calls == [] and math._waiting == 0
    math._slots.release()
    assert math.check_answer("2x=8", "4", "x")[0]  # yuva boşalınca çalışır; timeout_seconds değişmedi
    assert math.timeout_seconds == 8.0


@pytest.mark.parametrize(("error", "code"), [
    # TA-005C: hazır satırı görüldüyse hesaplama zaman aşımı, görülmediyse başlatma gecikmesi.
    (subprocess.TimeoutExpired(["worker"], 8.0, output=b"__mathai_ready__\n"), "mathai_timeout"),
    (subprocess.TimeoutExpired(["worker"], 8.0, output="__mathai_ready__\n"), "mathai_timeout"),
    (subprocess.TimeoutExpired(["worker"], 8.0), "mathai_startup_timeout"),
    (subprocess.TimeoutExpired(["worker"], 8.0, output=b""), "mathai_startup_timeout"),
    (subprocess.CalledProcessError(1, ["worker"]), "mathai_error"),
    (subprocess.CalledProcessError(-24, ["worker"]), "mathai_error"),  # RLIMIT_CPU sinyali: işçi hatası
    (OSError("spawn"), "mathai_error"),
])
def test_failures_have_distinct_codes_and_release_the_slot(monkeypatch, error, code):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(isolated.subprocess, "run", fail)
    math = IsolatedMathAI(max_processes=1, max_waiting=0)
    for _ in range(3):  # yuva her hatada geri verilir; aksi hâlde ikinci deneme mathai_busy olurdu
        with pytest.raises(MathAIUnavailable) as caught:
            math.check_answer("2x=8", "4", "x")
        assert caught.value.code == code and caught.value.headers is None


def test_concurrency_never_exceeds_limit(monkeypatch):
    active, peak, lock = [0], [0], threading.Lock()
    real = subprocess.run

    def tracked(argv, **kwargs):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        try:
            return real(argv, **kwargs)
        finally:
            with lock:
                active[0] -= 1

    monkeypatch.setattr(isolated.subprocess, "run", tracked)
    math = IsolatedMathAI(max_processes=2, max_waiting=16)
    math.queue_timeout_seconds = 30
    results = []
    threads = [threading.Thread(target=lambda: results.append(math.check_answer("2x=8", "4", "x")[0])) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [True] * 6 and peak[0] <= 2


class BusyMathAI(MathAIService):
    def reconcile_answer_choice(self, plan):
        raise MathAIUnavailable("mathai_busy", 2)


def test_api_returns_busy_code_and_retry_after():
    from apps.api.app.features.auth.schemas import AuthenticatedUser

    app = create_app()
    service = LessonService(AlgebraLessonProvider(), BusyMathAI(), BoardPlanner())
    app.state.container = replace(app.state.container, lesson_service=service)
    analysis = plan().source_analysis
    app.state.container.student_service.save_analysis(AuthenticatedUser(uid="student-a"), analysis)
    with authenticated_client(app) as client:
        response = client.post("/api/v1/lessons/generate", json={"analysis_id": analysis.request_id})
    assert (response.status_code, response.json()["error"]) == (503, "mathai_busy")
    assert response.headers["Retry-After"] == "2"


def test_worker_announces_readiness_before_reading_input_and_output_still_parses():
    """TA-005C: gerçek alt süreç; hazır satırı ilk satırdır, zarf son satırdır."""
    math = IsolatedMathAI(max_processes=1, max_waiting=0)
    assert math.check_answer("2x=8", "4", "x")[0]
    assert math.timeout_seconds == 8.0 and math.last_timing["startup_ms"] >= 0


def test_unparseable_worker_output_is_a_worker_failure(monkeypatch):
    def garbage(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="__mathai_ready__\nbozuk", stderr="")

    monkeypatch.setattr(isolated.subprocess, "run", garbage)
    with pytest.raises(MathAIUnavailable) as caught:
        IsolatedMathAI(max_processes=1, max_waiting=0).check_answer("2x=8", "4", "x")
    assert caught.value.code == "mathai_error"


def test_startup_timeout_has_its_own_public_code():
    from fastapi.testclient import TestClient

    from apps.api.app.main import create_app

    app = create_app()

    @app.get("/__startup")
    def boom():
        raise MathAIUnavailable("mathai_startup_timeout")

    response = TestClient(app).get("/__startup")
    assert (response.status_code, response.json()["error"]) == (503, "mathai_startup_timeout")
    assert "Retry-After" not in response.headers

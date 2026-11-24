"""Güvenilmeyen her doğrulama için yeni, kesilebilir bir süreç (TA-005B §6).

- **Eşzamanlılık sınırı:** aynı anda en çok ``max_processes`` alt süreç çalışır. Sıra beklemesi
  (``queue_timeout_seconds``) hesaplama zaman aşımından (``timeout_seconds``) ayrıdır; bekleyen sayısı
  ``max_waiting`` ile sınırlıdır.
- **Hata sınıfları:** ``mathai_busy`` (kuyruk dolu ya da bekleme aşıldı; 503 + ``Retry-After``),
  ``mathai_startup_timeout`` (TA-005C: süreç toplam sınır içinde başlatmayı bitiremedi; 503),
  ``mathai_timeout`` (başlatma bitti, hesaplama sınırı aştı; 503), ``mathai_error`` (alt süreç hatası,
  sinyal veya bozuk çıktı; 503). Ayrım worker'ın içe aktarmadan sonra yazdığı hazır satırına dayanır;
  toplam sınır (``timeout_seconds``) değişmedi.
- **Birleştirme:** ders hattı her ``reconcile_answer_choice`` çağrısından hemen sonra aynı planla
  ``verify`` çağırır. Uzlaştırma aynı süreçte doğrulamayı da hesaplar; sonuç, uzlaştırılmış planın
  kanonik JSON'una bağlı kısa ömürlü bir önbellekte tutulur ve aynı plan için ikinci süreç açılmaz.
- **Isıtılmış süreç havuzu yok:** ``RLIMIT_CPU`` ve ``RLIMIT_AS`` süreç ömrü boyunca birikir ve
  yükseltilemez; görev başına sınır kurulamaz. SymPy önbelleği görevler arasında durum taşır. Aynı
  güçte izolasyon korunamadığı için havuz uygulanmadı.
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from hashlib import sha256

from fastapi import HTTPException

from ..lessons.schemas import LessonPlan
from .parser import MathParseError
from .schemas import VerificationResult
from .worker import READY


class MathAIUnavailable(HTTPException):
    """503. ``code`` istemciye ``error`` olarak döner; yalnız ``mathai_busy`` ``Retry-After`` taşır."""

    def __init__(self, code: str, retry_after: int | None = None):
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(503, "Symbolic computation unavailable.", headers=headers)
        self.code = code


logger = logging.getLogger(__name__)


def _ready(output) -> bool:
    """Zaman aşımına kadar worker hazır satırını yazdı mı? (TimeoutExpired çıktısı bytes olabilir.)"""
    if isinstance(output, bytes):
        output = output.decode("utf-8", "replace")
    return bool(output) and READY in output


def _env_int(name, default):
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


class IsolatedMathAI:
    timeout_seconds = 8.0
    queue_timeout_seconds = 2.0
    retry_after_seconds = 2
    cache_size = 32

    def __init__(self, max_processes: int | None = None, max_waiting: int | None = None):
        self.max_processes = max_processes or _env_int("TEACHERAI_MATHAI_MAX_PROCESSES", os.cpu_count() or 2)
        self.max_waiting = max_waiting if max_waiting is not None else _env_int(
            "TEACHERAI_MATHAI_MAX_WAITING", 4 * self.max_processes)
        self._slots = threading.BoundedSemaphore(self.max_processes)
        self._lock = threading.Lock()
        self._waiting = 0
        self._verified: OrderedDict[str, dict] = OrderedDict()
        self.last_timing: dict | None = None  # ölçüm betiği için: spawn ve hesaplama ayrı

    def _acquire(self):
        if self._slots.acquire(blocking=False):
            return
        with self._lock:
            if self._waiting >= self.max_waiting:
                logger.warning(json.dumps({"event": "mathai_unavailable", "code": "mathai_busy", "reason": "queue_full",
                                           "waiting": self._waiting, "max_waiting": self.max_waiting}))
                raise MathAIUnavailable("mathai_busy", self.retry_after_seconds)
            self._waiting += 1
        try:
            if not self._slots.acquire(timeout=self.queue_timeout_seconds):
                logger.warning(json.dumps({"event": "mathai_unavailable", "code": "mathai_busy", "reason": "queue_wait",
                                           "queue_timeout_seconds": self.queue_timeout_seconds}))
                raise MathAIUnavailable("mathai_busy", self.retry_after_seconds)
        finally:
            with self._lock:
                self._waiting -= 1

    def _run(self, operation, data):
        self._acquire()
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "apps.api.app.features.mathai.worker"],
                input=json.dumps([operation, data]),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=self.timeout_seconds,
                check=True,
            )
        except subprocess.TimeoutExpired as exc:
            code = "mathai_timeout" if _ready(exc.stdout) else "mathai_startup_timeout"
            self._report(code, operation, started)
            raise MathAIUnavailable(code) from exc
        except (subprocess.CalledProcessError, OSError) as exc:
            self._report("mathai_error", operation, started, returncode=getattr(exc, "returncode", None))
            raise MathAIUnavailable("mathai_error") from exc
        finally:
            self._slots.release()
        try:
            lines = [line for line in completed.stdout.splitlines() if line.strip()]
            envelope = json.loads(lines[-1])
        except (ValueError, IndexError) as exc:
            self._report("mathai_error", operation, started, returncode=0)
            raise MathAIUnavailable("mathai_error") from exc
        total = (time.perf_counter() - started) * 1000
        compute = envelope["timing"]["compute_ms"]
        self.last_timing = {"total_ms": total, "compute_ms": compute, "startup_ms": total - compute}
        return envelope["value"]

    @staticmethod
    def _report(code, operation, started, returncode=None):
        """Yalnız sınıf, işlem adı, süre ve çıkış kodu; plan içeriği veya öğrenci verisi yazılmaz."""
        logger.warning(json.dumps({"event": "mathai_unavailable", "code": code, "operation": operation,
                                   "elapsed_ms": round((time.perf_counter() - started) * 1000),
                                   "returncode": returncode}, separators=(",", ":")))

    @staticmethod
    def _key(plan_json):
        return sha256(json.dumps(plan_json, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def reconcile_answer_choice(self, plan):
        result = self._run("reconcile_verify", plan.model_dump(mode="json"))
        with self._lock:
            self._verified[self._key(result["plan"])] = result["verification"]
            while len(self._verified) > self.cache_size:
                self._verified.popitem(last=False)
        return LessonPlan.model_validate(result["plan"])

    def verify(self, plan):
        data = plan.model_dump(mode="json")
        with self._lock:
            cached = self._verified.pop(self._key(data), None)
        if cached is None:
            cached = self._run("verify", data)
        return VerificationResult.model_validate(cached)

    def check_answer(self, question, answer, variable):
        result = self._run("answer", [question, answer, variable])
        if isinstance(result, dict):
            raise MathParseError("unsupported answer")
        return result

"""A new interruptible process per untrusted verification, including reconciliation."""

import json
import subprocess
import sys

from .parser import MathParseError
from .schemas import VerificationResult
from ..lessons.schemas import LessonPlan


class IsolatedMathAI:
    timeout_seconds = 8.0

    def _run(self, operation, data):
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
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            from fastapi import HTTPException

            raise HTTPException(503, "Symbolic computation unavailable.") from exc
        return json.loads(completed.stdout)

    def reconcile_answer_choice(self, plan):
        return LessonPlan.model_validate(
            self._run("reconcile", plan.model_dump(mode="json"))
        )

    def verify(self, plan):
        return VerificationResult.model_validate(
            self._run("verify", plan.model_dump(mode="json"))
        )

    def check_answer(self, question, answer, variable):
        result = self._run("answer", [question, answer, variable])
        if isinstance(result, dict):
            raise MathParseError("unsupported answer")
        return result

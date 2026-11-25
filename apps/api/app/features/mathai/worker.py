import json
import sys
import time

READY = "__mathai_ready__"


def main():
    boot = time.perf_counter()
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 << 20, 512 << 20))
        resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
    from ..lessons.schemas import LessonPlan
    from .service import MathAIService

    # TA-005C: başlatma (yorumlayıcı + içe aktarma) bitti. Üst süreç zaman aşımında bu satırı görüp
    # görmediğine göre başlatma gecikmesini hesaplama zaman aşımından ayırır.
    print(READY, flush=True)
    import_ms = (time.perf_counter() - boot) * 1000
    operation, data = json.load(sys.stdin)
    started = time.perf_counter()  # içe aktarma sonrası: yalnız hesaplama
    service = MathAIService()
    phases: dict = {}
    if operation == "answer":
        from .parser import MathParseError

        try:
            value = service.check_answer(*data)
        except MathParseError:
            value = {"invalid_answer": True}
    elif operation == "reconcile_verify":
        plan = service.reconcile_answer_choice(LessonPlan.model_validate(data))
        verification = service.verify(plan)
        dumping = time.perf_counter()
        value = {"plan": plan.model_dump(mode="json"), "verification": verification.model_dump(mode="json")}
        phases["serialize_ms"] = (time.perf_counter() - dumping) * 1000
    elif operation == "ping":
        value = None
    else:
        plan = LessonPlan.model_validate(data)
        value = (
            service.verify(plan)
            if operation == "verify"
            else service.reconcile_answer_choice(plan)
        ).model_dump(mode="json")
    # TA-008B §20: faz süreleri yalnız sayıdır; içerik taşımaz.
    phases |= getattr(service, "last_phases", {})
    timing = {"compute_ms": (time.perf_counter() - started) * 1000, "import_ms": import_ms, **phases}
    print(json.dumps({"value": value, "timing": timing}))


if __name__ == "__main__":
    main()

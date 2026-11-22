import json
import sys
import time


def main():
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 << 20, 512 << 20))
        resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
    from ..lessons.schemas import LessonPlan
    from .service import MathAIService

    operation, data = json.load(sys.stdin)
    started = time.perf_counter()  # içe aktarma sonrası: yalnız hesaplama
    service = MathAIService()
    if operation == "answer":
        from .parser import MathParseError

        try:
            value = service.check_answer(*data)
        except MathParseError:
            value = {"invalid_answer": True}
    elif operation == "reconcile_verify":
        plan = service.reconcile_answer_choice(LessonPlan.model_validate(data))
        value = {"plan": plan.model_dump(mode="json"), "verification": service.verify(plan).model_dump(mode="json")}
    elif operation == "ping":
        value = None
    else:
        plan = LessonPlan.model_validate(data)
        value = (
            service.verify(plan)
            if operation == "verify"
            else service.reconcile_answer_choice(plan)
        ).model_dump(mode="json")
    print(json.dumps({"value": value, "timing": {"compute_ms": (time.perf_counter() - started) * 1000}}))


if __name__ == "__main__":
    main()

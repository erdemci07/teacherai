import sys
import json


def main():
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 << 20, 512 << 20))
        resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
    from .service import MathAIService
    from ..lessons.schemas import LessonPlan

    operation, data = json.load(sys.stdin)
    service = MathAIService()
    if operation == "answer":
        from .parser import MathParseError

        try:
            value = service.check_answer(*data)
        except MathParseError:
            value = {"invalid_answer": True}
    else:
        plan = LessonPlan.model_validate(data)
        value = (
            service.verify(plan)
            if operation == "verify"
            else service.reconcile_answer_choice(plan)
        ).model_dump(mode="json")
    print(json.dumps(value))


if __name__ == "__main__":
    main()

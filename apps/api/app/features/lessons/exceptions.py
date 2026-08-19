class LessonError(Exception):
    code = "lesson_error"; status_code = 500; public_message = "Öğretmen anlatımı oluşturulamadı. Lütfen tekrar deneyin."
class LessonProviderConfigurationError(LessonError):
    code = "lesson_provider_not_configured"; status_code = 503; public_message = "Öğretmen anlatımı servisi yapılandırılmamış."
class LessonProviderUnavailableError(LessonError):
    code = "lesson_provider_unavailable"; status_code = 503
class InvalidLessonPlanError(LessonError):
    code = "invalid_lesson_plan"; status_code = 502; public_message = "Güvenilir bir anlatım oluşturulamadı."
class VerificationContradictionError(LessonError):
    code = "verification_contradiction"; status_code = 422; public_message = "Bu çözüm matematiksel kontrolden geçemedi. Yeniden inceleyelim."

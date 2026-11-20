class LessonError(Exception):
    code = "lesson_error"; status_code = 500; public_message = "Öğretmen anlatımı oluşturulamadı. Lütfen tekrar deneyin."
class LessonProviderConfigurationError(LessonError):
    code = "lesson_provider_not_configured"; status_code = 503; public_message = "Öğretmen anlatımı servisi yapılandırılmamış."
class LessonProviderUnavailableError(LessonError):
    code = "lesson_provider_unavailable"; status_code = 503
class LessonProviderTimeoutError(LessonError):
    code = "lesson_timeout"; status_code = 504; public_message = "İnceleme beklediğimden uzun sürdü. Tekrar deneyebilir misin?"
class InvalidLessonPlanError(LessonError):
    code = "invalid_lesson_plan"; status_code = 502; public_message = "Güvenilir bir anlatım oluşturulamadı."
class LessonContextTooLargeError(LessonError):
    code = "lesson_context_too_large"; status_code = 422; public_message = "Bu sorunun içeriği oldukça yoğun olduğu için anlatımı hazırlayamadım. Yeniden incelemeyi deneyebilirsin."
class MathVerificationError(LessonError):
    code = "math_verification_failed"; status_code = 502; public_message = "Çözüm matematiksel kontrolden geçirilemedi. Lütfen tekrar deneyin."
class VerificationContradictionError(LessonError):
    code = "verification_contradiction"; status_code = 422; public_message = "Bu çözüm matematiksel kontrolden geçemedi. Yeniden inceleyelim."
class InvalidQuestionAnalysisError(LessonError):
    code = "invalid_question_analysis"; status_code = 422; public_message = "Bu görsel geçerli ve okunabilir bir matematik sorusu içermiyor."
class QuestionClarificationRequiredError(LessonError):
    code = "question_clarification_required"; status_code = 409; public_message = "Soruyu çözmeden önce okunamayan bir kısmı netleştirmemiz gerekiyor."
class StaleQuestionRevisionError(LessonError):
    code = "stale_question_revision"; status_code = 409; public_message = "Soru bu arada güncellendi. Güncel hâliyle devam edelim."

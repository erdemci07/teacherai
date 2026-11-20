"""TA-001 öncesi ve sonrası paylaşım biçimlerinin ayrımı.

TA-001 ile yeni paylaşımlar yalnız sabit başlık, işlem adımları ve matematiksel sonuç
içerir (ShareService._public_lesson_snapshot). Tespit ölçütü bu sabit alanlardır:
- question_summary == "Paylaşılan çözümün işlem adımları"
- lesson_snapshot.learning_objectives == ["İşlem adımlarını takip et."]
- lesson_snapshot.content.question_understanding == "İşlem adımlarını incele."
Üçünden biri farklıysa paylaşım TA-001 öncesi biçimdedir ve ham soru metni veya
serbest anlatım taşıyabilir.
"""

CURRENT_SUMMARY = "Paylaşılan çözümün işlem adımları"
CURRENT_OBJECTIVES = ["İşlem adımlarını takip et."]
CURRENT_UNDERSTANDING = "İşlem adımlarını incele."


def is_current_format(data: dict) -> bool:
    lesson = data.get("lesson_snapshot") or {}
    content = lesson.get("content") or {}
    return (
        data.get("question_summary") == CURRENT_SUMMARY
        and lesson.get("learning_objectives") == CURRENT_OBJECTIVES
        and content.get("question_understanding") == CURRENT_UNDERSTANDING
    )

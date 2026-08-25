from datetime import datetime, timezone
from html import escape
from secrets import token_urlsafe
from urllib.parse import quote

from apps.api.app.core.settings import Settings
from apps.api.app.features.lessons.exceptions import InvalidLessonPlanError
from apps.api.app.features.lessons.normalization import _contains_placeholder_artifact
from apps.api.app.features.lessons.service import GeneratedLesson

from .repository import ShareRepository
from .schemas import CreateShareResponse, PublicShareResponse, PublicSolutionSnapshot

MAX_STEPS = 12
MAX_BOARD_ELEMENTS = 40
MAX_EXPRESSIONS_PER_STEP = 8

SHARE_TITLE = "TeacherAI bu matematik sorusunu çözdü"
SHARE_DESCRIPTION = "Adım adım öğretmen anlatımıyla çözümü incele. Sen de kendi sorunu TeacherAI ile çöz."


class ShareService:
    def __init__(self, repository: ShareRepository, settings: Settings):
        self.repository = repository
        self.settings = settings

    def create_or_reuse(self, result: GeneratedLesson, existing_share_id: str | None = None) -> CreateShareResponse:
        if existing_share_id:
            existing = self.repository.get(existing_share_id)
            if existing and existing.source_lesson_plan_id == result.lesson.lesson_plan_id and existing.status == "published":
                return CreateShareResponse(share_id=existing.share_id, share_url=self.share_url(existing.share_id))

        existing = self.repository.find_by_lesson_plan_id(result.lesson.lesson_plan_id)
        if existing:
            return CreateShareResponse(share_id=existing.share_id, share_url=self.share_url(existing.share_id))

        self._validate_public_result(result)
        share_id = self._new_share_id()
        now = datetime.now(timezone.utc)
        lesson = result.lesson
        snapshot = PublicSolutionSnapshot(
            share_id=share_id,
            created_at=now,
            updated_at=now,
            topic=lesson.source_analysis.topic,
            subtopic=lesson.source_analysis.subtopic,
            question_summary=lesson.source_analysis.question_text,
            final_answer=lesson.content.final_answer,
            lesson_snapshot=lesson,
            board_snapshot=result.board,
            app_version=self.settings.version,
            source_lesson_plan_id=lesson.lesson_plan_id,
        )
        self.repository.save(snapshot)
        return CreateShareResponse(share_id=share_id, share_url=self.share_url(share_id))

    def get_public(self, share_id: str) -> PublicShareResponse | None:
        snapshot = self.repository.get(share_id)
        if not snapshot or snapshot.status != "published" or snapshot.revoked_at:
            return None
        return PublicShareResponse(share_id=share_id, share_url=self.share_url(share_id), snapshot=snapshot)

    def share_url(self, share_id: str) -> str:
        return f"{self.public_app_url}/s/{quote(share_id)}"

    @property
    def public_app_url(self) -> str:
        return self.settings.public_app_url.rstrip("/")

    @property
    def og_image_url(self) -> str:
        path = self.settings.share_og_image_path
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.public_app_url}/{path.lstrip('/')}"

    def render_public_html(self, share_id: str) -> str | None:
        public = self.get_public(share_id)
        if not public:
            return None
        snapshot = public.snapshot
        title = SHARE_TITLE
        description = SHARE_DESCRIPTION
        share_url = public.share_url
        app_url = f"{self.public_app_url}/shared/?id={quote(share_id)}"
        topic = snapshot.topic if snapshot.subtopic is None else f"{snapshot.topic} · {snapshot.subtopic}"
        question = snapshot.question_summary[:320]
        final = snapshot.final_answer[:180]
        return "\n".join(
            [
                "<!doctype html>",
                '<html lang="tr">',
                "<head>",
                '<meta charset="utf-8">',
                '<meta name="viewport" content="width=device-width, initial-scale=1">',
                '<meta name="robots" content="noindex, follow">',
                f'<title>{escape(title)}</title>',
                f'<meta name="description" content="{escape(description)}">',
                f'<meta property="og:title" content="{escape(title)}">',
                f'<meta property="og:description" content="{escape(description)}">',
                f'<meta property="og:url" content="{escape(share_url)}">',
                '<meta property="og:type" content="article">',
                f'<meta property="og:image" content="{escape(self.og_image_url)}">',
                '<meta name="twitter:card" content="summary_large_image">',
                f'<meta name="twitter:title" content="{escape(title)}">',
                f'<meta name="twitter:description" content="{escape(description)}">',
                f'<meta name="twitter:image" content="{escape(self.og_image_url)}">',
                f'<link rel="canonical" href="{escape(share_url)}">',
                f'<meta http-equiv="refresh" content="0; url={escape(app_url)}">',
                "</head>",
                '<body style="font-family:Inter,Arial,sans-serif;margin:32px;line-height:1.55;color:#172033">',
                "<main>",
                "<p>TeacherAI</p>",
                f"<h1>{escape(title)}</h1>",
                f"<p>{escape(description)}</p>",
                f"<p><strong>{escape(topic)}</strong></p>",
                f"<p>{escape(question)}</p>",
                f"<p><strong>Cevap:</strong> {escape(final)}</p>",
                f'<p><a href="{escape(app_url)}">Çözümü aç</a></p>',
                "</main>",
                "</body>",
                "</html>",
            ]
        )

    def _new_share_id(self) -> str:
        for _ in range(8):
            share_id = token_urlsafe(9).replace("_", "").replace("-", "")[:12]
            if len(share_id) >= 10 and not self.repository.get(share_id):
                return share_id
        raise RuntimeError("share id generation failed")

    def _validate_public_result(self, result: GeneratedLesson) -> None:
        lesson = result.lesson
        content = lesson.content
        if len(content.steps) > MAX_STEPS or len(result.board.elements) > MAX_BOARD_ELEMENTS:
            raise InvalidLessonPlanError
        for step in content.steps:
            if len(step.expressions) > MAX_EXPRESSIONS_PER_STEP:
                raise InvalidLessonPlanError
        public_text = [
            lesson.source_analysis.topic,
            lesson.source_analysis.subtopic,
            lesson.source_analysis.question_text,
            content.question_understanding,
            content.strategy,
            content.final_answer,
            content.takeaway,
            content.common_mistake,
            content.shortcut,
            content.teacher_tip,
            *content.known_values,
            *(step.title for step in content.steps),
            *(step.explanation for step in content.steps),
            *(item.text for item in result.board.elements),
        ]
        if any(isinstance(item, str) and _contains_placeholder_artifact(item) for item in public_text):
            raise InvalidLessonPlanError

import logging

from apps.api.app.core.settings import Settings


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    usage = logging.getLogger("teacherai.ai_usage")
    if not usage.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        usage.addHandler(handler)
        usage.propagate = False

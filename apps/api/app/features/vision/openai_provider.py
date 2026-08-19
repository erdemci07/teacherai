import asyncio
import base64
from pathlib import Path

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI
from pydantic import ValidationError

from apps.api.app.features.vision.exceptions import (
    InvalidProviderResponseError,
    ProviderConfigurationError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from apps.api.app.features.vision.provider import ProviderResult
from apps.api.app.features.vision.schemas import VisionProviderAnalysis


class OpenAIVisionProvider:
    name = "openai"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._model = model
        self.model = model
        self._timeout_seconds = timeout_seconds
        self._prompt = (Path(__file__).parent / "prompts" / "question_analysis.txt").read_text(encoding="utf-8")

    async def analyze_image(self, image: bytes, media_type: str) -> ProviderResult:
        if not self._api_key:
            raise ProviderConfigurationError

        image_url = f"data:{media_type};base64,{base64.b64encode(image).decode('ascii')}"
        client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout_seconds, max_retries=1)
        try:
            response = await asyncio.wait_for(
                client.responses.parse(
                    model=self._model,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": self._prompt},
                                {"type": "input_image", "image_url": image_url, "detail": "high"},
                            ],
                        }
                    ],
                    text_format=VisionProviderAnalysis,
                ),
                timeout=self._timeout_seconds + 2,
            )
        except (APITimeoutError, TimeoutError, asyncio.TimeoutError) as exc:
            raise ProviderTimeoutError from exc
        except APIConnectionError as exc:
            raise ProviderUnavailableError from exc
        except ValidationError as exc:
            raise InvalidProviderResponseError from exc
        except Exception as exc:
            raise ProviderUnavailableError from exc

        parsed = response.output_parsed
        if parsed is None:
            raise InvalidProviderResponseError
        try:
            analysis = VisionProviderAnalysis.model_validate(parsed)
        except Exception as exc:
            raise InvalidProviderResponseError from exc
        return ProviderResult(analysis=analysis, provider=self.name, model=self._model, response_id=response.id)

    async def health(self) -> bool:
        return bool(self._api_key)

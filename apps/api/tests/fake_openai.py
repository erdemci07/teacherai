"""Sahte OpenAI Responses istemcisi. Hiçbir ağ çağrısı yapmaz.

Gateway, SDK'nın `responses.with_raw_response.parse` yolunu kullanır ve ham gövdeyi
kendisi sınıflandırır. Buradaki yardımcılar bu gövdeyi testlerde üretir.
"""

import json
from types import SimpleNamespace


class FakeRaw:
    def __init__(self, body, request_id="req_fixture"):
        self.http_response = SimpleNamespace(json=lambda: body)
        self.request_id = request_id


def usage(output_tokens=100, input_tokens=50, cached_tokens=0, reasoning_tokens=0):
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_tokens_details": {"cached_tokens": cached_tokens},
        "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
    }


def body(parsed=None, *, text=None, status="completed", reason=None, refusal=False, tokens=None, model="fixture"):
    if text is None and parsed is not None:
        text = parsed.model_dump_json() if hasattr(parsed, "model_dump_json") else json.dumps(parsed)
    content = [{"type": "refusal", "refusal": "Yardımcı olamam."}] if refusal else []
    if text is not None:
        content.append({"type": "output_text", "text": text})
    return {
        "id": "resp_fixture",
        "model": model,
        "status": status,
        "incomplete_details": {"reason": reason} if reason else None,
        "output": [{"type": "message", "role": "assistant", "content": content}],
        "usage": tokens if tokens is not None else usage(),
    }


def _plain(value):
    if isinstance(value, SimpleNamespace):
        return {key: _plain(item) for key, item in vars(value).items()}
    return value


def legacy_body(result):
    """Eski `responses.parse` taklitlerinin döndürdüğü nesneyi ham gövdeye çevirir."""
    parsed = getattr(result, "output_parsed", None)
    return {
        **body(parsed, model=getattr(result, "model", None) or "fixture"),
        "status": getattr(result, "status", None) or "completed",
        "usage": _plain(getattr(result, "usage", None)) or {},
    }


def raw_responses(parse):
    """`parse(**kwargs)` taklidini ham yanıt yoluna bağlar; çağrı argümanları `parse` üzerinde kalır."""

    async def raw_parse(**kwargs):
        result = await parse(**kwargs)
        return result if isinstance(result, FakeRaw) else FakeRaw(legacy_body(result))

    return SimpleNamespace(parse=parse, with_raw_response=SimpleNamespace(parse=raw_parse))


def fake_client(parse):
    return SimpleNamespace(responses=raw_responses(parse))

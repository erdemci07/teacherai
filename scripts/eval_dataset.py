"""Değerlendirme veri seti biçimi ve doğrulayıcı (TA-001B, D paketi).

evals/datasets/*.jsonl dosyasındaki her satır bir EvalItem'dır. JSON Schema dosyası
(evals/schema/eval-item.schema.json) bu modelden üretilir; test ikisinin eşleştiğini denetler.

Telif koruması: kaynak yalnız synthetic, original_author veya teacher_contributed olabilir.
ÖSYM, yayınevi veya bilinmeyen kaynaklı, lisansı boş ya da görseli eksik öğe reddedilir.
"""

import json
import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "evals" / "schema" / "eval-item.schema.json"
BANNED_SOURCE = re.compile(r"ösym|osym|ÖSYM|yay[ıi]n|publisher|unknown|bilinm", re.IGNORECASE)


class EvalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    source: Literal["synthetic", "original_author", "teacher_contributed"]
    license: str = Field(min_length=1)
    author: str = Field(min_length=1)
    created_at: date
    image: str = Field(min_length=1, description="Veri seti dosyasına göre göreli görsel yolu")
    is_valid_math_question: bool
    question_text: str = Field(description="Interaction değerlendirmesi için referans soru metni")
    topic: str
    variable: str = "x"
    expected_expressions: list[str] = Field(default_factory=list)
    expected_solutions: list[str] = Field(default_factory=list)
    forbidden_in_hint: list[str] = Field(default_factory=list, description="İpucunda geçmemesi gereken değerler")
    variant: str | None = Field(default=None, description="ör. blur, rotate")
    notes: str | None = None

    @field_validator("source", mode="before")
    @classmethod
    def copyright_guard(cls, value):
        if isinstance(value, str) and BANNED_SOURCE.search(value):
            raise ValueError(f"telif: izin verilmeyen kaynak '{value}'")
        return value

    @field_validator("license", "author")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("boş olamaz")
        return value


def json_schema():
    return EvalItem.model_json_schema()


def load(path, check_images=True, check_math=True):
    """(öğeler, hatalar) döndürür. Hata mesajları içerik değil, öğe kimliği ve neden taşır."""
    path = Path(path)
    items, errors, seen = [], [], set()
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            item = EvalItem.model_validate(json.loads(line))
        except (ValidationError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}:{number}: {_reason(exc)}")
            continue
        if item.id in seen:
            errors.append(f"{path.name}:{number}: yinelenen kimlik {item.id}")
        seen.add(item.id)
        if check_images and not (path.parent / item.image).is_file():
            errors.append(f"{path.name}:{number}: görsel dosyası eksik ({item.id})")
        if check_math and item.is_valid_math_question:
            problem = _math_problem(item)
            if problem:
                errors.append(f"{path.name}:{number}: {problem} ({item.id})")
        items.append(item)
    return items, errors


def _reason(exc):
    if isinstance(exc, json.JSONDecodeError):
        return "bozuk JSON"
    return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())


def root_set(text):
    """Tek değişkenli denklemin gerçel çözüm kümesi; güvenli MathAI ayrıştırıcısıyla."""
    import sympy as sp

    from apps.api.app.features.mathai.parser import branches, equation

    result = set()
    for branch in branches(text):
        eq = equation(branch)
        if len(eq.free_symbols) != 1:
            raise ValueError("tek değişken gerekli")
        roots = sp.solveset(eq, next(iter(eq.free_symbols)), domain=sp.S.Reals)
        if roots != sp.EmptySet and not isinstance(roots, sp.FiniteSet):
            raise ValueError("sonlu olmayan çözüm kümesi")
        result.update(sp.nsimplify(root) for root in roots)
    return result


def value_set(values):
    import sympy as sp

    from apps.api.app.features.mathai.parser import expression

    return {sp.nsimplify(expression(value)) for value in values}


def _math_problem(item):
    """Beklenen çözüm kümesinin beklenen denklemin çözüm kümesine eşit olduğunu denetler."""
    if not item.expected_expressions or not item.expected_solutions:
        return "geçerli soru için beklenen ifade ve çözüm gerekli"
    try:
        same = root_set(item.expected_expressions[0]) == value_set(item.expected_solutions)
    except ValueError:
        return "beklenen ifade ayrıştırılamadı"
    return None if same else "beklenen çözüm kümesi denklemi sağlamıyor"

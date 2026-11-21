"""MathAI kontrollerinin v2 bloklarına ve problem modeline belirlenimci eşlenmesi (TA-004).

Eşleme yalnızca var olan kontrol kimliklerini kullanır: ``step_N_i`` → ifade bloğu, ``step_N`` → adım bloğu,
``final_answer``/``displayed_answer``/``answer_choice`` → cevap. Bloğa bağlanamayan kontrol ders düzeyinde
``unmapped`` kalır, rastgele bir bloğa iliştirilmez. Kontrolü olmayan adım ``not_checked`` olarak görünür.
Hiçbir kontrol sonucu sağlayıcı çıktısından gelmez.
"""

from __future__ import annotations

import re

from pydantic import ValidationError

from ..education.lesson import BlockCheck, DerivationStepBlock
from ..education.reasoning import EvidenceRef
from ..education.science import Observation, ScientificProblemModel
from .narrative import quantities, segments

_DIMENSION = {
    "transformation": "transformation", "equation": "calculation", "expression": "calculation",
    "function": "calculation", "geometry": "calculation", "domain": "domain", "answer_target": "answer_target",
    "final_answer": "answer_target",
}
_PARTIAL_REASONS = {"nonreversible_superset"}
_STATUS = {"passed": "passed", "failed": "failed", "unsupported": "unsupported"}


def _reason(value: str | None, fallback: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_.:-]", "_", value or fallback)[:120]
    return text if re.match(r"^[a-zA-Z0-9]", text) else fallback


def block_checks(result, blocks, integrity=None) -> list[BlockCheck]:
    ids = {block.id for block in blocks}
    output: list[BlockCheck] = []
    seen: dict[str, int] = {}
    covered: set[str] = set()
    for check in result.checks:
        base = f"mathai:{check.id}"
        seen[base] = seen.get(base, 0) + 1
        check_id = base if seen[base] == 1 else f"{base}:{seen[base]}"
        outcome = _STATUS[check.status]
        if outcome == "passed" and check.reason in _PARTIAL_REASONS:
            outcome = "partially_checked"
        dimension = _DIMENSION.get(check.kind, "calculation")
        reason = _reason(check.reason, {"passed": "check_passed", "failed": "check_failed"}.get(check.status, "check_unsupported"))
        evidence = [EvidenceRef(kind="check", id=check.id[:128])] if re.match(r"^[a-zA-Z0-9]", check.id) else []
        if check.id in {"final_answer", "displayed_answer"}:
            output.append(BlockCheck(id=check_id, scope="answer", dimension="answer_target", verifier="mathai",
                                     outcome=outcome, reason=reason, evidence=evidence))
        elif check.id == "answer_choice":
            output.append(BlockCheck(id=check_id, scope="answer", dimension="answer_choice", verifier="mathai",
                                     outcome=outcome, reason=reason, evidence=evidence))
        elif check.id in ids:
            covered.add(check.id)
            output.append(BlockCheck(id=check_id, scope="block", target=check.id, dimension=dimension, verifier="mathai",
                                     outcome=outcome, reason=reason, evidence=evidence))
        else:
            output.append(BlockCheck(id=check_id, scope="lesson", mapping="unmapped", dimension=dimension, verifier="mathai",
                                     outcome=outcome, reason=reason, evidence=evidence))
    for block in blocks:
        if not isinstance(block, DerivationStepBlock):
            continue
        children = [ref.id for ref in block.outputs if ref.kind == "block"]
        if block.id not in covered and not covered.intersection(children):
            output.append(BlockCheck(id=f"none:{block.id}", scope="block", target=block.id, dimension="transformation",
                                     verifier="none", outcome="not_checked", reason="no_verifier_for_step"))
    if integrity is not None and integrity.solvable:
        output.append(BlockCheck(id="integrity:source", scope="lesson", mapping="unmapped", dimension="source_consistency",
                                 verifier="integrity", outcome="partially_checked", reason="structural_source_check"))
    return output[:512]


def _chunks(text: str, size: int = 1000) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)] if text else []


def math_problem(analysis, subject, target) -> ScientificProblemModel | None:
    """Yetkili analizden anlam modeli. Kaynak gözlemi, görsel okuma, öğrenci onayı ve çıkarım ayrıdır."""
    integrity = analysis.integrity
    observations: list[Observation] = []
    for index, fact in enumerate(list(analysis.visual_elements.relevant_visual_facts) + list(analysis.visual_elements.relationships)):
        for part, chunk in enumerate(_chunks(fact.strip())):
            observations.append(Observation(id=f"obs_visual_{index + 1}_{part + 1}", statement=chunk, provenance="visual_reading",
                                            source="visual"))
    if integrity is not None:
        for index, item in enumerate(integrity.corrections):
            observations.append(Observation(id=f"obs_confirmed_{index + 1}", statement=f"{item.original} → {item.corrected}",
                                            provenance="student_confirmed", source=item.element))
        given = [item for item in integrity.expressions if item.role == "given" and item.status == "parsed" and item.canonical]
        models = [item.canonical for item in given if " = " in item.canonical and not any(op in item.canonical for op in "<>")]
        constraints = [item.canonical for item in given if any(op in item.canonical for op in ("<", ">", "!="))]
    else:
        models, constraints = [], []
    text = analysis.question_text or ""
    try:
        return ScientificProblemModel(
            subject=subject, source_revision=analysis.revision if integrity is not None else None,
            narrative=segments(text[:8192]), observations=observations[:128], known=quantities(text),
            candidate_models=models[:16], constraints=constraints[:32], target=target,
            uncertainties=[item.id for item in integrity.uncertainties][:16] if integrity is not None else [],
        )
    except ValidationError:
        return None

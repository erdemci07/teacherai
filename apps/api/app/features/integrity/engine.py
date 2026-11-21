"""Belirlenimci soru bütünlüğü kararları (TA-003).

Karar sırası: kaynak durumu → alan yeteneği → kaynak seçimi → ifade yapısı → seçenek bütünlüğü →
amaç ve olumsuzluk → sağlayıcı belirsizlikleri → önemlilik → (gerekirse) tek hedefli yeniden okuma →
(gerekirse) öğrenci açıklaması. Güven puanı karar girdisi değildir. Önemsiz belirsizlik çözümü
durdurmaz; desteklenmeyen gösterim soruyu geçersiz kılmaz; kritik belirsizlik tahminle kapatılmaz.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import ValidationError

from ..education.domain import Subject, canonical_subject, capabilities
from ..education.source import (
    Alternative,
    AnswerChoice,
    ClarificationRecord,
    Correction,
    IntegrityCheck,
    IntegrityReport,
    NormalizationNote,
    QuestionIntent,
    SourceExpression,
    SourceRegion,
    SourceUncertainty,
)
from .expression import (
    Mixed,
    ParseResult,
    Rel,
    _children,
    equivalent_readings,
    parse,
    symbols,
)
from .language import casefold_tr, detect_intent, parse_choices
from .materiality import classify as classify_legacy

MAX_PROVIDER_UNCERTAINTIES = 8
MAX_LEGACY_UNCERTAINTIES = 6
MAX_ALTERNATIVES = 3
MAX_RECHECK_ITEMS = 3
# Görsel yeniden okumayla çözülemeyecek kategoriler: gösterim kuralı veya kaynak seçimi.
NOT_RECHECKABLE = {"decimal", "source_selection"}

_LEGACY_CATEGORIES = (
    (("kök", "karekök", "radikal"), "radical_scope"),
    (("üs", "kuvvet"), "exponent_scope"),
    (("kesir", "pay", "payda"), "fraction_scope"),
    (("eksi", "işaret", "negatif"), "sign"),
    (("ondalık", "virgül"), "decimal"),
    (("seçenek", "şık"), "answer_choice"),
    (("şekil", "çizim"), "diagram"),
    (("grafik",), "graph"),
    (("tablo",), "table"),
    (("birim",), "unit"),
    (("değil", "olumsuz"), "negation"),
    (("parantez",), "grouping"),
    (("alt simge", "indis"), "subscript"),
)


@dataclass(frozen=True)
class EvaluationState:
    """Önceki revizyondan taşınan sunucu durumu."""

    revision: int = 1
    origin: str = "vision"
    recheck_limit: int = 0
    rechecks_used: int = 0
    image: tuple[str, ...] = ()
    corrections: tuple[Correction, ...] = ()
    clarifications: tuple[ClarificationRecord, ...] = ()
    prior: IntegrityReport | None = None


def _element_content(analysis, element: str, choices: list[AnswerChoice], statements: list[str]) -> str | None:
    if element == "stem":
        return analysis.question_text or None
    if element == "visual":
        visual = analysis.visual_elements
        parts = list(visual.relevant_visual_facts) + list(visual.relationships)
        return "\n".join(parts) if parts else None
    kind, _, key = element.partition(":")
    if kind == "expression" and key.isdigit():
        index = int(key)
        return analysis.mathematical_expressions[index] if index < len(analysis.mathematical_expressions) else None
    if kind == "choice":
        found = [choice for choice in choices if choice.label == key.upper()]
        return found[0].content if len(found) == 1 else None
    if kind == "statement":
        for item in statements:
            if re.match(rf"^\s*{key}\s*[.)]", item):
                return item
    return None


def _check(checks: list[IntegrityCheck], code: str, impact: str = "noncritical", element: str | None = None):
    item = IntegrityCheck(code=code, impact=impact, element=element)  # type: ignore[arg-type]
    if item not in checks and len(checks) < 96:
        checks.append(item)


def _legacy_category(text: str) -> str:
    folded = text.replace("İ", "i").replace("I", "ı").lower()
    for words, category in _LEGACY_CATEGORIES:
        if any(word in folded for word in words):
            return category
    return "text"


def _region(proposal, index) -> SourceRegion | None:
    if index is None or not (0 <= index < len(proposal.regions)):
        return None
    item = proposal.regions[index]
    try:
        return SourceRegion(kind=item.kind, x0=item.x0, y0=item.y0, x1=item.x1, y1=item.y1)
    except (ValidationError, ValueError):
        return None


def _role(index: int, result: ParseResult, raw: str, choices: list[AnswerChoice], statements: list[str], intent: QuestionIntent) -> str:
    canonical = result.canonical() if result.parsed else None
    compact = re.sub(r"\s+", "", raw)
    for choice in choices:
        if choice.content and (re.sub(r"\s+", "", choice.content) == compact or (canonical and choice.canonical == canonical)):
            return "answer_choice"
    for statement in statements:
        if compact and compact in re.sub(r"\s+", "", statement):
            return "premise"
    if result.parsed and isinstance(result.tree, Rel):
        return "given"
    if result.parsed and intent.kind in {"find_value", "simplify", "compare", "find_minimum", "find_maximum"}:
        return "requested"
    return "given" if result.parsed else "unknown"


def _apply_fragment(content: str, recognized: str, replacement: str) -> str | None:
    return content.replace(recognized, replacement, 1) if content.count(recognized) == 1 else None


def _alternatives(element: str | None, recognized: str | None, raw_alternatives: list[str], content: str | None,
                  origin: str, prefix: str) -> tuple[list[Alternative], int]:
    """Uygulanabilir ve anlamı farklı alternatifleri döndürür; (liste, eşdeğer olduğu için atılan sayı)."""
    if not (element and recognized and content) or content.count(recognized) != 1:
        return [], 0
    kept: list[Alternative] = []
    dropped = 0
    original = parse(content) if element.startswith(("expression", "choice")) else None
    seen = {recognized.strip()}
    for raw in raw_alternatives:
        text = raw.strip()[:400]
        if not text or text in seen:
            continue
        seen.add(text)
        candidate = _apply_fragment(content, recognized, text)
        if candidate is None:
            continue
        latex = None
        if original is not None:
            reading = parse(candidate)
            if equivalent_readings(original, reading):
                dropped += 1
                continue
            latex = reading.latex() if reading.parsed else None
        kept.append(Alternative(id=f"{prefix}_{len(kept) + 1}", text=text, latex=latex[:400] if latex else None, origin=origin))  # type: ignore[arg-type]
        if len(kept) >= MAX_ALTERNATIVES:
            break
    return kept, dropped


def _overlay(uncertainty: SourceUncertainty, prior: IntegrityReport | None) -> SourceUncertainty:
    if prior is None:
        return uncertainty
    for previous in prior.uncertainties:
        if previous.id != uncertainty.id:
            continue
        update: dict = {}
        if previous.resolution != "unresolved":
            update["resolution"] = previous.resolution
        extra = [alt for alt in previous.alternatives if alt.origin == "vision_recheck" and all(alt.text != own.text for own in uncertainty.alternatives)]
        if extra and uncertainty.resolution == "unresolved" and previous.resolution == "unresolved":
            update["alternatives"] = (uncertainty.alternatives + extra)[:4]
            if uncertainty.recognized is None and previous.recognized is not None:
                update["recognized"] = previous.recognized
                update["element"] = previous.element
        evidence = list(dict.fromkeys(uncertainty.evidence + previous.evidence))[:8]
        update["evidence"] = evidence
        return uncertainty.model_copy(update=update)
    return uncertainty


def evaluate(analysis, state: EvaluationState = EvaluationState()) -> IntegrityReport:
    """Mevcut kabul edilmiş okuma için bütünlük kararını üretir. Yan etkisizdir."""
    checks: list[IntegrityCheck] = []
    uncertainties: list[SourceUncertainty] = []
    proposal = getattr(analysis, "source", None)
    statements = list(proposal.statements[:6]) if proposal else []

    subject = canonical_subject(analysis.subject or "")
    subject_origin = "canonical_label" if subject != Subject.UNKNOWN else "unknown"
    if subject == Subject.UNKNOWN and analysis.is_valid_question and analysis.image_status == "valid_math_question":
        subject, subject_origin = Subject.MATHEMATICS, "vision_math_gate"

    choice_evidence = parse_choices(list(analysis.answer_choices))
    choices = choice_evidence.choices
    intent_evidence = detect_intent(analysis.question_text or "", choices, statements)
    intent = intent_evidence.intent

    def report(decision: str, recovery: str, expressions=(), extra_checks=()) -> IntegrityReport:
        for code, impact in extra_checks:
            _check(checks, code, impact)
        return IntegrityReport(
            revision=state.revision, revision_origin=state.origin, decision=decision, recovery=recovery,  # type: ignore[arg-type]
            subject=subject, subject_origin=subject_origin, intent=intent, expressions=list(expressions),  # type: ignore[arg-type]
            choices=choices, uncertainties=uncertainties[:16], checks=checks, image=list(state.image)[:12],  # type: ignore[arg-type]
            rechecks_used=state.rechecks_used, recheck_limit=state.recheck_limit,
            corrections=list(state.corrections), clarifications=list(state.clarifications),
        )

    # 1. Kaynağın kendisi (ölümcül sorunlar)
    if analysis.image_status == "unreadable":
        return report("unreadable", "retake", extra_checks=[("unreadable_source", "fatal")])
    if analysis.image_status == "incomplete_question":
        return report("incomplete", "retake", extra_checks=[("incomplete_source", "fatal")])
    if not analysis.is_valid_question or analysis.image_status != "valid_math_question":
        return report("no_question", "retake", extra_checks=[("not_a_question", "fatal")])
    if not capabilities(subject).generation:
        return report("unsupported_subject", "none", extra_checks=[("unsupported_subject", "fatal")])
    if not (analysis.question_text or "").strip() and not analysis.mathematical_expressions:
        return report("incomplete", "retake", extra_checks=[("missing_question_text", "fatal")])

    # 2. Kaynak seçimi
    if proposal and proposal.question_count > 1:
        if proposal.target_question_clear:
            _check(checks, "multiple_questions")
        else:
            uncertainties.append(SourceUncertainty(
                id="d_source_selection", category="source_selection", impact="material", resolution="unresolved",
                origin="vision", evidence=["multiple_questions", "target_question_unclear"],
            ))

    # 3. İfadeler
    expressions: list[SourceExpression] = []
    seen_canonical: dict[str, int] = {}
    for index, raw in enumerate(analysis.mathematical_expressions[:64]):
        source = raw[:400] if raw else "?"
        result = parse(raw) if raw else ParseResult(raw or "", "invalid", reason="empty")
        role = _role(index, result, raw or "", choices, statements, intent)
        notes = [NormalizationNote(rule=note.rule, original=note.original.strip()[:256] or "space",  # type: ignore[arg-type]
                                   normalized=note.normalized.strip()[:256] or "space")
                 for note in result.notes][:16]
        canonical = result.canonical() if result.parsed else None
        latex = result.latex() if result.parsed else None
        if canonical and len(canonical) > 400 or latex and len(latex) > 400:
            result = ParseResult(result.source, "unsupported", reason="display_budget")
            canonical = latex = None
        expressions.append(SourceExpression(
            id=f"expr_{index + 1}", index=index, role=role, source=source, status=result.status,  # type: ignore[arg-type]
            canonical=canonical, latex=latex, reason=result.reason, normalizations=notes,
        ))
        element = f"expression:{index}"
        if notes:
            _check(checks, "decimal_comma_resolved" if any(n.rule == "decimal_comma" for n in notes) else "normalized_notation", element=element)
        if result.parsed and _contains_mixed(result.tree):
            _check(checks, "mixed_number_convention", element=element)
        if canonical:
            if canonical in seen_canonical:
                _check(checks, "duplicate_expression", element=element)
            seen_canonical.setdefault(canonical, index)
        if result.status == "unsupported":
            _check(checks, "unsupported_notation", element=element)
        elif result.status == "invalid":
            category = {"fraction_operand_missing": "fraction_scope", "radicand_missing": "radical_scope",
                        "exponent_missing": "exponent_scope"}.get(result.reason or "", "grouping")
            uncertainties.append(SourceUncertainty(
                id=f"d_structure_{index}", category=category, element=element, recognized=source, impact="material",  # type: ignore[arg-type]
                resolution="unresolved", origin="deterministic", evidence=["invalid_structure"], note=(result.reason or "")[:256] or None,
            ))
        if result.ambiguity is not None:
            category = result.ambiguity.category
            fragment = _ambiguous_fragment(raw, result)
            alternatives = []
            if fragment:
                for position, reading in enumerate(result.ambiguity.readings, start=1):
                    candidate = _apply_fragment(raw, fragment, reading)
                    parsed_candidate = parse(candidate) if candidate else None
                    alternatives.append(Alternative(
                        id=f"d_{category}_{index}_{position}", text=reading,
                        latex=_decimal_display(reading, position) if category == "decimal" else (parsed_candidate.latex()[:400] if parsed_candidate and parsed_candidate.parsed else None),
                        origin="deterministic",
                    ))
            uncertainties.append(SourceUncertainty(
                id=f"d_{category}_{index}", category=category, element=element if fragment else None,  # type: ignore[arg-type]
                recognized=fragment if fragment else None, alternatives=alternatives if fragment else [],
                impact="material", resolution="unresolved", origin="deterministic",
                evidence=["decimal_ambiguity" if category == "decimal" else "latex_exponent_scope"],
            ))

    # 4. Seçenekler (etki soru amacına bağlıdır)
    dependent = intent.choice_dependent
    if choices:
        if choice_evidence.duplicate_labels:
            _check(checks, "duplicate_choice_labels", "material")
            uncertainties.append(SourceUncertainty(
                id="d_choice_labels", category="answer_choice", impact="material", resolution="unresolved",
                origin="deterministic", evidence=["duplicate_choice_labels"],
            ))
        if choice_evidence.missing_labels:
            _check(checks, "missing_choice_label", "material" if dependent else "noncritical")
            if dependent:
                uncertainties.append(SourceUncertainty(
                    id="d_choice_missing", category="answer_choice", impact="material", resolution="unresolved",
                    origin="deterministic", evidence=["missing_choice_label"],
                ))
        if choice_evidence.unlabeled:
            _check(checks, "unlabeled_choices", "material" if dependent else "noncritical")
        if len(choices) == 1:
            _check(checks, "single_choice", "material" if dependent else "noncritical")
            if dependent:
                uncertainties.append(SourceUncertainty(
                    id="d_choice_single", category="answer_choice", impact="material", resolution="unresolved",
                    origin="deterministic", evidence=["single_choice"],
                ))
        if choice_evidence.equivalent_values:
            _check(checks, "equivalent_choice_values")
        for label in choice_evidence.invalid:
            _check(checks, "invalid_structure", "material" if dependent else "noncritical",
                   element=f"choice:{label}" if label.isalpha() else None)
            if dependent:
                uncertainties.append(SourceUncertainty(
                    id=f"d_choice_structure_{label}", category="answer_choice",
                    element=f"choice:{label}" if label.isalpha() else None, impact="material", resolution="unresolved",
                    origin="deterministic", evidence=["invalid_structure"],
                ))
        referenced = {ref for choice in choices for ref in choice.statement_refs}
        if referenced and not referenced.issubset(set(intent.statement_labels)):
            _check(checks, "missing_statements", "material")
            uncertainties.append(SourceUncertainty(
                id="d_statements_missing", category="text", element="stem", impact="material", resolution="unresolved",
                origin="deterministic", evidence=["missing_statements"],
            ))
    if intent_evidence.duplicate_statements:
        _check(checks, "duplicate_statement_labels", "material")
        uncertainties.append(SourceUncertainty(
            id="d_statement_labels", category="text", element="stem", impact="material", resolution="unresolved",
            origin="deterministic", evidence=["duplicate_statement_labels"],
        ))

    # 5. Amaç ve olumsuzluk
    if any(marker.category == "negation" or marker.marker in {"yanlıştır", "yanlış olan", "olamaz"} for marker in intent.markers):
        _check(checks, "negation_present", element="stem")
    if intent_evidence.polarity_conflict:
        uncertainties.append(SourceUncertainty(
            id="d_polarity", category="negation", element="stem", impact="material", resolution="unresolved",
            origin="deterministic", evidence=["polarity_conflict"],
        ))

    # 6. Sağlayıcı belirsizlikleri
    structured = list(proposal.uncertainties[:MAX_PROVIDER_UNCERTAINTIES]) if proposal else []
    for index, item in enumerate(structured):
        element = item.element.strip()
        content = _element_content(analysis, element, choices, statements) if element else None
        if content is None:
            element = None
        recognized = item.recognized.strip()[:400] or None
        alternatives, dropped = _alternatives(element, recognized, item.alternatives, content, "vision", f"u{index + 1}")
        if item.alternatives and not alternatives and not dropped:
            _check(checks, "alternative_not_applicable", element=element)
        region = _region(proposal, item.region_index)
        if item.region_index is not None and region is None:
            _check(checks, "invalid_region_omitted")
        evidence = []
        if dropped and not alternatives:
            impact, resolution = "noncritical", "resolved_locally"
            evidence.append("equivalent_alternatives")
        elif item.affects_answer:
            impact, resolution = "material", "unresolved"
            evidence.append("provider_uncertainty_material")
        else:
            impact, resolution = "noncritical", "unresolved"
            evidence.append("provider_uncertainty_noncritical")
        usable = element is not None and recognized is not None and content is not None and content.count(recognized) == 1
        uncertainties.append(SourceUncertainty(
            id=f"u{index + 1}", category=item.category, element=element if usable else (element or None),
            recognized=recognized if usable else None, alternatives=alternatives if usable else [],
            impact=impact, resolution=resolution, origin="vision", evidence=evidence, region=region,  # type: ignore[arg-type]
        ))

    # 7. Eski serbest metin belirsizlikleri (TA-004 önemlilik köprüsü). Şüphe ifadesi, kategori ve kaynakta
    # ilgili yapının bulunması birlikte gerekir; anahtar kelime tek başına engel değildir. Yapılandırılmış
    # bir belirsizlikle aynı kategori/öğeye düşen not yinelenmez. TA-003 öncesi kayıtlarda (``legacy``) not
    # önemsiz kalır; görsel artık mevcut olmadığından yeni engel oluşturulmaz.
    for index, text in enumerate(analysis.ocr_uncertainties[:MAX_LEGACY_UNCERTAINTIES]):
        if not text.strip():
            continue
        finding = classify_legacy(text, analysis, intent)
        duplicate = any(item.origin in {"vision", "deterministic"} and item.category == finding.category
                        and (finding.element is None or item.element in (None, finding.element)) for item in uncertainties)
        if duplicate and finding.level != "harmless":
            _check(checks, "legacy_uncertainty_merged", element=finding.element)
            continue
        material = finding.level == "material" and state.origin != "legacy"
        evidence = ["legacy_uncertainty", {"material": "legacy_uncertainty_material", "harmless": "legacy_uncertainty_formatting",
                                           "nonconsequential": "legacy_uncertainty_context_absent",
                                           "insufficient": "legacy_uncertainty_unclassified"}[finding.level]]
        category = finding.category if finding.category != "text" else _legacy_category(text)
        uncertainties.append(SourceUncertainty(
            id=f"l{index + 1}", category=category, element=finding.element if material else None,  # type: ignore[arg-type]
            recognized=finding.recognized if material else None, impact="material" if material else "noncritical",
            resolution="unresolved", origin="legacy_text", evidence=evidence, note=text.strip()[:256],  # type: ignore[arg-type]
        ))

    # 8. Görsel bağlam (TA-004): zorunlu görselin olguları eksikse önce metnin yeterliliğine bakılır.
    visual = analysis.visual_elements
    if visual.visual_relevance == "essential" and not (visual.relevant_visual_facts or visual.relationships or visual.description):
        _check(checks, "essential_visual_without_facts", element="visual")
        if text_suffices_without_visual(analysis, expressions):
            _check(checks, "essential_visual_text_sufficient", element="visual")
        elif state.origin != "legacy":
            uncertainties.append(SourceUncertainty(
                id="d_visual_missing", category="diagram", element="visual", impact="material", resolution="unresolved",
                origin="deterministic", evidence=["essential_visual_without_facts", "essential_visual_insufficient"],
            ))

    uncertainties[:] = [_overlay(item, state.prior) for item in uncertainties][:16]
    for item in uncertainties:
        if item.resolution in {"resolved_by_student", "confirmed_by_recheck", "resolved_locally"}:
            code = {"resolved_by_student": "student_selected", "confirmed_by_recheck": "recheck_confirmed",
                    "resolved_locally": "equivalent_alternatives"}[item.resolution]
            _check(checks, code, element=item.element)
        if item.resolution == "rejected_by_student":
            _check(checks, "student_rejected", "material", element=item.element)

    decision, recovery = _decide(uncertainties, checks, state)
    if decision in {"ready", "ready_with_noncritical_uncertainty"} and not checks and not uncertainties:
        _check(checks, "clean")
    return report(decision, recovery, expressions)


def _decide(uncertainties: list[SourceUncertainty], checks: list[IntegrityCheck], state: EvaluationState) -> tuple[str, str]:
    if any(item.resolution == "rejected_by_student" for item in uncertainties):
        return "retake_required", "retake"
    pending = [item for item in uncertainties if item.impact != "noncritical" and item.resolution == "unresolved"]
    if pending:
        recheckable = [item for item in pending if item.category not in NOT_RECHECKABLE]
        if recheckable and state.rechecks_used < state.recheck_limit:
            return "targeted_recheck", "none"
        if any(item.category == "source_selection" for item in pending):
            return "clarification_required", "crop"
        if all(item.alternatives for item in pending):
            return "clarification_required", "choose_alternative"
        return "retake_required", "retake"
    if uncertainties or any(check.code != "clean" for check in checks):
        return "ready_with_noncritical_uncertainty", "none"
    return "ready", "none"


_VISUAL_REFERENCE = re.compile(r"şekil|şekle|grafi|tablo|görsel|diyagram|çizim|yukarıda|aşağıda verilen")


_VISUAL_TARGET = re.compile(
    r"\b(?:grafik(?:ten|lerden|lere göre)|grafiğe göre|tablo(?:dan|ya göre))\b"
    r"|\b(?:kırmızı|mavi|taralı|işaretli)\s+(?:[a-zçğıöşü]+\s+){0,2}(?:yay|kiriş|eğri|bölge|parça|doğru)\w*"
)


def text_suffices_without_visual(analysis, expressions: list[SourceExpression]) -> bool:
    """Zorunlu görselin olguları yokken metin problemi tek başına tanımlıyor mu? (TA-004)

    Metinde verilen bir ilişki (denklem veya eşitsizlik) varsa bilgi metindedir. Metin görsele atıf
    yapmıyor ve sayısal veri içeriyorsa da yeterli sayılır. Metin veriyi görselden istiyorsa yeterli değildir.
    """
    text = casefold_tr(analysis.question_text or "")
    # Kaynakta başka bir eşitlik bulunması, açıkça görselden istenen ilişkiyi sağlamaz.
    if _VISUAL_TARGET.search(text):
        return False
    given = [item for item in expressions if item.role == "given" and item.status == "parsed" and item.canonical
             and any(op in item.canonical for op in ("=", "<", ">"))]
    if given:
        return True
    return not _VISUAL_REFERENCE.search(text) and bool(re.search(r"\d", text))


def visual_facts_from_recheck(items: list[SourceUncertainty], readings: dict[int, tuple[bool, str]]) -> list[str]:
    """Eksik zorunlu görsel için hedefli okumanın verdiği olgular. Tek okumadır; doğrulama sayılmaz."""
    for position, item in enumerate(items, start=1):
        if item.id == "d_visual_missing":
            legible, reading = readings.get(position, (False, ""))
            reading = reading.strip()[:400]
            if legible and reading:
                return [reading]
    return []


def _contains_mixed(node) -> bool:
    if isinstance(node, Mixed):
        return True
    return any(_contains_mixed(child) for child in _children(node))


def _ambiguous_fragment(raw: str, result: ParseResult) -> str | None:
    if result.ambiguity is None:
        return None
    if result.ambiguity.category == "decimal":
        whole, fraction = result.ambiguity.readings[0].split(".")
        for candidate in (f"{whole},{fraction}", f"{whole}{{,}}{fraction}"):
            if raw.count(candidate) == 1:
                return candidate
        return None
    full = result.ambiguity.readings[1][2:-1]
    for candidate in (f"^{full}",):
        if raw.count(candidate) == 1:
            return candidate
    return None


def _decimal_display(reading: str, position: int) -> str:
    if position == 1:
        whole, fraction = reading.split(".")
        return f"{whole}{{,}}{fraction.rstrip('0') or '0'}"
    return reading


# --------------------------------------------------------------------------- yeniden okuma


def recheck_items(report: IntegrityReport) -> list[SourceUncertainty]:
    return [item for item in report.pending() if item.category not in NOT_RECHECKABLE][:MAX_RECHECK_ITEMS]


def apply_recheck(analysis, report: IntegrityReport, items: list[SourceUncertainty], readings: dict[int, tuple[bool, str]],
                  state: EvaluationState) -> IntegrityReport:
    """Yeniden okumayı ilk okumayla karşılaştırır. Son yanıt kendiliğinden doğru kabul edilmez.

    - Aynı ya da anlamca eşdeğer okuma: ilk okuma teyit edilmiş sayılır (doğrulama değil, iki okumanın uyumu).
    - Farklı okuma: iki okuma da öğrenciye seçenek olarak sunulur.
    - Okunamadı: belirsizlik açık kalır.
    """
    choices = report.choices
    statements = list(analysis.source.statements[:6]) if getattr(analysis, "source", None) else []
    updated = {item.id: item for item in report.uncertainties}
    for position, item in enumerate(items, start=1):
        legible, reading = readings.get(position, (False, ""))
        reading = reading.strip()[:400]
        current = updated[item.id]
        if not legible or not reading:
            updated[item.id] = current.model_copy(update={"evidence": _evidence(current, "recheck_illegible")})
            continue
        element = current.element
        recognized = current.recognized
        content = _element_content(analysis, element, choices, statements) if element else None
        if recognized is None and element and content and current.origin == "deterministic":
            recognized = content
        if recognized is None or content is None:
            updated[item.id] = current.model_copy(update={"evidence": _evidence(current, "recheck_illegible")})
            continue
        same = re.sub(r"\s+", "", reading) == re.sub(r"\s+", "", recognized)
        if same and current.origin == "deterministic":
            # Yapısal olarak geçersiz okuma ikinci kez aynı geldiyse çözülmüş sayılmaz.
            updated[item.id] = current.model_copy(update={"recognized": recognized, "evidence": _evidence(current, "recheck_confirmed")})
            continue
        equivalent = False
        if not same and element.startswith(("expression", "choice")):
            candidate = _apply_fragment(content, recognized, reading)
            if candidate is not None:
                equivalent = equivalent_readings(parse(content), parse(candidate)) and parse(content).parsed
        if (same or equivalent) and current.origin != "deterministic":
            updated[item.id] = current.model_copy(update={
                "resolution": "confirmed_by_recheck",
                "evidence": _evidence(current, "recheck_confirmed" if same else "recheck_equivalent"),
            })
            continue
        alternatives, _ = _alternatives(element, recognized, [reading], content, "vision_recheck", f"{item.id}_r")
        merged = (current.alternatives + [alt for alt in alternatives if all(alt.text != own.text for own in current.alternatives)])[:4]
        updated[item.id] = current.model_copy(update={
            "recognized": recognized, "alternatives": merged, "evidence": _evidence(current, "recheck_disagreement"),
        })
    prior = report.model_copy(update={"uncertainties": list(updated.values())})
    next_state = EvaluationState(
        revision=state.revision, origin="vision_recheck", recheck_limit=state.recheck_limit,
        rechecks_used=state.rechecks_used + 1, image=state.image, corrections=state.corrections,
        clarifications=state.clarifications, prior=prior,
    )
    return evaluate(analysis, next_state)


def mark_recheck_unavailable(analysis, report: IntegrityReport, state: EvaluationState, reason: str) -> IntegrityReport:
    """Yeniden okuma yapılamadıysa (kapalı, bütçe yok, sağlayıcı hatası) bunu kanıt olarak kaydeder."""
    pending = {item.id for item in recheck_items(report)}
    uncertainties = [
        item.model_copy(update={"evidence": _evidence(item, reason)}) if item.id in pending else item
        for item in report.uncertainties
    ]
    prior = report.model_copy(update={"uncertainties": uncertainties})
    next_state = EvaluationState(
        revision=state.revision, origin=state.origin, recheck_limit=state.rechecks_used, rechecks_used=state.rechecks_used,
        image=state.image, corrections=state.corrections, clarifications=state.clarifications, prior=prior,
    )
    return evaluate(analysis, next_state)


def _evidence(item: SourceUncertainty, code: str) -> list:
    return list(dict.fromkeys(item.evidence + [code]))[:8]


# --------------------------------------------------------------------------- öğrenci açıklaması


class ClarificationError(ValueError):
    pass


def apply_clarification(analysis, uncertainty_id: str, selection: str):
    """Öğrencinin seçimini yeni revizyona işler. Yalnızca belirlenimci denetim yeniden çalışır.

    Döner: güncellenmiş analiz. Seçim, öğrenci onayıdır; bağımsız doğrulama sayılmaz.
    """
    report: IntegrityReport | None = analysis.integrity
    if report is None or report.decision != "clarification_required":
        raise ClarificationError("not_pending")
    target = next((item for item in report.pending() if item.id == uncertainty_id), None)
    if target is None:
        raise ClarificationError("unknown_uncertainty")
    record = ClarificationRecord(uncertainty_id=uncertainty_id, selection=selection, from_revision=report.revision)
    updates: dict = {}
    corrections = list(report.corrections)
    if selection == "none":
        resolution = "rejected_by_student"
    elif selection == "recognized":
        resolution = "resolved_by_student"
    else:
        alternative = next((alt for alt in target.alternatives if alt.id == selection), None)
        if alternative is None or target.element is None or target.recognized is None:
            raise ClarificationError("unknown_alternative")
        updates = _replace(analysis, report, target.element, target.recognized, alternative.text)
        if updates is None:
            raise ClarificationError("not_applicable")
        corrections.append(Correction(element=target.element, original=target.recognized, corrected=alternative.text,
                                      uncertainty_id=target.id, from_revision=report.revision))
        resolution = "resolved_by_student"
    resolved = [item.model_copy(update={"resolution": resolution}) if item.id == uncertainty_id else item for item in report.uncertainties]
    candidate = analysis.model_copy(update={**updates, "revision": report.revision + 1})
    state = EvaluationState(
        revision=report.revision + 1, origin="student_clarification", recheck_limit=report.rechecks_used,
        rechecks_used=report.rechecks_used, image=tuple(report.image), corrections=tuple(corrections[-16:]),
        clarifications=tuple((list(report.clarifications) + [record])[-16:]),
        prior=report.model_copy(update={"uncertainties": resolved}),
    )
    return candidate.model_copy(update={"integrity": evaluate(candidate, state)})


def _replace(analysis, report: IntegrityReport, element: str, recognized: str, replacement: str) -> dict | None:
    kind, _, key = element.partition(":")
    if kind == "expression":
        index = int(key)
        expressions = list(analysis.mathematical_expressions)
        if index >= len(expressions):
            return None
        updated = _apply_fragment(expressions[index], recognized, replacement)
        if updated is None:
            return None
        expressions[index] = updated
        result: dict = {"mathematical_expressions": expressions}
        # Aynı parça soru metninde tek kez geçiyorsa oradaki okuma da eşitlenir; aksi halde düzeltme
        # kaydı ders bağlamına ayrıca taşınır.
        if analysis.question_text and analysis.question_text.count(recognized) == 1:
            result["question_text"] = analysis.question_text.replace(recognized, replacement, 1)
        return result
    if kind == "choice":
        choices = list(analysis.answer_choices)
        for index, raw in enumerate(choices):
            match = next((choice for choice in report.choices if choice.order == index), None)
            if match and match.label == key.upper():
                updated = _apply_fragment(raw, recognized, replacement)
                if updated is None:
                    return None
                choices[index] = updated
                return {"answer_choices": choices}
        return None
    if kind == "stem":
        updated = _apply_fragment(analysis.question_text or "", recognized, replacement)
        return {"question_text": updated} if updated is not None else None
    if kind == "visual":
        visual = analysis.visual_elements
        facts, relations = list(visual.relevant_visual_facts), list(visual.relationships)
        hits = [(name, index) for name, items in (("facts", facts), ("relations", relations))
                for index, item in enumerate(items) if recognized in item]
        if len(hits) != 1:
            return None
        name, index = hits[0]
        items = facts if name == "facts" else relations
        updated = _apply_fragment(items[index], recognized, replacement)
        if updated is None:
            return None
        items[index] = updated
        return {"visual_elements": visual.model_copy(update={"relevant_visual_facts": facts, "relationships": relations})}
    return None


def symbols_of(expression: SourceExpression) -> set[str]:
    result = parse(expression.source)
    return symbols(result.tree) if result.parsed else set()

"""Kaynak tutarlılığı ve kanıt denetimleri: etiket, sıra, deney, öncül (TA-004).

Bu denetimler *verilen kaynağın kendi içindeki tutarlılığını* sınar; evrensel bilimsel doğruluğu
kanıtlamaz. Bir modelin önerdiği organel etiketi işlevin doğrulandığı anlamına gelmez. Yalnızca
doğrudan kökenli (kaynak metin, görsel okuma, öğrenci onayı) ilişkiler kanıt sayılır; çıkarımlar
kendi başına kanıt değildir. Korelasyon nedensellik sayılmaz.
"""

from __future__ import annotations

import re
from collections import defaultdict
from fractions import Fraction

from ..education.science import DIRECT_PROVENANCE, ExperimentalModel, Premise, ScientificProblemModel
from ..education.source import AnswerChoice
from ..integrity.language import casefold_tr
from .formula import CheckOutcome, trend
from .units import NumberError, UnitError, parse_number, parse_unit


def _direct(relation) -> bool:
    return relation.provenance in DIRECT_PROVENANCE


# --------------------------------------------------------------------------- etiketler


def check_labels(model: ScientificProblemModel) -> CheckOutcome:
    """Etiket–yapı eşleşmeleri: bir yapıya iki farklı etiket veya bir etikete iki yapı çelişkidir."""
    entities = {item.id: item for item in model.entities}
    by_structure: dict[str, set[str]] = defaultdict(set)
    by_label: dict[tuple[str | None, str], set[str]] = defaultdict(set)
    unclear = []
    for relation in model.relations:
        if relation.type != "labeled_as" or not _direct(relation):
            continue
        label_entity = entities[relation.object]
        text = casefold_tr((label_entity.label or label_entity.id).strip())
        if not relation.direction_clear:
            unclear.append(relation.id)
            continue
        by_structure[relation.subject].add(text)
        by_label[(entities[relation.subject].figure, text)].add(relation.subject)
    for entity in model.entities:
        if entity.label and entity.id in by_structure and entity.provenance in DIRECT_PROVENANCE:
            by_structure[entity.id].add(casefold_tr(entity.label.strip()))
    conflicts = sorted(key for key, labels in by_structure.items() if len(labels) > 1)
    reused = sorted(label for (_, label), owners in by_label.items() if len(owners) > 1)
    if conflicts or reused:
        return CheckOutcome("failed", "conflicting_labels", details={"structures": conflicts, "labels": reused})
    if unclear:
        return CheckOutcome("unsupported", "label_association_unclear", details={"relations": sorted(unclear)})
    if not by_structure:
        return CheckOutcome("unsupported", "no_label_evidence")
    return CheckOutcome("passed", "labels_consistent", details={"structures": sorted(by_structure)})


def check_direction(model: ScientificProblemModel, relation_id: str) -> CheckOutcome:
    """Bir okun yönü ve anlamı kanıta dayanıyor mu? Belirsiz ok yönü tahmin edilmez.

    Aynı ok kuvvet, hareket, madde aktarımı veya neden-sonuç olabilir; anlam yalnızca kaynak metin veya
    öğrenci onayından gelir. Görsel okuma yalnızca okun varlığını ve yönünü gösterir.
    """
    relation = next((item for item in model.relations if item.id == relation_id), None)
    if relation is None or relation.type not in {"points_to", "acts_on"}:
        return CheckOutcome("unsupported", "unknown_relation")
    if not _direct(relation):
        return CheckOutcome("unsupported", "direction_not_observed")
    if not relation.direction_clear:
        return CheckOutcome("unsupported", "direction_unclear")
    if relation.interpretation_provenance not in {"source_text", "student_confirmed"}:
        return CheckOutcome("partially_checked", "direction_observed_meaning_open")
    return CheckOutcome("passed", "direction_and_meaning_grounded")


# --------------------------------------------------------------------------- süreç sırası


def _order(model: ScientificProblemModel) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for relation in model.relations:
        if relation.type == "precedes" and _direct(relation) and relation.direction_clear:
            graph[relation.subject].add(relation.object)
    return graph


def _reachable(graph: dict[str, set[str]], start: str) -> set[str]:
    seen: set[str] = set()
    stack = list(graph.get(start, ()))
    while stack:
        node = stack.pop()
        if node not in seen:
            seen.add(node)
            stack.extend(graph.get(node, ()))
    return seen


def check_sequence(model: ScientificProblemModel, claimed: list[str]) -> CheckOutcome:
    """İddia edilen sıra kaynaktaki açık ``precedes`` ilişkileriyle karşılaştırılır."""
    graph = _order(model)
    if any(node in _reachable(graph, node) for node in list(graph)):
        return CheckOutcome("failed", "source_order_cycle")
    known = {item.id for item in model.entities}
    if not set(claimed) <= known or len(set(claimed)) != len(claimed) or len(claimed) < 2:
        return CheckOutcome("unsupported", "unknown_stage")
    undecided = []
    for index, earlier in enumerate(claimed):
        for later in claimed[index + 1:]:
            if earlier in _reachable(graph, later):
                return CheckOutcome("failed", "order_contradicts_source", details={"pair": [earlier, later]})
            if later not in _reachable(graph, earlier):
                undecided.append([earlier, later])
    if undecided:
        return CheckOutcome("unsupported", "order_not_decidable", details={"pairs": undecided[:8]})
    return CheckOutcome("passed", "order_entailed_by_source")


# --------------------------------------------------------------------------- deney


def _condition(group, variable: str) -> str | None:
    return next((item.value for item in group.conditions if item.variable == variable), None)


def changed_variables(experiment: ExperimentalModel, groups: list[str]) -> set[str]:
    selected = [group for group in experiment.groups if group.id in groups]
    variables = {item.variable for group in selected for item in group.conditions}
    return {name for name in variables if len({_condition(group, name) for group in selected}) > 1}


def check_controlled_comparison(experiment: ExperimentalModel, groups: list[str]) -> CheckOutcome:
    """Karşılaştırmada bağımsız değişken dışında değişen bir koşul varsa karşılaştırma kontrollü değildir."""
    if len(groups) < 2:
        return CheckOutcome("unsupported", "insufficient_groups")
    changed = changed_variables(experiment, groups)
    extra = sorted(changed - set(experiment.independent))
    if extra:
        return CheckOutcome("failed", "confounded_comparison", details={"changed": extra})
    if not changed:
        return CheckOutcome("unsupported", "no_manipulated_variable")
    return CheckOutcome("passed", "controlled_comparison")


def _unit_dim(spec):
    if spec is None or spec.status != "parsed":
        return None
    try:
        return parse_unit(spec.original).dim
    except UnitError:
        return None


def check_claim(experiment: ExperimentalModel, claim_id: str) -> CheckOutcome:
    """Açık ölçümler iddia edilen eğilimi destekliyor mu? Nedensel iddia ayrıca kontrollü tasarım ister."""
    claim = next((item for item in experiment.claims if item.id == claim_id), None)
    if claim is None:
        return CheckOutcome("unsupported", "unknown_claim")
    variables = {item.id: item for item in experiment.variables}
    expected_dim = _unit_dim(variables[claim.y].unit)
    groups = [group for group in experiment.groups if not claim.groups or group.id in claim.groups]
    points: list[tuple[Fraction, Fraction]] = []
    values_by_group: dict[str, Fraction] = {}
    for measurement in experiment.measurements:
        if measurement.variable != claim.y or measurement.group not in {group.id for group in groups}:
            continue
        if expected_dim is not None and measurement.unit is not None and _unit_dim(measurement.unit) not in (None, expected_dim):
            return CheckOutcome("failed", "unit_mismatch")
        values_by_group[measurement.group] = parse_number(measurement.value)[0]
    used = [group for group in groups if group.id in values_by_group]
    if len(used) < 2:
        return CheckOutcome("unsupported", "insufficient_data")
    if claim.x is None:
        observed = "equal" if len(set(values_by_group.values())) == 1 else "differs"
        matches = observed == claim.relation or (claim.relation == "no_change" and observed == "equal")
        return CheckOutcome("passed" if matches else "failed", "data_supports_claim" if matches else "data_contradicts_claim")
    for group in used:
        raw = _condition(group, claim.x)
        if raw is None:
            return CheckOutcome("unsupported", "missing_condition")
        try:
            points.append((parse_number(raw)[0], values_by_group[group.id]))
        except NumberError:
            return CheckOutcome("unsupported", "non_numeric_condition")
    points.sort()
    if len({x for x, _ in points}) == 1:
        # Değişken hiç değiştirilmemiş: veriden bu değişkenin etkisi hakkında sonuç çıkarılamaz.
        return CheckOutcome("unsupported", "no_variation")
    if len({x for x, _ in points}) != len(points):
        return CheckOutcome("unsupported", "repeated_condition")
    observed = trend([y for _, y in points])
    if observed == "mixed":
        return CheckOutcome("failed" if claim.relation in {"increases", "decreases", "no_change"} else "unsupported",
                            "data_trend_mixed")
    if observed != claim.relation:
        return CheckOutcome("failed", "data_contradicts_claim", details={"observed": observed})
    if not claim.causal:
        return CheckOutcome("passed", "data_supports_trend", details={"observed": observed})
    if claim.x not in experiment.independent:
        return CheckOutcome("unsupported", "correlation_not_causation")
    controlled = check_controlled_comparison(experiment, [group.id for group in used])
    if controlled.outcome != "passed":
        return CheckOutcome("unsupported", controlled.reason, details=controlled.details)
    # Bu deneyin kapsamında tutarlı; evrensel bir yasa kanıtlanmış değildir.
    return CheckOutcome("partially_checked", "controlled_trend_consistent", details={"observed": observed})


# --------------------------------------------------------------------------- öncüller

_NOT_DEDUCIBLE = ("ulaşılamaz", "çıkarılamaz", "söylenemez", "varılamaz", "desteklenmez")
_FALSE = ("doğru değildir", "yanlıştır", "yanlış olan", "yanlış")
_SUPPORTED = ("ulaşılabilir", "çıkarılabilir", "söylenebilir", "varılabilir", "doğrudur", "doğru olan", "desteklenir")


def premise_polarity(question_text: str) -> str:
    """Soru kökünün kutupluluğu metinden silinmeden çıkarılır: supported | not_deducible | false | unknown."""
    ask = casefold_tr(question_text)
    ask = ask[: ask.rfind("?") + 1] if "?" in ask else ask
    ask = re.split(r"[.\n]", ask.rstrip("?"))[-1]
    if any(word in ask for word in _NOT_DEDUCIBLE):
        return "not_deducible"
    if any(word in ask for word in _FALSE):
        return "false"
    if any(word in ask for word in _SUPPORTED):
        return "supported"
    return "unknown"


# Kaynağın yetersiz olduğunu gösteren nedenler; denetleyicinin sınırı (ör. desteklenmeyen biçim) bu değildir.
_INSUFFICIENT_SOURCE = {"insufficient_data", "correlation_not_causation", "confounded_comparison", "order_not_decidable",
                        "no_manipulated_variable", "missing_condition", "no_variation"}


def premise_status(outcome: CheckOutcome) -> str:
    """Denetim sonucu → öncül durumu. Denetleyici değerlendiremediyse ``unevaluated`` kalır, uydurulmaz."""
    if outcome.outcome in {"passed", "partially_checked"}:
        return "supported"
    if outcome.outcome == "failed":
        return "contradicted"
    return "not_decidable" if outcome.reason in _INSUFFICIENT_SOURCE else "unevaluated"


def select_premises(premises: list[Premise], polarity: str) -> list[str] | None:
    """Kutupluluğa göre seçilmesi gereken öncüller; karar verilemiyorsa None (birleşim uydurulmaz)."""
    if polarity == "unknown" or not premises or any(item.status == "unevaluated" for item in premises):
        return None
    selected = []
    for item in premises:
        if polarity == "supported":
            chosen = item.status == "supported"
        elif polarity == "not_deducible":
            chosen = item.status in {"contradicted", "not_decidable", "true_not_deducible"}
        else:  # false
            if item.status in {"not_decidable"}:
                return None
            chosen = item.status == "contradicted"
        if chosen:
            selected.append(item.label)
    return selected


def match_combination(selected: list[str] | None, choices: list[AnswerChoice]) -> tuple[str, list[str]]:
    """(durum, etiketler). Yalnızca öncül kümesi tam eşleşen basılı etiketli seçenek kabul edilir."""
    if selected is None:
        return "unresolved", []
    wanted = set(selected)
    matches = [choice.label for choice in choices if choice.label and choice.kind == "statement_combination"
               and set(choice.statement_refs) == wanted]
    if len(matches) == 1:
        return "matched", matches  # type: ignore[return-value]
    return ("multiple" if matches else "no_match"), matches  # type: ignore[return-value]


# --------------------------------------------------------------------------- ölçüm verisi (TA-004)


def _series_by(experiment: ExperimentalModel, x: str, y: str) -> list[tuple[Fraction, Fraction]]:
    values = {m.group: parse_number(m.value)[0] for m in experiment.measurements if m.variable == y}
    points = []
    for group in experiment.groups:
        raw = _condition(group, x)
        if raw is not None and group.id in values:
            points.append((parse_number(raw)[0], values[group.id]))
    return sorted(points)


def check_measured_extremum(experiment: ExperimentalModel, x: str, y: str, at: str, kind: str = "max") -> CheckOutcome:
    """"Ölçülen en yüksek değer x = a'dadır" iddiası: yalnızca ölçülen noktalar arasında değerlendirilir."""
    points = _series_by(experiment, x, y)
    if len(points) < 2:
        return CheckOutcome("unsupported", "insufficient_data")
    best = max(value for _, value in points) if kind == "max" else min(value for _, value in points)
    winners = [position for position, value in points if value == best]
    if len(winners) != 1:
        return CheckOutcome("unsupported", "tied_extremum")
    return CheckOutcome("passed" if winners[0] == parse_number(at)[0] else "failed",
                        "measured_extremum_matches" if winners[0] == parse_number(at)[0] else "measured_extremum_differs")


def check_exact_optimum(experiment: ExperimentalModel, x: str, y: str, at: str) -> CheckOutcome:
    """"Optimum tam olarak a'dır" iddiası ayrık ölçümlerden çıkarılamaz (ölçülmeyen noktalar arasında olabilir)."""
    measured = check_measured_extremum(experiment, x, y, at)
    if measured.outcome == "failed":
        return CheckOutcome("failed", "measured_extremum_differs")
    return CheckOutcome("unsupported", "insufficient_data")


def check_measured_value(experiment: ExperimentalModel, group: str, y: str, relation: str, value: str) -> CheckOutcome:
    """Tek bir ölçümün açık değerle karşılaştırılması (ör. "70 °C'de etkinlik 0'dır")."""
    found = [parse_number(m.value)[0] for m in experiment.measurements if m.group == group and m.variable == y]
    if len(found) != 1:
        return CheckOutcome("unsupported", "insufficient_data")
    actual, expected = found[0], parse_number(value)[0]
    holds = {"equal": actual == expected, "greater": actual > expected, "less": actual < expected}.get(relation)
    if holds is None:
        return CheckOutcome("unsupported", "unknown_relation")
    return CheckOutcome("passed" if holds else "failed", "measurement_consistent" if holds else "measurement_contradicts")


def check_pair(experiment: ExperimentalModel, y: str, left: str, right: str, relation: str) -> CheckOutcome:
    """İki grubun ölçülen değerleri arasındaki ilişki (ör. büyük balık > küçük balık)."""
    values = {m.group: parse_number(m.value)[0] for m in experiment.measurements if m.variable == y}
    if left not in values or right not in values:
        return CheckOutcome("unsupported", "insufficient_data")
    holds = {"equal": values[left] == values[right], "greater": values[left] > values[right],
             "less": values[left] < values[right]}.get(relation)
    if holds is None:
        return CheckOutcome("unsupported", "unknown_relation")
    return CheckOutcome("passed" if holds else "failed", "measurement_consistent" if holds else "measurement_contradicts")


def check_constant_ratio(experiment: ExperimentalModel, x: str, y: str) -> CheckOutcome:
    """Ardışık ölçümler arasındaki oran sabit mi? Yaklaşık eşitlik "tam aynı" sayılmaz."""
    points = _series_by(experiment, x, y)
    if len(points) < 3 or any(value == 0 for _, value in points[:-1]):
        return CheckOutcome("unsupported", "insufficient_data")
    ratios = {b / a for (_, a), (_, b) in zip(points, points[1:])}
    return CheckOutcome("passed" if len(ratios) == 1 else "failed", "constant_ratio" if len(ratios) == 1 else "ratio_varies")


def proportional_prediction(experiment: ExperimentalModel, x: str, y: str, at: str, claim: str) -> CheckOutcome:
    """Ölçümler tam orantılıysa (y/x sabit) verilen noktadaki değer; geçerlilik aralığı kaynakta verilmelidir."""
    points = _series_by(experiment, x, y)
    if len(points) < 2 or any(position == 0 for position, _ in points):
        return CheckOutcome("unsupported", "insufficient_data")
    ratios = {value / position for position, value in points}
    if len(ratios) != 1:
        return CheckOutcome("unsupported", "not_proportional")
    predicted = next(iter(ratios)) * parse_number(at)[0]
    matches = predicted == parse_number(claim)[0]
    return CheckOutcome("passed" if matches else "failed", "proportional_prediction_matches" if matches else "proportional_prediction_differs")

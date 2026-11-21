"""Sorunun istediği hedefin belirlenimci tespiti (TA-004).

Bir denklemin çözümü her zaman istenen cevap değildir: ``x = 3`` verilip ``x + 2`` sorulduğunda cevap 5'tir.
Hedef; soru kökünün son soru cümlesindeki Türkçe kalıplardan, sorudaki "istenen" rollü ifadeden ve soru
amacından çıkarılır. Kalıp tabanlıdır, tam bir dil ayrıştırıcısı değildir. Hedef belirlenemezse
``unresolved`` döner ve seçenek otomatik seçilmez.
"""

from __future__ import annotations

import re

from ..education.reasoning import AnswerTarget
from ..integrity import expression as tree
from ..integrity.language import _last_question_sentence

_ROOT_WORDS = r"(?:(?:kök|çözüm|değer)(?:ler)?(?:i|in|inin)?|çözüm kümesinin elemanlar(?:ı|ının))"
_ROOT_SUM = re.compile(_ROOT_WORDS + r"\s+toplam")
_ROOT_PRODUCT = re.compile(_ROOT_WORDS + r"\s+çarpım")
_COUNT = re.compile(r"kaç\s+(?:tane|farklı|adet)|kaç\s+tanedir|sayısı\s+kaç")
_ASKED_FRAGMENT = re.compile(
    r"([0-9a-zA-Z+\-−*/^().\s²³√·×{}\\_|]{1,80}?)\s*(?:oranı|toplamı|farkı|çarpımı)?\s*(?:ifadesinin\s+(?:değeri|eşiti|sonucu)|değeri|kaçtır|kaç\s+olur|nedir|=\s*\?)"
)


def _raw_question_sentence(text: str) -> str:
    """Son soru cümlesi, harf büyüklüğü korunarak (``language._last_question_sentence`` ile aynı sınırlar)."""
    end = text.rfind("?")
    segment = text[: end + 1] if end >= 0 else text
    for separator in (".", "\n"):
        position = segment.rstrip("?").rfind(separator)
        if position > 0:
            segment = segment[position + 1:]
    return segment[-400:]


def _symbol_name(node: tree.Sym) -> str:
    return node.name + (f"_{node.sub}" if node.sub else "")


def _strip(node):
    while isinstance(node, tree.Group):
        node = node.arg
    return node


def _expression_kind(node) -> str:
    node = _strip(node)
    if isinstance(node, tree.Bin):
        if node.op == "+":
            return "sum"
        if node.op == "-":
            return "difference"
        if node.op == "*":
            return "product"
        if node.op == "/":
            return "ratio"
    if isinstance(node, tree.Frac):
        return "ratio"
    return "expression_value"


def _given_equations(integrity) -> list:
    if integrity is None:
        return []
    return [item for item in integrity.expressions if item.role == "given" and item.status == "parsed"
            and item.canonical and " = " in item.canonical and not any(op in item.canonical for op in ("<", ">", "!="))]


def _given_relations(integrity) -> list:
    if integrity is None:
        return []
    return [item for item in integrity.expressions if item.role == "given" and item.status == "parsed" and item.canonical
            and any(op in item.canonical for op in (" = ", "<", ">"))]


def _variables(items) -> set[str]:
    names: set[str] = set()
    for item in items:
        parsed = tree.parse(item.source)
        if parsed.parsed:
            names |= tree.symbols(parsed.tree)
    return names


def _requested_from_text(ask: str, variables: set[str]):
    """Soru cümlesinden "x + 2 kaçtır" gibi istenen ifadeyi sınırlı biçimde çıkarır."""
    for match in _ASKED_FRAGMENT.finditer(ask):
        fragment = match.group(1).strip(" ,.;:")
        fragment = re.sub(r"^.*?(?:göre|ise|için|olduğuna|olmak üzere)\s+", "", fragment)
        if not fragment or not re.search(r"[a-zA-Z]", fragment):
            continue
        parsed = tree.parse(fragment)
        if not parsed.parsed or isinstance(parsed.tree, tree.Rel):
            continue
        names = tree.symbols(parsed.tree)
        if names and (not variables or names <= variables):
            return parsed
    return None


def detect_target(question_text: str, integrity, visual_text: str = "") -> AnswerTarget:
    """Bütünlük raporu ve soru metninden hedefi çıkarır. Yan etkisizdir, sağlayıcı çağırmaz.

    ``visual_text`` görselden okunan olgulardır; yalnızca "h = ?" gibi açık bilinmeyen işareti için kullanılır.
    """
    text = question_text or ""
    ask = _last_question_sentence(text)
    intent = integrity.intent if integrity is not None else None
    kind = intent.kind if intent is not None else "unknown"
    equations = _given_equations(integrity)
    relations = _given_relations(integrity)
    variables = _variables(relations)
    single = next(iter(variables)) if len(variables) == 1 else None
    integer_only = "tam sayı" in ask or "tamsayı" in ask
    markers: list[str] = []

    def target(kind_: str, **values) -> AnswerTarget:
        return AnswerTarget(kind=kind_, origin="deterministic", markers=markers[:8], integer_only=integer_only, **values)  # type: ignore[arg-type]

    if kind in {"identify_true", "identify_false", "find_all_valid"}:
        markers.append(kind)
        if intent is not None and intent.statement_labels:
            return target("statement_combination")
        return target("proposition_truth")
    if kind == "compare":
        return target("comparison")
    if kind in {"interpret_graph", "interpret_table", "identify_shape"}:
        return target("scientific_interpretation")

    if _ROOT_SUM.search(ask):
        markers.append("kökler toplamı")
        return target("root_sum", variable=single)
    if _ROOT_PRODUCT.search(ask):
        markers.append("kökler çarpımı")
        return target("root_product", variable=single)
    if _COUNT.search(ask) and re.search(r"kök|çözüm|değer|sayı", ask):
        markers.append("kaç tane")
        return target("solution_count", variable=single)
    requested = [item for item in (integrity.expressions if integrity is not None else [])
                 if item.role == "requested" and item.status == "parsed" and item.canonical]
    extremum_expression = {}
    if len(requested) == 1:
        node = _strip(tree.parse(requested[0].source).tree) if tree.parse(requested[0].source).parsed else None
        if node is not None and not (isinstance(node, tree.Sym) and _symbol_name(node) in variables):
            extremum_expression = {"expression": requested[0].canonical, "latex": requested[0].latex,
                                   "source": f"expression:{requested[0].index}"}
    if re.search(r"en büyük|en çok|maksimum", ask):
        markers.append("en büyük")
        return target("maximum", variable=single, **extremum_expression)
    if re.search(r"en küçük|en az|minimum", ask):
        markers.append("en küçük")
        return target("minimum", variable=single, **extremum_expression)
    if "çözüm kümesi" in ask:
        markers.append("çözüm kümesi")
        return target("solution_set", variable=single)
    # "0–4 saniye aralığında" bir koşuldur; yalnızca aralığın kendisi sorulduğunda hedef aralıktır.
    if re.search(r"(?:çözüm\s+)?aralığı\s+(?:nedir|hangisidir|kaçtır)|hangi aralık", ask):
        return target("interval", variable=single)

    # Sembol adları büyük/küçük harfe duyarlıdır (A ile a farklıdır); ham soru cümlesi kullanılır.
    raw_ask = _raw_question_sentence(text)
    asked = re.search(r"(?<![a-zA-Zçğıöşü0-9_])([a-zA-Z])(?:_\{?([0-9a-z]{1,4})\}?)?\s*(?:kaçtır|değeri|nedir|kaç olur)", raw_ask)
    asked_name = (asked.group(1) + (f"_{asked.group(2)}" if asked.group(2) else "")) if asked else None
    if asked_name and variables and asked_name not in variables and not requested:
        # Sorulan sembol verilen modelde yok: değişkenin değeri istenen cevap sayılmaz.
        return AnswerTarget(kind="unresolved", origin="unresolved", markers=["sorulan sembol modelde yok"])
    if len(requested) == 1:
        parsed = tree.parse(requested[0].source)
        if parsed.parsed:
            node = _strip(parsed.tree)
            if isinstance(node, tree.Sym) and _symbol_name(node) in variables:
                return target("variable_value", variable=_symbol_name(node), source=f"expression:{requested[0].index}")
            markers.append("istenen ifade")
            return target(_expression_kind(parsed.tree), expression=requested[0].canonical, latex=requested[0].latex,
                          source=f"expression:{requested[0].index}", variable=single)
    fragment = _requested_from_text(raw_ask, variables)
    if fragment is not None:
        node = _strip(fragment.tree)
        if isinstance(node, tree.Sym) and (not variables or _symbol_name(node) in variables):
            return target("variable_value", variable=_symbol_name(node), source="stem")
        markers.append("soru cümlesindeki ifade")
        return target(_expression_kind(fragment.tree), expression=fragment.canonical()[:400],
                      latex=fragment.latex()[:400], source="stem", variable=single)
    if "oran" in ask:
        return AnswerTarget(kind="unresolved", origin="unresolved", markers=["oran"])

    # Kaynakta "h = ?" biçiminde açıkça işaretlenmiş bilinmeyen (metin veya şekil etiketi).
    marked = {m.group(1) for m in re.finditer(r"(?<![\w])([a-zA-Z])\s*=\s*\?", f"{text}\n{visual_text}")}
    if single is not None and len(equations) == 1 and (
        kind == "find_variable" or asked_name == single or marked == {single}
        or re.search(r"çözümler|kökler|kökü|çözümü|çözünüz|çözün", ask)
    ):
        if marked == {single}:
            markers.append(f"{single} = ?")
        return target("variable_value", variable=single)
    if single is not None and len(equations) == 1 and "?" not in text and not requested:
        # Soru cümlesi olmadan yalnızca denklem verilmişse örtük görev denklemi çözmektir (eski kayıtlar).
        return AnswerTarget(kind="variable_value", origin="legacy_default", variable=single)
    if kind == "unknown" and not equations:
        return target("textual_explanation") if not (integrity and integrity.choices) else AnswerTarget(
            kind="unresolved", origin="unresolved")
    return AnswerTarget(kind="unresolved", origin="unresolved")


def target_for(analysis, integrity=None) -> AnswerTarget:
    """Analizden hedef: soru metni, bütünlük raporu ve görsel olgular aynı kuralla kullanılır."""
    visual = analysis.visual_elements
    return detect_target(analysis.question_text or "", integrity if integrity is not None else analysis.integrity,
                         "\n".join(list(visual.relevant_visual_facts) + list(visual.relationships)))

"""TA-008/TA-008B matematik regresyon derlemi, yetenek matrisi ve yerel kıyaslama.

    python -m scripts.math_matrix              # vakaları koşturur, matris ve kıyaslama raporlarını yazar
    python -m scripts.math_matrix --check      # vakalar beklenenle uyuşmalı; matris raporu güncel olmalı (CI)

Sağlayıcı, ağ veya Firestore çağrısı yoktur. Vakalar sentetik ve özgündür; bağımsız değerlendirme setinden ayrıdır.
Kıyaslama süreleri yerel makinedir; bulut performansı iddiası değildir. SymPy bu betikte süreç içinde çalışır
(üretimde aynı modüller yalnız yalıtılmış MathAI işçisinde çalışır).
"""

from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path
from statistics import median
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "apps/api/tests/fixtures/mathematics/regression.json"
MATRIX = ROOT / "docs/mathematics/TA-008-capability-matrix.md"
# TA-008B: TA-008 ölçümü (TA-008-performance.md) karşılaştırma tabanı olarak korunur; yeni ölçüm ayrı dosyadadır.
BENCHMARK = ROOT / "docs/mathematics/TA-008B-corpus-benchmark.md"


def _text(value) -> str:
    from apps.api.app.features.mathematics import expr

    return expr.text(value)


def run_case(case: dict):
    from apps.api.app.features.education.mathematics import (
        GeometryModel,
        WordProblemModel,
    )
    from apps.api.app.features.mathematics import (
        alternatives,
        calculus,
        expr,
        functions,
        geometry,
        probability,
        sets,
        strategies,
        transforms,
        trig,
        word_problems,
    )

    kind, a = case["kind"], case["args"]
    if kind == "solve":
        solved = sets.solve_equation(a["latex"], domain=a.get("domain", "real"))
        return {"kind": solved.view.kind, "elements": solved.view.elements, "exclusions": solved.view.exclusions,
                "status": solved.status}
    if kind in {"inequality", "inequality_integers"}:
        solved = sets.solve_inequality(a["latex"])
        if kind == "inequality_integers":
            return sets.integer_count(solved.value)
        return {"intervals": [_interval(item) for item in solved.view.intervals], "exclusions": solved.view.exclusions}
    if kind == "transform":
        verdict = transforms.compare(a["previous"], a["current"], a["original"])
        return {"relation": verdict.relation, "hazard": verdict.hazard}
    if kind == "alternatives":
        paths = alternatives.quadratic(a["latex"])
        return {"strategies": [p.strategy for p in paths], "all_verified": all(p.verified for p in paths)}
    if kind == "function_graph":
        facts = functions.analyze(a["latex"])
        return {"discontinuities": [_text(item) for item in facts.discontinuities], "segments": len(facts.segments),
                "holes": [list(item) for item in facts.holes], "asymptotes": list(facts.asymptotes),
                "first_closed": facts.segments[0].start_closed if facts.segments else None}
    if kind == "inverse":
        value, reason = functions.inverse(a["latex"])
        return {"reason": reason, "inverse": _text(value) if value is not None else None}
    if kind == "compose":
        _, domain = functions.compose(a["outer"], a["inner"])
        return {"domain": str(domain)}
    if kind == "vertex":
        return [_text(item) if not isinstance(item, str) else item for item in functions.vertex(a["latex"])]
    if kind == "trig_interval":
        values, _ = trig.solve_in_interval(a["latex"], a["lower"], a["upper"], a["unit"])
        return [_text(item) for item in values or []]
    if kind == "trig_value":
        try:
            return _text(trig.exact_value(a["function"], a["angle"], a["unit"]))
        except expr.ExprError as exc:
            return {"error": str(exc)}
    if kind == "draw":
        space = probability.draw_space(a["items"], a["draws"], a["replacement"])
        _, color = a["event"].split(":")
        return str(probability.probability(space, lambda o: o.count(color) == 1))
    if kind == "draw_conditional":
        space = probability.draw_space(a["items"], a["draws"], a["replacement"])
        first, second = (lambda o: o[0] == "K"), (lambda o: o[1] == "K")
        return {"conditional": str(probability.conditional(space, second, first)),
                "independent": probability.independent(space, first, second)}
    if kind == "counting":
        return {"permutations": probability.permutations(a["n"], a["k"]), "combinations": probability.combinations(a["n"], a["k"])}
    if kind == "distribution":
        return probability.validate_distribution([Fraction(item) for item in a["values"]])
    if kind == "describe":
        result = probability.describe(a["values"])
        return {"mean": str(result["mean"]), "median": str(result["median"]), "modes": [str(m) for m in result["modes"]],
                "range": str(result["range"])}
    if kind == "critical":
        return [[_text(point), label] for point, label in calculus.critical_points(a["latex"]) or []]
    if kind == "limit":
        value, _ = calculus.limit(a["latex"], a["point"])
        return {"value": _text(value) if value is not None else None}
    if kind == "definite":
        signed, area, nature = calculus.definite(a["latex"], a["lower"], a["upper"])
        out = {"kind": nature}
        if signed is not None:
            out |= {"signed": _text(signed), "area": _text(area) if area is not None else None}
        return out
    if kind == "antiderivative":
        return calculus.check_antiderivative(a["integrand"], a["candidate"])
    if kind == "geometry":
        # TA-008B: olgular yalnız kaynağa (metin alıntısı / işaretli şekil) bağlanırsa kısıt olur.
        source = geometry.Source(a.get("text", ""), bool(a.get("figure", False)))
        result = geometry.analyze(GeometryModel.model_validate(a["model"]), source)
        return {"determinacy": result.determinacy, "values": [_text(v) for v in result.target_values],
                "reasons": sorted({c.reason for c in result.checks})}
    if kind == "word":
        result = word_problems.analyze(WordProblemModel.model_validate(a["model"]), a["text"])
        fidelity = next((c for c in result.checks if c.area == "model_fidelity"), None)
        return {"status": result.status, "values": [_text(v) for v in result.objective_values],
                "fidelity": fidelity.status if fidelity else None, "fidelity_reason": fidelity.reason if fidelity else None}
    if kind == "strategy":
        refs = strategies.recommend(set(a["features"]), a["grade"], set(a["forbidden"]))
        return {ref.id: (ref.reason if ref.reason == "forbidden_by_approved_policy" else ref.suitable_for_grade) for ref in refs}
    raise ValueError(f"Tanımsız vaka türü: {kind}")


def _interval(item) -> str:
    if item.lower is not None and item.lower == item.upper:
        return "{" + item.lower + "}"
    lower = item.lower if item.lower is not None else "−∞"
    upper = item.upper if item.upper is not None else "+∞"
    return f"{'[' if item.lower_closed else '('}{lower}, {upper}{']' if item.upper_closed else ')'}"


def matches(actual, expected) -> bool:
    """Beklenen alt kümesi: sözlükte yalnız belirtilen anahtarlar karşılaştırılır; listeler kapsanmalı."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for key, value in expected.items():
            if key == "status_not":
                if actual.get("status") == value:
                    return False
                continue
            if key == "reasons":
                if not set(value) <= set(actual.get("reasons", [])):
                    return False
                continue
            if actual.get(key) != value:
                return False
        return True
    return actual == expected


def run() -> tuple[list[dict], list[str]]:
    data = json.loads(CASES.read_text(encoding="utf-8"))
    results, problems = [], []
    for case in data["cases"]:
        timings = []
        actual = None
        for _ in range(3):
            started = perf_counter()
            try:
                actual = run_case(case)
            except Exception as exc:  # noqa: BLE001 — derlem sonucu olarak raporlanır
                actual = {"exception": type(exc).__name__, "message": str(exc)[:120]}
            timings.append((perf_counter() - started) * 1000)
        ok = matches(actual, case["expect"])
        if not ok:
            problems.append(f"{case['id']}: beklenen {case['expect']!r}, bulunan {actual!r}")
        results.append({"id": case["id"], "area": case["area"], "ok": ok, "ms": median(timings)})
    return results, problems


def render_matrix(results: list[dict]) -> str:
    from apps.api.app.features.mathematics import capability_matrix

    by_area: dict[str, list[dict]] = {}
    for row in results:
        by_area.setdefault(row["area"], []).append(row)
    lines = ["# TA-008/TA-008B matematik yetenek matrisi", "",
             "Bu dosya `python -m scripts.math_matrix` ile üretilir; elle düzenlenmez. CI `--check` uygular.", "",
             ("Matris *gerçekte uygulanan* yeteneği gösterir; hedef mimari değildir. Hiçbir konu bağımsız öğretmen anahtarıyla "
              "değerlendirilmedi (değerlendirme: **yok**). `runtime`: `live` ders akışında kaynak ifadeler ayrıştığında, "
              "`model` yalnız sağlayıcı yapılandırılmış model önerdiğinde, `offline` yalnız çevrimdışı/regresyonda."), "",
             "| Konu | Tanıma | Temsil | Yerel çözücü | Doğrulama | Çalışma zamanı | Değerlendirme | Not |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in capability_matrix.rows():
        lines.append(f"| {row['topic']} | {row['recognition']} | {row['representation']} | `{row['local_solver']}` | "
                     f"{row['verification']} | {row['runtime']} | yok | {row['note']} |")
    lines += ["", "## Regresyon derlemi", "",
              (f"`apps/api/tests/fixtures/mathematics/regression.json`: {len(results)} sentetik vaka "
               f"(olumlu, olumsuz, sınır ve çekimser). Geçen: {sum(r['ok'] for r in results)}/{len(results)}."), "",
              "| Alan | Vaka | Geçen |", "| --- | --- | --- |"]
    for area, items in sorted(by_area.items()):
        lines.append(f"| {area} | {len(items)} | {sum(item['ok'] for item in items)} |")
    lines += ["", "Sentetik derlem başarısı gerçek model doğruluğu değildir.", ""]
    return "\n".join(lines)


def render_benchmark(results: list[dict]) -> str:
    by_area: dict[str, list[float]] = {}
    for row in results:
        by_area.setdefault(row["area"], []).append(row["ms"])
    lines = ["# TA-008B matematik derlemi yerel ölçümü", "",
             ("`python -m scripts.math_matrix` çıktısı. Süreler bu geliştirme makinesinde, süreç içinde (SymPy ısınmış), vaka "
              "başına üç koşunun ortancasıdır. Yalıtılmış işçinin süreç başlatma maliyeti (≈ 1–3 sn) dahil değildir. Bulut "
              "performansı iddiası değildir."), "",
             "| Alan | Vaka | Ortanca (ms) | En yavaş (ms) |", "| --- | --- | --- | --- |"]
    for area, values in sorted(by_area.items()):
        lines.append(f"| {area} | {len(values)} | {median(values):.1f} | {max(values):.1f} |")
    unsupported = sum(1 for r in results if not r["ok"])
    lines += ["", f"Beklenenle uyuşmayan vaka: {unsupported}.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    results, problems = run()
    matrix = render_matrix(results)
    for problem in problems:
        print(f"SORUN: {problem}")
    if args.check:
        current = MATRIX.read_text(encoding="utf-8") if MATRIX.exists() else ""
        if current != matrix:
            problems.append(f"Güncel olmayan rapor: {MATRIX.relative_to(ROOT)} (python -m scripts.math_matrix)")
            print(f"SORUN: {problems[-1]}")
        print(f"{len(results)} vaka; {sum(r['ok'] for r in results)} geçti. Sağlayıcı çağrısı yapılmadı.")
        return 1 if problems else 0
    MATRIX.parent.mkdir(parents=True, exist_ok=True)
    MATRIX.write_text(matrix, encoding="utf-8", newline="\n")
    BENCHMARK.write_text(render_benchmark(results), encoding="utf-8", newline="\n")
    print(f"Yazıldı: {MATRIX.relative_to(ROOT)}, {BENCHMARK.relative_to(ROOT)}; {sum(r['ok'] for r in results)}/{len(results)} geçti.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

"""TA-009 fizik tuzak seti ve yetenek matrisi (çevrimdışı, sağlayıcı çağrısı yok).

``apps/api/tests/fixtures/physics/traps.json`` içindeki özgün vakaları gerçek fizik doğrulama hattından geçirir ve
beklenen sonuçla karşılaştırır. Beklenen cevaplar türetilmiştir (``answer_origin = derived``); bağımsız öğretmen
anahtarı değildir ve model doğruluğu ölçmez.

    python -m scripts.physics_matrix          # özet + docs/physics/TA-009-capability-matrix.md
    python -m scripts.physics_matrix --check  # uyuşmazlıkta veya eskimiş raporda çıkış kodu 1
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from apps.api.app.features.education.science import ScientificProblemModel
from apps.api.app.features.physics import capability, verify
from apps.api.app.features.reasoning.units import unit_spec

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "apps/api/tests/fixtures/physics/traps.json"
MATRIX = ROOT / "docs/physics/TA-009-capability-matrix.md"


def _units(value):
    """Fikstürde birimler yalın metindir; kanonik biçim yalnız yerel ayrıştırıcıdan kurulur."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "unit" and isinstance(item, str):
                out[key] = unit_spec(item).model_dump()
            else:
                out[key] = _units(item)
        return out
    if isinstance(value, list):
        return [_units(item) for item in value]
    return value


def run_case(case: dict):
    problem = ScientificProblemModel.model_validate(_units(case["problem"]))
    return verify.verify(problem, case["text"], case["claims"])


def matches(report, expect: dict) -> list[str]:
    problems = []
    reasons = {c.reason for c in report.checks}
    if "capability" in expect and report.capability != expect["capability"]:
        problems.append(f"capability {report.capability} ≠ {expect['capability']}")
    if "answer" in expect and report.answer != expect["answer"]:
        problems.append(f"answer {report.answer} ≠ {expect['answer']}")
    if "material" in expect and (report.material_count > 0) != expect["material"]:
        problems.append(f"material {report.material_count}")
    if "reason" in expect and expect["reason"] not in reasons | set(report.answer_reasons):
        problems.append(f"reason {expect['reason']} yok ({sorted(reasons)})")
    if "reason_prefix" in expect and not any(r.startswith(expect["reason_prefix"]) for r in reasons):
        problems.append(f"reason_prefix {expect['reason_prefix']} yok ({sorted(reasons)})")
    if "open_condition" in expect and not any(c.condition == expect["open_condition"] and c.state == "unknown"
                                              and c.assumption_tr is None for c in report.conditions):
        problems.append(f"open_condition {expect['open_condition']} yok")
    if "sliding" in expect:
        marker = {"static": "kaymaz", "kinetic": "Kayma var"}[expect["sliding"]]
        if not any(marker in step for step in report.steps_tr):
            problems.append(f"sliding {expect['sliding']} adımlarda yok")
    if "clarification" in expect and report.clarification_needed != expect["clarification"]:
        problems.append("clarification")
    if "values_used_origin" in expect and not any(v.origin == expect["values_used_origin"] for v in report.values_used):
        problems.append(f"values_used_origin {expect['values_used_origin']} yok")
    return problems


def run():
    data = json.loads(CASES.read_text(encoding="utf-8"))
    results, problems = [], []
    for case in data["cases"]:
        try:
            report = run_case(case)
            issues = matches(report, case["expect"])
        except Exception as exc:  # noqa: BLE001 — vaka sonucu olarak raporlanır
            report, issues = None, [f"{type(exc).__name__}: {exc}"]
        results.append({"id": case["id"], "area": case["area"], "ok": not issues,
                        "capability": report.capability if report else "error", "origin": case.get("answer_origin")})
        problems += [f"{case['id']}: {issue}" for issue in issues]
    return results, problems


def render(results) -> str:
    lines = ["# TA-009 fizik yetenek matrisi", "",
             "Bu dosya `python -m scripts.physics_matrix` ile üretilir; elle düzenlenmez. CI `--check` uygular.", "",
             ("`verified` bir konu adından çıkarılmaz: o problem için belirlenimci denetimler gerçekten çalışıp geçtiğinde "
              "verilir. Konu sınıfı, o konudaki en güçlü *uygulanmış* doğrulamayı gösterir. Hiçbir konu bağımsız öğretmen "
              "anahtarıyla değerlendirilmedi; öğrenciye açıklık kapalıdır (`TEACHERAI_PHYSICS_STUDENT_ENABLED=false`)."), "",
             "| Alan | Konu | Sınıf | Çözücü / denetleyici | Not |", "| --- | --- | --- | --- | --- |"]
    for row in capability.ROWS:
        lines.append(f"| {row[0]} | {row[1]} | {row[2]} | `{row[3]}` | {row[4]} |")
    by_area = Counter(r["area"] for r in results)
    ok = Counter(r["area"] for r in results if r["ok"])
    lines += ["", "## Tuzak seti", "",
              (f"`apps/api/tests/fixtures/physics/traps.json`: {len(results)} özgün vaka; geçen "
               f"{sum(r['ok'] for r in results)}/{len(results)}. Bütün beklenen cevaplar türetilmiştir "
               "(`answer_origin = derived`); bağımsız öğretmen cevap anahtarı yoktur."), "",
              "| Alan | Vaka | Geçen |", "| --- | --- | --- |"]
    lines += [f"| {area} | {count} | {ok[area]} |" for area, count in sorted(by_area.items())]
    lines += ["", "Sahte sağlayıcı ve sentetik vaka başarısı model doğruluğu değildir.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    results, problems = run()
    for problem in problems:
        print(f"SORUN: {problem}")
    matrix = render(results)
    if args.check:
        current = MATRIX.read_text(encoding="utf-8") if MATRIX.exists() else ""
        if current != matrix:
            problems.append("eskimiş rapor")
            print(f"SORUN: güncel olmayan rapor: {MATRIX.relative_to(ROOT)} (python -m scripts.physics_matrix)")
    else:
        MATRIX.parent.mkdir(parents=True, exist_ok=True)
        MATRIX.write_text(matrix, encoding="utf-8", newline="\n")
    print(f"{len(results)} vaka; {sum(r['ok'] for r in results)} geçti. Sağlayıcı çağrısı yapılmadı.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

"""TA-008: TA-007 denetim düzeltmeleri, matematik ve geometri uzmanlığı. Ağ ve sağlayıcı çağrısı yoktur; sentetik
yetkiler ve katkılar yalnız bu yalıtılmış testlerde fikstürdür."""

from __future__ import annotations

import json
from datetime import date

import pytest
from pydantic import ValidationError

from apps.api.app.features.curriculum import context as selection
from apps.api.app.features.curriculum import methods
from apps.api.app.features.education.base import Subject
from apps.api.app.features.education.contribution import ContributionRecord, ContributionRegister, TeacherContribution
from apps.api.app.features.education.knowledge import (
    ContributionPublication,
    KnowledgeEntry,
    content_digest,
    rights_digest,
)
from apps.api.app.features.knowledge import registry as knowledge
from apps.api.app.features.knowledge import retrieval
from apps.api.app.features.lessons.context import build_lesson_generation_context
from apps.api.app.features.lessons.normalization import normalize_lesson_draft_response
from apps.api.app.features.lessons.schemas import Expression, LessonDraftResponse, Step
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.mathematics import capability_matrix, specialist, strategies
from apps.api.tests.test_curriculum import linear_analysis
from apps.api.tests.test_lesson_provider_errors import lesson_payload
from apps.api.tests.test_mathai import plan
from apps.api.tests.test_question_integrity import analysis
from apps.api.tests.test_ta007 import auth, policy
from scripts import forms_import, math_matrix, teacher_contributions

TODAY = date(2026, 11, 24)
DIGEST = "a" * 64


# --- §3.1–3.3 katkı, bağımsızlık, haklar ------------------------------------------------------------------------

def teacher_entry(registry, *, reviewer="teacher:inceleyen-01", publication_status="published", digest=DIGEST,
                  source_use="teacher_original"):
    base = registry.entries["math.equation-equivalence"]
    data = {**base.model_dump(), "authored_by": "teacher", "author_ref": "teacher:katki-sahibi"}
    data["rights"] = {"source_use": source_use, "basis_tr": "Öğretmenin özgün açıklaması.", "contribution_id": "c-01",
                      "contribution_digest": digest, "decision": "approved", "decided_by": "owner:test-sahip",
                      "decided_on": "2026-12-03"}
    draft = KnowledgeEntry.model_validate({**data, "status": "draft", "reviews": []})
    review = {"reviewer": reviewer, "role": "teacher", "reviewed_on": "2026-12-02", "reviewed_version": draft.version,
              "decision": "approve", "rationale_tr": "İncelendi.", "stage": "scientific", "content_digest": content_digest(draft)}
    entry = KnowledgeEntry.model_validate({**data, "status": "approved", "reviews": [review]})
    entry = entry.model_copy(update={"rights": entry.rights.model_copy(update={"decision_digest": rights_digest(entry)})})
    publications = {"c-01": ContributionPublication(
        contribution_id="c-01", contributor="teacher:katki-sahibi", subject="mathematics", content_digest=DIGEST,
        status=publication_status, decided_on="2026-12-01",
        published_by="owner:test-sahip" if publication_status == "published" else None, consent_use=True)}
    reviewers = (auth(reviewer, "teacher", "scientific"), auth("owner:test-sahip", "project_owner", "rights"))
    return entry, publications, reviewers


def test_published_teacher_contribution_is_eligible_and_withdrawal_revokes_it():
    registry = knowledge.default_knowledge()
    entry, publications, reviewers = teacher_entry(registry)
    assert knowledge.runtime_eligibility(entry, registry.sources, reviewers, publications) == []
    for status in ("withdrawn", "rejected", "superseded"):
        _, revoked, _ = teacher_entry(registry, publication_status=status)
        assert f"contribution_{status}" in knowledge.runtime_eligibility(entry, registry.sources, reviewers, revoked)
    assert "contribution_unpublished" in knowledge.runtime_eligibility(entry, registry.sources, reviewers, {})
    stale, _, _ = teacher_entry(registry, digest="b" * 64)
    assert "contribution_digest_mismatch" in knowledge.runtime_eligibility(stale, registry.sources, reviewers, publications)


def test_contributor_and_author_cannot_independently_approve():
    registry = knowledge.default_knowledge()
    with pytest.raises(ValidationError):  # yazar kendi içeriğini onaylayamaz (sözleşme)
        teacher_entry(registry, reviewer="teacher:katki-sahibi")
    entry, publications, reviewers = teacher_entry(registry)
    expert = KnowledgeEntry.model_validate({**entry.model_dump(), "authored_by": "subject_expert", "author_ref": "expert:yazar-01"})
    other = {"c-01": publications["c-01"].model_copy(update={"contributor": "teacher:inceleyen-01"})}
    assert "not_independent:scientific" in knowledge.runtime_eligibility(expert, registry.sources, reviewers, other)
    with pytest.raises(ValidationError):  # öğretmen yazımı yazar başvurusu taşır
        KnowledgeEntry.model_validate({**entry.model_dump(), "author_ref": None})


def test_reference_only_rights_and_stale_rights_or_content_block_transmission():
    registry = knowledge.default_knowledge()
    entry, publications, reviewers = teacher_entry(registry)
    reference = entry.model_copy(update={"rights": entry.rights.model_copy(update={"source_use": "reference_citation"})})
    blockers = knowledge.runtime_eligibility(reference, registry.sources, reviewers, publications)
    assert "reference_only_not_transmittable" in blockers and "rights_decision_stale" in blockers
    retitled = entry.model_copy(update={"title_tr": "Değiştirilmiş başlık"})  # başlık artık özete dahil
    assert "stale_approval" in knowledge.runtime_eligibility(retitled, registry.sources, reviewers, publications)
    unsealed = entry.model_copy(update={"rights": entry.rights.model_copy(update={"decision_digest": None})})
    assert "rights_decision_incomplete" in knowledge.runtime_eligibility(unsealed, registry.sources, reviewers, publications)
    uses = knowledge.use_permissions(registry, registry.entries["math.function-domain"])
    assert uses["provider_transmission"].startswith("blocked") and uses["model_training"] == "not_performed"


def test_snapshot_is_built_offline_and_withdrawal_changes_status(tmp_path, monkeypatch):
    contribution = TeacherContribution.model_validate({
        "schema_name": "teacherai.teacher_contribution", "version": "1.0.0", "contributor": "teacher:katki-sahibi",
        "role": "teacher", "subject": "mathematics", "submitted_on": "2026-12-01", "consent_use": True,
        "items": [{"kind": "common_error", "topic": "dogrusal_denklemler", "text_tr": "Değişkene bölmek."}]})
    (tmp_path / "c-01.json").write_text(contribution.model_dump_json(), encoding="utf-8")
    digest = teacher_contributions.contribution_digest(contribution)
    events = [{"stage": "submitted", "on": "2026-12-01", "by": "teacher:katki-sahibi", "role": "teacher", "content_digest": digest},
              {"stage": "withdrawn", "on": "2026-12-05", "by": "owner:test-sahip", "role": "project_owner", "content_digest": digest}]
    register = ContributionRegister(schema_name="teacherai.contribution_register", version="1.0.0",
                                    records=[ContributionRecord(contribution_id="c-01", path="c-01.json", events=events)])
    monkeypatch.setattr(teacher_contributions, "FOLDER", tmp_path)
    data = teacher_contributions.snapshot(register, reviewers=())
    assert data["records"][0]["status"] == "withdrawn" and data["records"][0]["consent_model_training"] is False


def test_method_policy_from_withdrawn_contribution_is_inactive():
    approved = {"status": "approved", "approved_by": "teacher:test-ogretmen", "approved_on": date(2026, 1, 15)}
    linked = policy(contribution_id="c-01", contribution_digest=DIGEST, **approved)
    reviewers = (auth("teacher:test-ogretmen", "teacher", "pedagogical"),)
    published = ContributionPublication(contribution_id="c-01", contributor="teacher:katki-sahibi", subject="mathematics",
                                        content_digest=DIGEST, status="published", decided_on="2026-12-01",
                                        published_by="owner:test-sahip", consent_use=True)
    assert methods.inactive_reason(linked, reviewers, {"c-01": published}) is None
    withdrawn = published.model_copy(update={"status": "withdrawn", "published_by": None})
    assert methods.inactive_reason(linked, reviewers, {"c-01": withdrawn}) == "contribution_withdrawn"
    assert methods.inactive_reason(linked, reviewers, {}) == "contribution_unpublished"


# --- §3.4–3.5 düzey uygunluğu, bütçe, denemeler ---------------------------------------------------------------

def test_retrieval_respects_learner_level_without_confusing_exam_with_grade():
    entry = knowledge.default_knowledge().entries["math.function-domain"]  # 10-12. sınıf
    assert retrieval.level_reason(entry, retrieval.Learner(8)) == "above_learner_level"
    assert retrieval.level_reason(entry, retrieval.Learner(8, advanced_requested=True)) is None
    assert retrieval.level_reason(entry, retrieval.Learner(11)) is None
    assert retrieval.level_reason(entry, retrieval.Learner(None, ("AYT",))) == "learner_level_unknown"
    ayt = knowledge.default_knowledge().entries["math.limit-laws"]  # "12. sınıf", "AYT"
    assert retrieval.level_reason(ayt, retrieval.Learner(None, ("AYT",))) is None
    lower = knowledge.default_knowledge().entries["math.equation-equivalence"]  # 7-8: ön koşul olarak üst sınıfa uygun
    assert retrieval.level_reason(lower, retrieval.Learner(11)) is None


def test_payload_budget_matches_transmitted_serialization():
    chosen = selection.select(linear_analysis(), Subject.MATHEMATICS, 8, today=TODAY)
    serialized = json.dumps(chosen.payload.model_dump(exclude_none=True), ensure_ascii=False, separators=(",", ":"))
    assert chosen.provenance.payload_bytes == len(serialized.encode("utf-8")) <= selection.MAX_PAYLOAD_BYTES


def test_attempts_distinguish_accepted_retried_and_emergency():
    provenance = selection.select(linear_analysis(), Subject.MATHEMATICS, 8, today=TODAY).provenance
    recorded = selection.with_attempts(provenance, [
        {"purpose": "initial", "levels": ["normal", "emergency"], "accepted": False},
        {"purpose": "verification_correction", "levels": ["normal"], "accepted": True}])
    assert recorded.transmission == "normal" and len(recorded.attempts) == 2
    assert recorded.attempts[0].levels == ["normal", "emergency"] and not recorded.attempts[0].accepted
    unknown = selection.with_attempts(provenance, [{"purpose": "initial", "levels": ["unknown"], "accepted": True}])
    assert unknown.transmission is None  # düzey uydurulmaz


# --- §3.6 Google Forms adaptörü -------------------------------------------------------------------------------

MAPPING = {"columns": {"timestamp": "Zaman", "subject": "Branş", "experience": "Deneyim", "misconceptions": "Hatalar",
                       "strategies": "Stratejiler", "general": "Genel", "consent_use": "İzin", "consent_training": "Eğitim izni"},
           "subject_values": {"Matematik": "mathematics"}, "yes_values": ["Evet"], "no_values": ["Hayır"]}
HEADER = "Zaman,Branş,Deneyim,Hatalar,Stratejiler,Genel,İzin,Eğitim izni"


def forms_csv(tmp_path, *rows):
    path = tmp_path / "yanitlar.csv"
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    mapping = tmp_path / "eşleme.json"
    mapping.write_text(json.dumps(MAPPING, ensure_ascii=False), encoding="utf-8")
    return path, mapping


def test_forms_import_requires_consent_detects_duplicates_and_keeps_general_topic(tmp_path):
    good = "25.11.2026 10:00:00,Matematik,12 yıl,x'e bölmek,Terazi modeli,Önce bilinmeyeni sorun,Evet,Hayır"
    path, mapping = forms_csv(tmp_path, good, good,
                              "25.11.2026 11:00:00,Matematik,5 yıl,Hata,Strateji,,Hayır,Hayır",
                              "25.11.2026 12:00:00,Matematik,3 yıl,ogretmen@example.com,Strateji,,Evet,Hayır",
                              "25.11.2026 13:00:00,Tarih,3 yıl,Hata,Strateji,,Evet,Hayır")
    report = forms_import.convert(path, mapping, ledger=set())
    assert len(report["accepted"]) == 1
    reasons = " ".join(item["reason"] for item in report["skipped"])
    assert "yinelenen" in reasons and "kullanım izni" in reasons and "kişisel bilgi" in reasons and "alan eşlenemedi" in reasons
    record = report["accepted"][0]["record"]
    assert record["submitted_on"] == "2026-11-25" and record["consent_model_training"] is False
    assert any(item["kind"] == "general_pedagogy" and item["topic"] == "genel" for item in record["items"])
    assert record["contributor"].startswith("teacher:form-")  # takma başvuru; kimlik uydurulmaz
    TeacherContribution.model_validate(record)
    again = forms_import.convert(path, mapping, ledger={report["accepted"][0]["digest"]})
    assert again["accepted"] == []  # artımlı içe aktarma


def test_forms_mapping_must_match_real_headers(tmp_path):
    path, mapping = forms_csv(tmp_path, "x,Matematik,,Hata,,,Evet,Hayır")
    broken = {**MAPPING, "columns": {**MAPPING["columns"], "subject": "Ders adı"}}
    mapping.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(forms_import.MappingError):
        forms_import.convert(path, mapping, ledger=set())


# --- Matematik uzmanlığı ders akışında ------------------------------------------------------------------------

def test_dividing_by_x_loses_a_root_and_is_never_verified():
    p = plan("x^2 = 3x", "x = 3", steps=[Step(id="step_1", type="transformation", title="x'e böl",
                                               explanation="İki tarafı x'e bölelim.",
                                               expressions=[Expression(type="equation", latex="x = 3")])])
    result = MathAIService().verify(p)
    reasons = {check.reason for check in result.mathematics.checks}
    assert result.status != "verified"
    assert {"missing_solutions", "division_by_expression_with_zero"} <= reasons
    assert result.mathematics.solution_set.elements == ["0", "3"]


def test_report_never_strengthens_status_and_offers_verified_alternatives():
    p = plan("x^2 - 5x + 6 = 0", "x = 2, x = 3", steps=[Step(id="step_1", type="transformation", title="Çarpanlara ayır",
                                                             explanation="Çarpanlarına ayıralım.",
                                                             expressions=[Expression(type="equation", latex="(x-2)(x-3) = 0")])])
    result = MathAIService().verify(p)
    assert result.status == "verified"
    assert [path.strategy for path in result.mathematics.alternatives] == ["factoring", "completing_square", "quadratic_formula"]
    assert all(path.verified for path in result.mathematics.alternatives)
    inequality = plan("2x - 3 < 7", "x < 5", steps=[Step(id="step_1", type="transformation", title="Ekle", explanation="3 ekle",
                                                         expressions=[Expression(type="inequality", latex="2x < 10")])])
    inequality.content.final_answer_expressions = [Expression(type="inequality", latex="x < 5")]
    checked = MathAIService().verify(inequality)
    assert any(c.reason == "claimed_interval_matches" for c in checked.mathematics.checks)
    assert checked.mathematics.solution_set.kind == "intervals"


def test_provider_model_is_validated_and_invalid_model_is_dropped():
    payload = lesson_payload()
    geometry = {"kind": "geometry", "word_problem": None, "geometry": {
        "points": ["A", "B", "C"], "facts": [{"id": "t", "kind": "triangle", "points": ["A", "B", "C"], "other": [],
                                              "value": None, "origin": "stated"}],
        "constructions": [], "target": {"kind": "angle", "points": ["A", "B", "C"]}, "schematic": True}}
    payload["content"]["mathematical_model"] = geometry
    draft = normalize_lesson_draft_response(LessonDraftResponse.model_validate(payload))
    assert draft.content.mathematical_model.geometry.facts[0].kind == "triangle"
    broken = json.loads(json.dumps(geometry))
    broken["geometry"]["facts"][0]["points"] = ["Z"]  # tanımsız nokta
    payload["content"]["mathematical_model"] = broken
    assert normalize_lesson_draft_response(LessonDraftResponse.model_validate(payload)).content.mathematical_model is None


def test_geometry_model_in_lesson_reports_schematic_and_unmarked_facts():
    from apps.api.app.features.education.mathematics import MathematicalModel

    p = plan("x = 1", "x = 1")
    model = MathematicalModel.model_validate({"kind": "geometry", "geometry": {
        "points": ["A", "B", "C"], "facts": [
            {"id": "t", "kind": "triangle", "points": ["A", "B", "C"], "origin": "stated"},
            {"id": "r", "kind": "right_angle", "points": ["A", "B", "C"], "origin": "visual_uncertain"},
            {"id": "ab", "kind": "segment_length", "points": ["A", "B"], "value": "3", "origin": "stated"},
            {"id": "bc", "kind": "segment_length", "points": ["B", "C"], "value": "4", "origin": "stated"}],
        "target": {"kind": "length", "points": ["A", "C"]}}})
    p = p.model_copy(update={"content": p.content.model_copy(update={"mathematical_model": model})})
    report = specialist.analyze(p)
    assert report.model_kind == "geometry" and report.model_status == "rejected"
    assert {"visual_fact_not_given", "target_underdetermined"} <= {c.reason for c in report.checks}
    assert any("ölçekli" in note for note in report.notes_tr)


def test_domain_hints_reach_the_prompt_only_when_present():
    rational = analysis(question_text="Denklemi çözünüz.", mathematical_expressions=[r"\frac{1}{x-1} = 2"],
                        answer_choices=["A) 1", "B) 2", "C) 3", "D) 3/2"])
    built = build_lesson_generation_context(rational)
    assert "x - 1 ≠ 0" in built.payload["mathematics_hints"]["domain_conditions_tr"][0]
    assert "mathematics_hints" not in build_lesson_generation_context(linear_analysis()).payload


def test_strategy_suitability_respects_grade_and_approved_policy():
    refs = {ref.id: ref for ref in strategies.recommend({"quadratic"}, 8)}
    assert refs["quadratic_formula"].suitable_for_grade is False and refs["quadratic_formula"].status == "draft"
    forbidden = {ref.id: ref for ref in strategies.recommend({"quadratic"}, 10, {"quadratic_formula"})}
    assert forbidden["quadratic_formula"].reason == "forbidden_by_approved_policy"
    assert all(item.status == "draft" for item in strategies.registry().values())  # AI taslağı; öğretmen deneyimi değil


def test_board_uses_only_validated_number_line_and_marks_schematic():
    from apps.api.app.features.board.planner import BoardPlanner

    p = plan("2x - 3 < 7", "x < 5", steps=[Step(id="step_1", type="transformation", title="Ekle", explanation="3 ekle",
                                                 expressions=[Expression(type="inequality", latex="2x < 10")])])
    p.content.final_answer_expressions = [Expression(type="inequality", latex="x < 5")]
    verification = MathAIService().verify(p)
    board = BoardPlanner().create(p, verification)
    line = next(item for item in board.elements if item.type == "number_line")
    assert line.intervals[0].upper == "5" and not line.intervals[0].upper_closed


def test_regression_corpus_and_capability_matrix_are_honest():
    results, problems = math_matrix.run()
    assert problems == [] and len(results) >= 60
    rows = capability_matrix.rows()
    assert {row["verification"] for row in rows} >= {"independent", "partial", "ai_assisted_only"}
    assert all(row["runtime"] in {"live", "model", "offline", "none"} for row in rows)


def test_math_knowledge_expansion_is_sourced_draft_and_level_tagged():
    registry = knowledge.default_knowledge()
    maths = [e for e in registry.entries.values() if e.subject in {Subject.MATHEMATICS, Subject.GEOMETRY}]
    assert 150 <= len(maths) <= 250
    assert all(e.status == "draft" and not e.reviews and e.levels for e in maths)
    assert sum(1 for e in maths if not e.provenance) == 1  # yalnız Pólya taslağı kaynaksız
    assert registry.sources["joyce.euclid-elements"].permissions.ingestion == "not_allowed"
    assert all(locator.page is None for e in maths for locator in e.provenance)

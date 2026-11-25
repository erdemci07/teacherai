"""TA-006 bilimsel kaynak/bilgi kaydı, onay akışı, denetleyici sınırları ve veri ayrımı. Ağ ve sağlayıcı yoktur."""

from datetime import date

import pytest
from pydantic import ValidationError

from apps.api.app.features.education.base import Subject
from apps.api.app.features.education.contribution import TeacherContribution
from apps.api.app.features.education.knowledge import (
    KnowledgeEntry,
    ReviewerAuthorization,
    SourceRecord,
    content_digest,
    rights_digest,
)
from apps.api.app.features.knowledge import capabilities as caps
from apps.api.app.features.knowledge import registry as k
from scripts import dataset_manifest

REVIEW = {"reviewer": "teacher:fizik-ogretmeni-01", "role": "teacher", "reviewed_on": "2026-12-01", "reviewed_version": 1,
          "decision": "approve", "rationale_tr": "Koşullar ve sadeleştirme 10. sınıfa uygun."}
# TA-007: sentetik yetkiler yalnız bu yalıtılmış testte. Üretim inceleyen kaydı boştur.
TEACHER = ReviewerAuthorization(reviewer="teacher:fizik-ogretmeni-01", roles=["teacher"], subjects=["physics"],
                                stages=["scientific"], valid_from=date(2026, 1, 1), authorized_by="owner:test-sahip",
                                authorized_on=date(2026, 1, 1), evidence_note_tr="Yalnız test fikstürü.")
OWNER = ReviewerAuthorization(reviewer="owner:test-sahip", roles=["project_owner"], subjects=["physics"],
                              stages=["rights"], valid_from=date(2026, 1, 1), authorized_by="owner:test-sahip",
                              authorized_on=date(2026, 1, 1), evidence_note_tr="Yalnız test fikstürü.")
RIGHTS = {"source_use": "independent_fact", "basis_tr": "Özgün anlatım; kaynak yalnız doğrulama başvurusu.",
          "decision": "approved", "decided_by": "owner:test-sahip", "decided_on": "2026-12-02"}


@pytest.fixture(scope="module")
def registry():
    return k.default_knowledge()


def seal_rights(entry):
    """TA-008: hak kararı, karar verilen hak kaydının ve içeriğin özetini taşır (yalnız test fikstürü)."""
    return entry.model_copy(update={"rights": entry.rights.model_copy(update={"decision_digest": rights_digest(entry)})})


def approved(entry: KnowledgeEntry, rights: dict | None = None, **review) -> KnowledgeEntry:
    """TA-007: onay bilimsel aşamada, aynı sürümün içerik özetiyle verilir."""
    base = {**REVIEW, "reviewed_version": entry.version, "stage": "scientific", "content_digest": content_digest(entry)}
    data = {**entry.model_dump(), "status": "approved", "reviews": [{**base, **review}]}
    if rights is not None:
        data["rights"] = rights
        return seal_rights(KnowledgeEntry.model_validate(data))
    return KnowledgeEntry.model_validate(data)


def test_balanced_initial_dataset_is_sourced_draft_and_not_runtime_eligible(registry):
    rows = {row["subject"]: row for row in k.coverage(registry)}
    # TA-007: dengeli genişletme (hedef aralık, kota değil): çekirdek branşlarda 40–60, ortaokul fende 15–30.
    for subject in ("physics", "chemistry", "biology"):
        assert 40 <= rows[subject]["total"] <= 60
    # TA-008: matematik/geometri uzmanlık fazında hedef aralık 150–250 (kota değil).
    assert 150 <= rows["mathematics"]["total"] <= 250
    assert 15 <= rows["science"]["total"] <= 30
    assert all(entry.status == "draft" and entry.authored_by == "claude-draft" and not entry.reviews
               for entry in registry.entries.values())
    assert sum(row["runtime_eligible"] for row in rows.values()) == 0
    assert rows["mathematics"]["unsourced"] == ["math.polya-problem-solving"]


def test_no_fabricated_page_numbers_and_every_locator_points_to_verified_section(registry):
    for entry in registry.entries.values():
        for locator in entry.provenance:
            assert locator.page is None
            # TA-008 eklemeleri 2026-11-25'te sayfa başlığıyla doğrulandı.
            assert locator.verified_on in {date(2026, 11, 24), date(2026, 11, 25)} and (locator.url or locator.section)


def test_biology_is_not_forced_into_equations(registry):
    biology = [entry for entry in registry.entries.values() if entry.subject == Subject.BIOLOGY]
    assert sum(1 for entry in biology if entry.representation) <= 2  # yalnız fotosentez toplam denklemi
    assert sum(1 for entry in biology if entry.structure_function) >= 4
    assert {entry.kind for entry in biology} >= {"process", "relationship"}


def test_simplifications_are_separate_from_scientific_statement(registry):
    entry = registry.entries["bio.ecosystem-energy-flow"]
    assert "%10" not in entry.statement_tr and entry.simplifications and entry.simplifications[0].omits_tr


# --- Kaynak hakları -----------------------------------------------------------------------------------------------

def test_source_permissions_are_four_independent_categories(registry):
    openstax = registry.sources["openstax.chemistry-2e"]
    assert openstax.license == "CC BY-NC-SA 4.0" and openstax.permissions.ingestion == "conditional"
    assert openstax.permissions.model_training == "unknown"
    textbook = registry.sources["campbell.biology"]
    assert textbook.access == "purchase_required" and textbook.permissions.ingestion == "not_allowed"
    assert registry.sources["iupac.gold-book"].access == "access_restricted"


def test_rights_cannot_be_assumed():
    base = SourceRecord.model_validate(k.default_knowledge().sources["nist.codata"].model_dump())
    for field in ("ingestion", "redistribution", "model_training"):
        with pytest.raises(ValidationError):
            SourceRecord.model_validate({**base.model_dump(), "permissions": {**base.permissions.model_dump(), field: "allowed"}})
    with pytest.raises(ValidationError):  # satın alınan kitap içeri alma izni sayılmaz
        SourceRecord.model_validate({**k.default_knowledge().sources["stewart.calculus"].model_dump(),
                                     "permissions": {"academic_reference": "allowed", "ingestion": "unknown",
                                                     "redistribution": "not_allowed", "model_training": "not_allowed"}})
    sa = k.default_knowledge().sources["active-calculus"].model_dump()
    with pytest.raises(ValidationError):  # share-alike yükümlülüğü koşul olarak yazılmalı
        SourceRecord.model_validate({**sa, "permissions": {**sa["permissions"], "ingestion": "unknown", "redistribution": "unknown"}})


# --- Öğretmen onayı -----------------------------------------------------------------------------------------------

def test_approval_requires_human_review_of_the_same_version(registry):
    entry = registry.entries["phys.ohms-law"]
    assert approved(entry).status == "approved"
    for bad in ({"reviewer": "claude:taslak"}, {"role": "project_owner"}, {"reviewed_version": 2}, {"decision": "source_verified"},
                {"content_digest": None}, {"stage": "pedagogical"}):
        with pytest.raises(ValidationError):
            approved(entry, **bad)
    with pytest.raises(ValidationError):
        KnowledgeEntry.model_validate({**entry.model_dump(), "status": "approved"})  # inceleme kaydı yok
    with pytest.raises(ValidationError):
        approved(registry.entries["math.polya-problem-solving"])  # kaynaksız girdi onaylanamaz


def test_review_workflow_states_follow_last_decision(registry):
    entry = registry.entries["chem.le-chatelier"].model_dump()
    revision = {**REVIEW, "decision": "request_revision", "rationale_tr": "Soy gaz örneği eklenmeli."}
    assert KnowledgeEntry.model_validate({**entry, "status": "revision_requested", "reviews": [revision]}).status == "revision_requested"
    rejected = {**REVIEW, "decision": "reject", "rationale_tr": "Kapsam dışı."}
    assert KnowledgeEntry.model_validate({**entry, "status": "rejected", "reviews": [rejected]}).status == "rejected"
    superseded = {**REVIEW, "decision": "supersede", "rationale_tr": "Sürüm 2 yerine geçti."}
    assert KnowledgeEntry.model_validate({**entry, "status": "superseded", "reviews": [superseded]}).status == "superseded"
    with pytest.raises(ValidationError):
        KnowledgeEntry.model_validate({**entry, "status": "approved", "reviews": [revision]})


def test_law_records_must_state_validity_conditions(registry):
    with pytest.raises(ValidationError):
        KnowledgeEntry.model_validate({**registry.entries["phys.ohms-law"].model_dump(), "conditions_tr": []})


# --- Çalışma zamanı uygunluğu ve seçim -------------------------------------------------------------------------

def test_drafts_are_excluded_from_runtime_selection_but_visible_in_offline_preview(registry):
    assert k.select(registry, Subject.PHYSICS, topic_keys={"elektrik"}) == []
    preview = [entry.id for entry in k.select(registry, Subject.PHYSICS, topic_keys={"elektrik"}, include_drafts=True)]
    # TA-007: genişletmeyle "elektrik" konusunda daha çok taslak var; sıra kimliğe göre belirlenimcidir.
    assert preview == ["phys.electric-current", "phys.electric-power", "phys.kirchhoff-rules"]
    shown = k.preview(registry, "phys.ohms-law")
    assert "status:draft" in shown["runtime_blockers"] and shown["notice_tr"].startswith("TASLAK")


def test_approved_and_rights_clear_entry_becomes_eligible(registry):
    entry = approved(registry.entries["phys.ohms-law"], rights=RIGHTS)
    reviewers = (TEACHER, OWNER)
    assert k.runtime_eligibility(entry, registry.sources, reviewers) == []
    # TA-007: yetki kaydı olmadan sözdizimi geçerli onay ve hak kararı yetmez.
    assert {"reviewer_not_authorized", "rights_decider_not_authorized"} <= set(k.runtime_eligibility(entry, registry.sources))
    restricted = {**registry.sources, "openstax.university-physics-volume-2": registry.sources["iupac.gold-book"].model_copy(
        update={"id": "openstax.university-physics-volume-2"})}
    assert "rights_restricted:openstax.university-physics-volume-2" in k.runtime_eligibility(entry, restricted, reviewers)
    custom = k.KnowledgeRegistry(sources=registry.sources, entries={**registry.entries, entry.id: entry}, digest="t",
                                 reviewers=reviewers)
    assert [item.id for item in k.select(custom, Subject.PHYSICS, topic_keys={"elektrik"})] == ["phys.ohms-law"]


def test_selection_is_deterministic_and_prefers_outcome_links(registry):
    outcome = {"meb-2018.matematik.1-8::M.8.2.3.3"}
    first = [entry.id for entry in k.select(registry, Subject.MATHEMATICS, topic_keys={"dogrusal_denklemler"},
                                            outcome_ids=outcome, include_drafts=True)]
    assert first == [entry.id for entry in k.select(registry, Subject.MATHEMATICS, topic_keys={"dogrusal_denklemler"},
                                                    outcome_ids=outcome, include_drafts=True)]
    assert first[0] == "math.inequality-sign-reversal"


# --- Denetleyici sınırları ------------------------------------------------------------------------------------

def test_every_verifier_id_resolves_to_a_real_function():
    assert caps.missing_definitions() == set()
    for name in caps.CAPABILITIES:
        assert callable(caps.resolve_target(name))


def test_verifier_link_never_marks_whole_claim_passed(registry):
    states = {entry.id: caps.capability_check(entry) for entry in registry.entries.values()}
    assert all(check.claim_state in {"partially_checked", "not_checked"} for check in states.values())
    balance = states["chem.balancing"]
    assert balance.claim_state == "partially_checked"
    assert any("gerçekleştiğini" in text for text in balance.unchecked_tr)  # denkleşme tepkimeyi kanıtlamaz
    assert states["chem.balance-not-feasibility"].claim_state == "not_checked"
    units = caps.CAPABILITIES["reasoning.units.dimension"].does_not_prove_tr
    assert "yasa" in units
    assert "biyolojik işlevi" in caps.CAPABILITIES["reasoning.sequence.transcription"].does_not_prove_tr


# --- Öğretmen katkısı ve veri ayrımı --------------------------------------------------------------------------

CONTRIBUTION = {"schema_name": "teacherai.teacher_contribution", "version": "1.0.0", "contributor": "teacher:kimya-01",
                "role": "teacher", "subject": "chemistry", "submitted_on": "2026-12-01", "consent_use": True,
                "items": [{"kind": "common_error", "topic": "kimyasal_tepkimeler", "text_tr": "Alt indisi değiştirerek denkleştirmek.",
                           "grades": [10], "knowledge_ids": ["chem.balancing"]},
                          {"kind": "example_question", "topic": "mol_kavrami", "text_tr": "Özgün soru.",
                           "example": {"question_tr": "2 mol H₂O kaç mol H atomu içerir?", "answer_key_tr": "4", "original": True}}]}


def test_teacher_contribution_is_input_not_approval():
    contribution = TeacherContribution.model_validate(CONTRIBUTION)
    assert contribution.consent_model_training is False
    for bad in ({"contributor": "Ad Soyad"}, {"consent_use": False}):
        with pytest.raises(ValidationError):
            TeacherContribution.model_validate({**CONTRIBUTION, **bad})
    with pytest.raises(ValidationError):  # örnek soru anahtarsız olamaz
        TeacherContribution.model_validate({**CONTRIBUTION, "items": [{"kind": "example_question", "topic": "x", "text_tr": "y"}]})
    assert "reviews" not in TeacherContribution.model_fields and "status" not in TeacherContribution.model_fields


def test_evaluation_data_is_separated_from_generation_context():
    problems, report = dataset_manifest.run()
    assert problems == [] and report["overlaps"] == [] and report["heldout_questions"] == 24
    roles = {row["id"]: row for row in report["datasets"]}
    assert roles["teacher_answer_keys"]["status"] == "missing" and not roles["teacher_answer_keys"]["generation_context"]


def test_overlap_between_heldout_and_generation_records_is_reported(monkeypatch):
    question = dataset_manifest.heldout_texts()[0]
    monkeypatch.setattr(dataset_manifest, "generation_texts", lambda: [("sızıntı", question[1])])
    problems, report = dataset_manifest.run()
    assert report["overlaps"] and any("örtüşme" in problem for problem in problems)


def test_blank_teacher_template_matches_import_format_and_has_five_subject_templates():
    from pathlib import Path

    TeacherContribution.model_validate_json(Path("docs/teachers/contribution.template.json").read_text(encoding="utf-8"))
    for name in ("matematik", "fizik", "kimya", "biyoloji", "ortaokul-fen"):
        text = Path(f"docs/teachers/{name}.md").read_text(encoding="utf-8")
        assert "bağımsız cevap" in text.lower() or "Cevap anahtarı" in text
        assert "Sık yapılan öğrenci hataları" in text

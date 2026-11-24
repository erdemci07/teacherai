"""TA-006 bilimsel kaynak/bilgi kaydı, onay akışı, denetleyici sınırları ve veri ayrımı. Ağ ve sağlayıcı yoktur."""

from datetime import date

import pytest
from pydantic import ValidationError

from apps.api.app.features.education.base import Subject
from apps.api.app.features.education.contribution import TeacherContribution
from apps.api.app.features.education.knowledge import KnowledgeEntry, SourceRecord
from apps.api.app.features.knowledge import capabilities as caps
from apps.api.app.features.knowledge import registry as k
from scripts import dataset_manifest

REVIEW = {"reviewer": "teacher:fizik-ogretmeni-01", "role": "teacher", "reviewed_on": "2026-12-01", "reviewed_version": 1,
          "decision": "approve", "rationale_tr": "Koşullar ve sadeleştirme 10. sınıfa uygun."}


@pytest.fixture(scope="module")
def registry():
    return k.default_knowledge()


def approved(entry: KnowledgeEntry, **review) -> KnowledgeEntry:
    return KnowledgeEntry.model_validate({**entry.model_dump(), "status": "approved", "reviews": [{**REVIEW, **review}]})


def test_balanced_initial_dataset_is_sourced_draft_and_not_runtime_eligible(registry):
    rows = {row["subject"]: row for row in k.coverage(registry)}
    for subject in ("mathematics", "physics", "chemistry", "biology"):
        assert 15 <= rows[subject]["total"] <= 25
    assert rows["science"]["total"] >= 5
    assert all(entry.status == "draft" and entry.authored_by == "claude-draft" and not entry.reviews
               for entry in registry.entries.values())
    assert sum(row["runtime_eligible"] for row in rows.values()) == 0
    assert rows["mathematics"]["unsourced"] == ["math.polya-problem-solving"]


def test_no_fabricated_page_numbers_and_every_locator_points_to_verified_section(registry):
    for entry in registry.entries.values():
        for locator in entry.provenance:
            assert locator.page is None
            assert locator.verified_on == date(2026, 11, 24) and (locator.url or locator.section)


def test_biology_is_not_forced_into_equations(registry):
    biology = [entry for entry in registry.entries.values() if entry.subject == Subject.BIOLOGY]
    assert sum(1 for entry in biology if entry.representation) <= 2
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
    for bad in ({"reviewer": "claude:taslak"}, {"role": "project_owner"}, {"reviewed_version": 2}, {"decision": "source_verified"}):
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
    assert preview == ["phys.ohms-law", "phys.resistivity", "phys.series-parallel"]
    shown = k.preview(registry, "phys.ohms-law")
    assert "status:draft" in shown["runtime_blockers"] and shown["notice_tr"].startswith("TASLAK")


def test_approved_and_rights_clear_entry_becomes_eligible(registry):
    entry = approved(registry.entries["phys.ohms-law"])
    assert k.runtime_eligibility(entry, registry.sources) == []
    restricted = {**registry.sources, "openstax.university-physics-volume-2": registry.sources["iupac.gold-book"].model_copy(
        update={"id": "openstax.university-physics-volume-2"})}
    assert "rights_restricted:openstax.university-physics-volume-2" in k.runtime_eligibility(entry, restricted)
    custom = k.KnowledgeRegistry(sources=registry.sources, entries={**registry.entries, entry.id: entry}, digest="t")
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
    for bad in ({"contributor": "Ayşe Yılmaz"}, {"consent_use": False}):
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

"""TA-007: konu taksonomisi, denetimli geri getirme, MethodPolicy v2 çalışma zamanı, köken kaydı, değerlendirme
paketi içe aktarma, öğretmen formu/katkı yönetişimi ve inceleme içe aktarma. Ağ ve sağlayıcı çağrısı yoktur;
sentetik yetkiler yalnız bu yalıtılmış testlerde fikstürle verilir."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from apps.api.app.features.curriculum import context as selection
from apps.api.app.features.curriculum import methods, registry_v2, topics
from apps.api.app.features.education.base import Subject
from apps.api.app.features.education.contribution import ContributionRecord, TeacherContribution
from apps.api.app.features.education.curriculum_v2 import EducationalProvenance, MethodPolicyV2
from apps.api.app.features.education.knowledge import KnowledgeEntry, ReviewerAuthorization, content_digest
from apps.api.app.features.knowledge import registry as knowledge
from apps.api.app.features.knowledge import retrieval
from apps.api.app.features.knowledge import reviewers as reviewer_registry
from apps.api.app.features.lessons.schemas import Expression, Step
from apps.api.tests.test_curriculum import CLEAN, DERIVATIVE, Provider, authorize, linear_analysis
from apps.api.tests.test_question_integrity import analysis
from apps.api.tests.test_ta006_knowledge import seal_rights
from scripts import eval_import, eval_pack, review_import, teacher_contributions, teacher_forms

TODAY = date(2026, 11, 24)
ROOT = Path(__file__).resolve().parents[3]


def auth(reviewer, role, stage, subject="mathematics"):
    return ReviewerAuthorization(reviewer=reviewer, roles=[role], subjects=[subject], stages=[stage],
                                 valid_from=date(2026, 1, 1), authorized_by="owner:test-sahip",
                                 authorized_on=date(2026, 1, 1), evidence_note_tr="Yalnız yalıtılmış test fikstürü.")


# --- Üretim verisi: uydurma onay yok ---------------------------------------------------------------------------

def test_production_registry_has_no_synthetic_or_real_approvals():
    assert reviewer_registry.load() == ()
    registry = knowledge.default_knowledge()
    assert all(entry.status == "draft" and not entry.reviews and entry.rights.decision == "pending"
               for entry in registry.entries.values())
    assert all(p.status == "draft" for p in methods.all_policies())
    assert not (ROOT / "data/contributions/register.json").exists() or \
        teacher_contributions.load_register().records == []


def test_audit_covers_all_74_original_drafts_and_revisions_keep_history():
    audit = json.loads((ROOT / "apps/api/app/features/knowledge/audit/TA-007-draft-audit.json").read_text(encoding="utf-8"))
    rows = audit["rows"] if "rows" in audit else audit["entries"]
    registry = knowledge.default_knowledge()
    assert len(rows) == 74 and len({row["entry_id"] for row in rows}) == 74
    for row in rows:
        entry = registry.entries[row["entry_id"]]
        assert entry.version == row["version_after"]
        if row["action"] == "revised":
            assert entry.revisions and entry.revisions[-1].version == entry.version
            assert entry.revisions[-1].previous_json  # önceki sürüm korunur
        assert entry.status == "draft"  # AI ön incelemesi onay değildir


# --- Konu taksonomisi --------------------------------------------------------------------------------------------

def q(text, expressions=()):
    return analysis(question_text=text, mathematical_expressions=list(expressions) or ["x"],
                    answer_choices=["A) 1", "B) 2", "C) 3", "D) 4"])


def test_structure_beats_words_and_is_the_only_certain_topic():
    mapping = topics.map_question(linear_analysis(), Subject.MATHEMATICS)
    assert mapping.status == "structural" and mapping.certain == "dogrusal_denklemler"
    # TA-008: taksonomiye "açılar" konusu eklendiği için iç açı sözü artık iki konuya düşer; tek konulu örnek seçildi.
    lexical = topics.map_question(SimpleNamespace(question_text="Üçgenin çevresi", integrity=None), Subject.MATHEMATICS)
    assert lexical.status == "single" and lexical.certain is None and lexical.keys == ("ucgenler",)


def test_turkish_suffixes_ambiguity_and_subject_isolation():
    text = SimpleNamespace(question_text="Çözeltinin pH değeri ve derişimi", integrity=None)
    mapping = topics.map_question(text, Subject.CHEMISTRY)
    assert mapping.status == "ambiguous" and set(mapping.keys) >= {"asit_baz", "cozeltiler"}
    assert topics.map_question(text, Subject.PHYSICS).keys == ()  # alanlar arası bulaşma yok
    # Kısa takma ad başka sözcüğün öneki olarak eşleşmez ("tür" → "türev" değil).
    assert "limit_turev" in topics.map_question(SimpleNamespace(question_text="Türevi alınırsa", integrity=None),
                                                Subject.MATHEMATICS).keys
    assert topics.map_question(SimpleNamespace(question_text="İşlem sonucu kaçtır?", integrity=None),
                               Subject.MATHEMATICS).status == "none"


def test_taxonomy_validation_rejects_bad_records(tmp_path):
    good = json.loads(topics.DATA.read_text(encoding="utf-8"))
    for broken in ({"key": "kesirler"}, {"outcome_pattern": "("}, {"prerequisites": ["yok_boyle"]}, {"key": "Büyük"}):
        data = {**good, "topics": [*good["topics"], {**good["topics"][1], **broken}]}
        path = tmp_path / "t.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(topics.TaxonomyError):
            topics.load(path)


def test_taxonomy_coverage_is_reported_honestly():
    report = topics.coverage(registry_v2.default_registry(), knowledge.default_knowledge())
    assert report["unmapped_knowledge_topics"] == []
    assert {row["program_id"] for row in report["programs"]} >= {"meb-2018.matematik.1-8", "tymm-2026.kimya.9-12"}
    assert any(row["mapped"] < row["outcomes"] for row in report["programs"])  # eksik kapsam gizlenmez


# --- Denetimli geri getirme --------------------------------------------------------------------------------------

def eligible_registry(*entry_ids, mutate=None):
    registry = knowledge.default_knowledge()
    entries = dict(registry.entries)
    reviewers = (auth("teacher:t-ogretmen", "teacher", "scientific", "physics"),
                 auth("teacher:t-ogretmen", "teacher", "scientific"),
                 auth("owner:test-sahip", "project_owner", "rights", "physics"),
                 auth("owner:test-sahip", "project_owner", "rights"))
    for entry_id in entry_ids:
        base = entries[entry_id]
        if mutate:
            base = KnowledgeEntry.model_validate({**base.model_dump(), **mutate})
        review = {"reviewer": "teacher:t-ogretmen", "role": "teacher", "reviewed_on": "2026-12-01",
                  "reviewed_version": base.version, "decision": "approve", "rationale_tr": "Test.",
                  "stage": "scientific", "content_digest": content_digest(base)}
        rights = {"source_use": "independent_fact", "basis_tr": "Özgün anlatım.", "decision": "approved",
                  "decided_by": "owner:test-sahip", "decided_on": "2026-12-02"}
        entries[entry_id] = seal_rights(KnowledgeEntry.model_validate({**base.model_dump(), "status": "approved",
                                                                       "reviews": [review], "rights": rights}))
    return knowledge.KnowledgeRegistry(sources=registry.sources, entries=entries, digest=f"t{len(entry_ids)}",
                                       reviewers=reviewers)


def test_production_mode_excludes_drafts_and_records_why():
    result = retrieval.retrieve(knowledge.default_knowledge(), Subject.PHYSICS, topic_keys=["elektrik"])
    assert result.context == () and result.excluded
    assert {item.reason for item in result.excluded} == {"not_runtime_eligible"}


def test_preview_includes_drafts_but_can_never_enter_the_prompt():
    result = retrieval.retrieve(knowledge.default_knowledge(), Subject.PHYSICS, topic_keys=["elektrik"], mode="preview")
    assert result.context and all(item.blockers for item in result.selected) and result.notice_tr.startswith("TASLAK")
    with pytest.raises(ValueError):
        retrieval.as_context(result)


def test_oversized_record_is_excluded_not_truncated_and_compaction_is_recorded():
    registry = eligible_registry("phys.ohms-law")
    entry = registry.entries["phys.ohms-law"]
    tiny = retrieval.Budget(max_entries=3, max_record_bytes=120, max_total_bytes=2000)
    result = retrieval.retrieve(registry, Subject.PHYSICS, topic_keys=["elektrik"], budget=tiny)
    assert result.context == () and any(item.id == entry.id and item.reason == "exceeds_record_budget"
                                        for item in result.excluded)
    full = retrieval.retrieve(registry, Subject.PHYSICS, topic_keys=["elektrik"])
    sent = full.context[0]
    assert sent.conditions_tr == list(entry.conditions_tr) and sent.exceptions_tr == list(entry.exceptions_tr)
    assert full.refs[0].version == entry.version and full.refs[0].content_digest == content_digest(entry)


def test_relationships_and_lexical_overlap_never_fetch_alone():
    registry = knowledge.default_knowledge()
    assert retrieval.candidates(registry, Subject.PHYSICS, query="Ohm yasası direnç akım gerilim") == []
    rows = retrieval.candidates(registry, Subject.PHYSICS, topic_keys=["elektrik"])
    assert rows == retrieval.candidates(registry, Subject.PHYSICS, topic_keys=["elektrik"])  # belirlenimci
    assert all(entry.subject == Subject.PHYSICS for entry, *_ in rows)


def test_selection_records_provenance_versions_and_exclusions():
    registry = eligible_registry("math.equation-equivalence")
    chosen = selection.select(linear_analysis(), Subject.MATHEMATICS, 8, today=TODAY, knowledge=registry)
    provenance = chosen.provenance
    assert provenance.selection_mode == "deterministic_production" and provenance.topic_mapping == "structural"
    assert [ref.id for ref in provenance.knowledge_refs] == provenance.knowledge_ids == ["math.equation-equivalence"]
    assert any(item.reason == "not_runtime_eligible" for item in provenance.excluded_knowledge)
    assert chosen.payload.methods == []  # taslak politika isteme girmez


# --- Köken: seçilen ve gerçekten gönderilen ---------------------------------------------------------------------

def test_transmission_distinguishes_selected_from_sent_and_never_rewrites():
    registry = eligible_registry("math.equation-equivalence")
    provenance = selection.select(linear_analysis(), Subject.MATHEMATICS, 8, today=TODAY, knowledge=registry).provenance
    normal = selection.with_transmission(provenance, ["normal"])
    assert normal.transmission == "normal" and normal.transmitted_knowledge_ids == ["math.equation-equivalence"]
    emergency = selection.with_transmission(provenance, ["normal", "emergency"])
    assert emergency.transmission == "mixed" and emergency.transmitted_knowledge_ids == []
    assert emergency.knowledge_ids == ["math.equation-equivalence"]  # seçim kaydı korunur
    assert selection.with_transmission(provenance, [None]).transmission is None  # bildirilmeyen düzey uydurulmaz
    with pytest.raises(ValidationError):
        EducationalProvenance.model_validate({**provenance.model_dump(), "transmitted_knowledge_ids": ["baska.girdi"]})


class EmergencyProvider(Provider):
    async def generate_lesson_plan(self, *args, **kwargs):
        result = await super().generate_lesson_plan(*args, **kwargs)
        return type(result)(result.draft, result.provider, result.model, context_level="emergency")


@pytest.mark.asyncio
async def test_lesson_records_emergency_transmission_without_extra_call():
    from apps.api.app.features.board.planner import BoardPlanner
    from apps.api.app.features.education.domain import Grade
    from apps.api.app.features.lessons.service import LessonService
    from apps.api.app.features.mathai.service import MathAIService

    provider = EmergencyProvider(CLEAN)
    result = await LessonService(provider, MathAIService(), BoardPlanner(), clock=lambda: TODAY).generate(
        linear_analysis(), grade=Grade(value=8, origin="declared"))
    assert len(provider.feedback) == 1
    assert result.educational_provenance.transmission == "emergency"
    assert result.educational_provenance.transmitted_knowledge_ids == []


# --- MethodPolicy v2 -----------------------------------------------------------------------------------------------

def policy(**update) -> MethodPolicyV2:
    base = MethodPolicyV2(id="t.v2.genel", subject=Subject.MATHEMATICS, topic="genel", program_ids=["meb-2018.matematik.1-8"],
                          grades=[8], forbidden_operations=[{"operation": "derivative", "reason": "Türev 8. sınıfta yok."}],
                          status="draft", authored_by="teacher")
    data = {**base.model_dump(), **update}
    if data["status"] == "approved":
        draft = MethodPolicyV2.model_validate({**data, "status": "draft", "approved_by": None})
        data.setdefault("approval_digest", None)
        data["approval_digest"] = data["approval_digest"] or methods.policy_digest(draft)
    return MethodPolicyV2.model_validate(data)


APPROVED = {"status": "approved", "approved_by": "teacher:test-ogretmen", "approved_on": date(2026, 1, 15)}
TEACHER = auth("teacher:test-ogretmen", "teacher", "pedagogical")


@pytest.mark.parametrize(("update", "reviewers", "reason"), [
    ({}, (TEACHER,), "draft"),
    ({**APPROVED, "approved_on": None}, (TEACHER,), "approval_incomplete"),
    (APPROVED, (), "reviewer_not_authorized"),
    (APPROVED, (auth("teacher:test-ogretmen", "teacher", "scientific"),), "reviewer_not_authorized"),
    ({**APPROVED, "approval_digest": "0" * 64}, (TEACHER,), "stale_approval"),
    (APPROVED, (TEACHER,), None),
])
def test_policy_activation_requires_authorized_current_approval(update, reviewers, reason):
    assert methods.inactive_reason(policy(**update), reviewers) == reason


def test_revoked_authorization_and_unauthorized_dates_do_not_activate():
    revoked = TEACHER.model_copy(update={"revoked_on": date(2026, 1, 10)})
    assert methods.inactive_reason(policy(**APPROVED), (revoked,)) == "reviewer_not_authorized"


def mapping(status, *keys):
    evidence = "structure" if status == "structural" else "alias"
    return topics.TopicMapping(status, tuple(topics.Candidate(key, evidence, ()) for key in keys))


def resolution(program_ids, status="resolved"):
    return registry_v2.resolve(registry_v2.default_registry(), Subject.MATHEMATICS, 8, today=TODAY).model_copy(
        update={"status": status, "program_ids": program_ids if status == "resolved" else [],
                "candidate_program_ids": program_ids})


def policy_set(policies, mapped, resolved, monkeypatch):
    monkeypatch.setattr(methods, "all_policies", lambda curriculum=None: list(policies))
    return methods.select(resolved, mapped, Subject.MATHEMATICS, 8, reviewers=(TEACHER,))


def derivative_plan():
    return SimpleNamespace(content=SimpleNamespace(steps=list(DERIVATIVE)), source_analysis=linear_analysis())


class NoChecks:
    checks = []


def test_forbidden_strong_evidence_fails_and_advanced_request_does_not(monkeypatch):
    chosen = policy_set([policy(**APPROVED)], mapping("structural", "dogrusal_denklemler"),
                        resolution(["meb-2018.matematik.1-8"]), monkeypatch)
    failed = methods.method_check(derivative_plan(), NoChecks(), 8, chosen)
    assert failed.state == "failed" and failed.operations == ["derivative"] and failed.evidence[0].used
    advanced = methods.method_check(derivative_plan(), NoChecks(), 8, chosen, advanced_requested=True)
    assert (advanced.state, advanced.reason) == ("partially_checked", "advanced_method_requested")


def test_ambiguous_program_enforces_only_common_prohibitions(monkeypatch):
    only_2018 = policy(**APPROVED)
    chosen = policy_set([only_2018], mapping("structural", "dogrusal_denklemler"),
                        resolution(["meb-2018.matematik.1-8", "tymm-2026.matematik.5-8"], "ambiguous"), monkeypatch)
    check = methods.method_check(derivative_plan(), NoChecks(), 8, chosen)
    assert check.state != "failed"  # yasak yalnız bir aday programda: kesin hüküm yok


def test_lexical_topic_never_passes_and_rejected_mentions_are_recorded(monkeypatch):
    topical = policy(id="t.v2.lineer", topic="dogrusal_denklemler", forbidden_operations=[],
                     allowed_operations=["subtract_both_sides", "divide_both_sides", "isolate_variable", "state_result", "explain"],
                     **APPROVED)
    chosen = policy_set([topical], mapping("single", "dogrusal_denklemler"), resolution(["meb-2018.matematik.1-8"]), monkeypatch)
    step = Step(id="step_1", type="explanation", title="Yöntem", explanation="Türev kullanmadan çözelim.", expressions=[])
    plan = SimpleNamespace(content=SimpleNamespace(steps=[step]), source_analysis=linear_analysis())
    check = methods.method_check(plan, NoChecks(), 8, chosen)
    assert check.state == "partially_checked" and check.reason == "topic_uncertain"
    assert check.evidence[0].rejected == ["derivative"] and check.evidence[0].mentioned == []


def test_unparsed_expression_is_outside_verification(monkeypatch):
    step = Step(id="step_1", type="transformation", title="Adım", explanation="Devam.",
                expressions=[Expression(type="equation", latex="\\frac{")])
    plan = SimpleNamespace(content=SimpleNamespace(steps=[step]), source_analysis=linear_analysis())
    assert methods.evidence(plan, NoChecks())[0].unparsed == 1


@pytest.mark.asyncio
async def test_lesson_flow_uses_v2_and_never_contradicts_itself(monkeypatch):
    authorize(monkeypatch)
    from apps.api.app.features.board.planner import BoardPlanner
    from apps.api.app.features.education.domain import Grade
    from apps.api.app.features.lessons.service import LessonService
    from apps.api.app.features.mathai.service import MathAIService

    provider = Provider(DERIVATIVE, CLEAN)
    result = await LessonService(provider, MathAIService(), BoardPlanner(), clock=lambda: TODAY).generate(
        linear_analysis(), grade=Grade(value=8, origin="declared"))
    assert result.method_check.policy_ids and all(pid.startswith("meb-2018.matematik.1-8.") for pid in result.method_check.policy_ids)
    assert result.educational_provenance.method_policy_ids == result.method_check.policy_ids
    assert result.method_check.state == "passed" and result.curriculum_check.state == "passed"


def test_curriculum_check_v2_states():
    curriculum = registry_v2.default_registry()
    resolved = registry_v2.resolve(curriculum, Subject.MATHEMATICS, 8, today=TODAY)
    exact = selection.match_outcomes(curriculum, resolved.program_ids[0], 8, mapping("structural", "dogrusal_denklemler"))
    assert methods.curriculum_check(resolved, mapping("structural", "dogrusal_denklemler"), 8, exact).state == "passed"
    lexical = selection.match_outcomes(curriculum, resolved.program_ids[0], 8, mapping("single", "dogrusal_denklemler"))
    assert methods.curriculum_check(resolved, mapping("single", "dogrusal_denklemler"), 8, lexical).reason == "topic_lexical_only"
    assert methods.curriculum_check(resolved, mapping("structural", "limit_turev"), 8, []).reason == "topic_not_found_in_program"
    assert methods.curriculum_check(None, mapping("none"), None, []).reason == "grade_unknown"


# --- İzlek ve sınav hedefi ------------------------------------------------------------------------------------------

def test_science_high_school_only_by_explicit_track_and_multiple_exams_kept():
    curriculum = registry_v2.default_registry()
    general = selection.select(linear_analysis(), Subject.MATHEMATICS, 12, today=TODAY, curriculum=curriculum)
    assert general.resolution.program_ids == ["meb-2018.matematik.9-12"]
    assert "track_unspecified_general_assumed" in general.resolution.reasons
    science = selection.select(linear_analysis(), Subject.MATHEMATICS, 12, today=TODAY, track="science_high_school")
    assert science.resolution.program_ids == ["meb-2018.fen-lisesi-matematik.9-12"]
    graduate = selection.select(linear_analysis(), Subject.MATHEMATICS, None, today=TODAY, exam_goal="Mezunum, YKS'ye hazırlanıyorum")
    assert graduate.resolution.learner_status == "graduate" and graduate.resolution.exams == ["TYT", "AYT"]
    assert graduate.resolution.grade is None and graduate.payload is None


def test_profile_keeps_school_track_when_omitted():
    from apps.api.app.features.students.schemas import ProfileInput, StudentProfile
    from apps.api.app.features.students.service import StudentService

    class Repo:
        profile = None

        def get_profile(self, uid):
            return self.profile

        def save_profile(self, value):
            self.profile = value

    repo = Repo()
    service = StudentService(repo, None)
    user = SimpleNamespace(uid="u1", email=None)
    service.profile(user, ProfileInput(display_name="A", grade=12, school_track="science_high_school"))
    service.profile(user, ProfileInput(display_name="A", grade=12))
    assert repo.profile.school_track == "science_high_school"
    assert service.learner(user)[3] == "science_high_school"
    assert StudentProfile(student_id="x", display_name="y").school_track is None


# --- Değerlendirme paketi -----------------------------------------------------------------------------------------

PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (10).to_bytes(4, "big") + (10).to_bytes(4, "big")
       + b"\x08\x02\x00\x00\x00" + b"\x00" * 4 + b"\x00\x00\x00\x00IEND\xaeB`\x82")
IDS = ["M01", "P01"]


def make_zip(tmp_path, files, manifest=None, questions=None, name="p.zip"):
    path = tmp_path / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file, data in files.items():
            archive.writestr(file, data)
        if manifest is not False:
            import hashlib
            rows = manifest or [{"file": file, "sha256": hashlib.sha256(data).hexdigest(),
                                 "kind": "ocr_variant" if "_" in file.rsplit("/", 1)[-1] else "base"}
                                for file, data in files.items() if file.startswith("images/")]
            archive.writestr("manifest.json", json.dumps(rows))
        if questions is not None:
            archive.writestr("sorular.jsonl", "\n".join(json.dumps(row) for row in questions))
    return path


def test_valid_package_groups_variants_and_writes_only_inside_target(tmp_path):
    files = {"images/M01.png": PNG, "images/P01.png": PNG + b"", "images/M01_light_blur.png": PNG}
    report, images = eval_import.inspect(make_zip(tmp_path, files, questions=[{"id": i, "question": "?"} for i in IDS]), IDS)
    assert report.ok and set(report.base) == set(IDS) and report.variants["M01"][0]["variant"] == "light_blur"
    target = tmp_path / "out"
    eval_import.write(report, images, target)
    assert sorted(path.name for path in target.iterdir()) == ["M01.png", "M01_light_blur.png", "P01.png"]
    manifest, variants = eval_import.manifests(report)
    assert [row["question_id"] for row in variants["variants"]] == ["M01"]
    assert sum(1 for row in manifest["images"] if row.get("kind") == "ocr_variant") == 1


@pytest.mark.parametrize(("files", "questions", "fragment"), [
    ({"../evil.png": PNG}, None, "yol aşımı"),
    ({"images/../../evil.png": PNG}, None, "yol aşımı"),
    ({"C:/evil.png": PNG}, None, "Windows"),
    ({"images/M01.png": b"GIF89a" + b"\x00" * 40, "images/P01.png": PNG}, None, "PNG"),
    ({"images/M01.png": PNG}, None, "Özgün görseli olmayan soru"),
    ({"images/M01.png": PNG, "images/P01.png": PNG, "images/B09_blur.png": PNG}, None, "varyant"),
    ({"images/M01.png": PNG, "images/P01.png": PNG}, [{"id": "M01", "answer": "C"}, {"id": "P01"}], "cevap alanı"),
    ({"images/M01.png": PNG, "images/P01.png": PNG, "notes/x.txt": b"x"}, None, "izinli"),
])
def test_unsafe_or_inconsistent_packages_are_rejected(tmp_path, files, questions, fragment):
    report, _ = eval_import.inspect(make_zip(tmp_path, files, questions=questions), IDS)
    assert not report.ok and any(fragment in problem for problem in report.problems), report.problems


def test_hash_mismatch_and_zip_bomb_are_rejected(tmp_path):
    files = {"images/M01.png": PNG, "images/P01.png": PNG}
    bad = [{"file": "images/M01.png", "sha256": "0" * 64, "kind": "base"},
           {"file": "images/P01.png", "sha256": "0" * 64, "kind": "base"}]
    report, _ = eval_import.inspect(make_zip(tmp_path, files, manifest=bad), IDS)
    assert any("sha256" in problem for problem in report.problems)
    bomb = make_zip(tmp_path, {"images/M01.png": PNG + b"\x00" * 2_000_000, "images/P01.png": PNG}, name="b.zip")
    report, _ = eval_import.inspect(bomb, IDS)
    assert any("oran" in problem for problem in report.problems)
    with pytest.raises(ValueError):
        eval_import.write(report, {}, tmp_path / "x")


def test_pack_plan_never_counts_variants_as_separate_samples(tmp_path):
    import hashlib
    images = tmp_path / "img"
    images.mkdir()
    (images / "M01.png").write_bytes(PNG)
    (images / "M01_light_blur.png").write_bytes(PNG + b"1")
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"images": [
        {"file": "M01.png", "sha256": hashlib.sha256(PNG).hexdigest(), "question_id": "M01"},
        {"file": "M01_light_blur.png", "sha256": hashlib.sha256(PNG + b"1").hexdigest(), "question_id": "M01",
         "kind": "ocr_variant"}]}), encoding="utf-8")
    runs, missing = eval_pack.plan(manifest, images)
    assert len(runs) == 1 and runs[0]["variants"][0].name == "M01_light_blur.png" and len(missing) == 23


# --- Öğretmen Word formu ve katkı yönetişimi ---------------------------------------------------------------------

def docx(tmp_path, paragraphs, name="form.docx"):
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    xml = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return path


def form(identity="teacher:mat-ogretmen / öğretmen / 2026-12-05", consent="Evet", training="Hayır (varsayılan)",
         answer="x = 4; iki taraftan 7 çıkar, 3'e böl.", extra=()):
    return ["Matematik ve geometri", "Takma ad / rol / tarih:  teacher:… veya expert:…", identity,
            "Düzey ve program:  5–12. sınıf", "8. sınıf, MEB 2018", "Seçtiğiniz konu ve kazanım (biliniyorsa):", "Denklem",
            "1  |  Bilinmeyen soruya yaklaşım", "İlk inceleme ve çözüm planı:  …", "Önce bilinmeyeni sorarım.",
            "2  |  Öğrenci hataları ve yöntem", "Sık hata → nedeni → öğrenciye fark ettirecek soru:", "[Buraya yazınız.]",
            "5  |  Özgün soru ve öğretmen çözümü", "Özgün soru (varsa kendi çiziminizi ayrı ekleyin):", "3x + 7 = 19 ise x kaçtır?",
            "Bağımsız cevap ve kısa gerekçeli çözüm:", *([answer] if answer else ["[Buraya yazınız.]"]),
            "6  |  Kullanım izni ve teslim",
            f"Katkımın Teacher AI içinde, ticari kullanım dahil, düzenlenerek kullanılmasına izin veriyorum:  {consent}",
            f"Model ağırlıklarının eğitimi veya fine-tuning için ayrı izin:  {training}", *extra]


def test_filled_form_becomes_draft_contribution_without_inventing_answers(tmp_path):
    record, problems = teacher_forms.convert(docx(tmp_path, form()))
    assert problems == [] and record["contributor"] == "teacher:mat-ogretmen" and record["consent_model_training"] is False
    kinds = [item["kind"] for item in record["items"]]
    assert kinds == ["unfamiliar_question_approach", "example_question"]  # boş alan öğe üretmez
    assert record["items"][1]["example"]["answer_key_tr"].startswith("x = 4") and record["items"][0]["topic"] == "dogrusal_denklemler"
    TeacherContribution.model_validate(record)


@pytest.mark.parametrize(("kwargs", "fragment"), [
    ({"consent": "Evet / Hayır (birini bırakınız)"}, "Kullanım izni"),
    ({"identity": "teacher:a-01 ve teacher:b-02 / 2026-12-05"}, "Takma ad"),
    ({"identity": "teacher:mat-ogretmen / öğretmen"}, "Tarih"),
    ({"answer": None}, "bağımsız öğretmen cevabı"),
    ({"extra": ["Ek not", "ogretmen@example.com"]}, None),
])
def test_ambiguous_or_unsafe_forms_are_not_imported(tmp_path, kwargs, fragment):
    paragraphs = form(**kwargs)
    if kwargs.get("extra"):
        paragraphs = form()
        paragraphs[9] = "Önce bilinmeyeni sorarım. İletişim: ogretmen@example.com"
        fragment = "Kişisel bilgi"
    record, problems = teacher_forms.convert(docx(tmp_path, paragraphs))
    assert record is None and any(fragment in problem for problem in problems), problems


def contribution_record(contribution, *stages, by=None, digest=None):
    digest = digest or teacher_contributions.contribution_digest(contribution)
    roles = {"normalized": ("owner:test-sahip", "project_owner"), "source_verified": ("expert:kaynak-01", "subject_expert"),
             "scientific_review": ("expert:bilim-01", "subject_expert"), "pedagogical_review": ("teacher:pedagoji-01", "teacher"),
             "rights_approved": ("owner:test-sahip", "project_owner"), "published": ("owner:test-sahip", "project_owner"),
             "withdrawn": ("owner:test-sahip", "project_owner")}
    events = [{"stage": "submitted", "on": "2026-12-01", "by": contribution.contributor, "role": "teacher", "content_digest": digest}]
    for index, stage in enumerate(stages, 2):
        ref, role = (by or {}).get(stage, roles[stage])
        events.append({"stage": stage, "on": f"2026-12-{index:02d}", "by": ref, "role": role, "content_digest": digest})
    return ContributionRecord(contribution_id="c1", path="teacher-mat-ogretmen-c1.json", events=events)


GOVERNANCE = (auth("owner:test-sahip", "project_owner", "publication"), auth("owner:test-sahip", "project_owner", "rights"),
              auth("expert:kaynak-01", "subject_expert", "source_verification"),
              auth("expert:bilim-01", "subject_expert", "scientific"), auth("teacher:pedagoji-01", "teacher", "pedagogical"),
              auth("teacher:mat-ogretmen", "teacher", "scientific"))
STAGES = ("normalized", "source_verified", "scientific_review", "pedagogical_review", "rights_approved", "published")


def test_contribution_publication_gates(tmp_path):
    record, _ = teacher_forms.convert(docx(tmp_path, form()))
    contribution = TeacherContribution.model_validate(record)
    full = contribution_record(contribution, *STAGES)
    assert teacher_contributions.publication_blockers(full, contribution, GOVERNANCE) == []
    assert "missing:rights_approved" in teacher_contributions.publication_blockers(
        contribution_record(contribution, *STAGES[:4]), contribution, GOVERNANCE)
    self_review = contribution_record(contribution, *STAGES, by={"scientific_review": ("teacher:mat-ogretmen", "teacher")})
    assert "not_independent:scientific_review" in teacher_contributions.publication_blockers(self_review, contribution, GOVERNANCE)
    stale = contribution_record(contribution, *STAGES, digest="f" * 64)
    assert "stale:published" in teacher_contributions.publication_blockers(stale, contribution, GOVERNANCE)
    assert "not_authorized:published" in teacher_contributions.publication_blockers(full, contribution, ())
    withdrawn = contribution_record(contribution, *STAGES, "withdrawn")
    assert "stage:withdrawn" in teacher_contributions.publication_blockers(withdrawn, contribution, GOVERNANCE)
    assert teacher_contributions.training_allowed(withdrawn, contribution.model_copy(update={"consent_model_training": True})) is False
    with pytest.raises(ValidationError):  # geri çekme sonrası aşama eklenemez
        ContributionRecord.model_validate({**withdrawn.model_dump(mode="json"),
                                           "events": [*withdrawn.model_dump(mode="json")["events"],
                                                      {**withdrawn.model_dump(mode="json")["events"][-1], "stage": "published"}]})


# --- İnceleme formu içe aktarma -----------------------------------------------------------------------------------

def review_csv(tmp_path, rows):
    import csv
    path = tmp_path / "r.csv"
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=review_import.KNOWLEDGE_HEADER, delimiter=";")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in review_import.KNOWLEDGE_HEADER})
    path.write_text("﻿" + buffer.getvalue(), encoding="utf-8")
    return path


def test_review_import_rejects_unauthorized_stale_and_ambiguous_rows(tmp_path):
    entry = knowledge.default_knowledge().entries["phys.ohms-law"]
    revised = next(e for e in knowledge.default_knowledge().entries.values() if e.version > 1)
    row = {"kayit_id": entry.id, "surum": str(entry.version), "inceleyen_takma_ad": "teacher:fizik-01", "rol": "öğretmen",
           "tarih": "2026-12-03", "karar": "approve", "gerekce_ve_kaynak": "Kaynak bölümü doğrulandı."}
    path = review_csv(tmp_path, [row, {**row, "kayit_id": revised.id, "surum": "1"}, {**row, "karar": "belki"},
                                 {**row, "karar": "not_reviewed"}, {**row, "karar": ""}])
    _, accepted, problems = review_import.validate(path, reviewers=())
    assert accepted == [] and any("yetkili değil" in p for p in problems) and any("bayat" in p for p in problems)
    assert any("tanımsız karar" in p for p in problems)
    _, accepted, problems = review_import.validate(review_csv(tmp_path, [row]),
                                                   reviewers=(auth("teacher:fizik-01", "teacher", "scientific", "physics"),))
    assert problems == [] and accepted[0]["review"].content_digest == content_digest(entry)
    approved = KnowledgeEntry.model_validate({**entry.model_dump(), "status": "approved",
                                              "reviews": [accepted[0]["review"].model_dump()]})
    assert "rights_decision:pending" in knowledge.runtime_eligibility(approved, knowledge.default_knowledge().sources)

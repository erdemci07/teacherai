"""TA-006 Müfredat Kaydı v2: veri, göç, doğrulama, program çözümleme ve gözatma. Ağ ve sağlayıcı çağrısı yoktur."""

from dataclasses import replace
from datetime import date

import pytest

from apps.api.app.features.curriculum import registry as legacy
from apps.api.app.features.curriculum import registry_v2 as r
from apps.api.app.features.education.base import Subject
from apps.api.app.features.education.curriculum import CurriculumRegistry
from apps.api.app.features.education.curriculum_v2 import ProgramFile
from apps.api.app.main import create_app
from apps.api.tests.client import authenticated_client
from scripts import curriculum_extract

TODAY = date(2026, 11, 24)
EMPTY_V1 = CurriculumRegistry(schema_name="teacherai.curriculum_registry", version="1.0.0", program_note="boş")


@pytest.fixture(scope="module")
def registry():
    return r.default_registry()


def resolve(registry, subject=Subject.MATHEMATICS, grade=None, **kwargs):
    return r.resolve(registry, subject, grade, today=kwargs.pop("today", TODAY), **kwargs)


# --- Veri ve göç --------------------------------------------------------------------------------------------------

def test_inventory_matches_every_official_count_that_could_be_read(registry):
    checked = 0
    for program in registry.catalog.programs:
        for expected in program.expected_counts:
            assert len(registry.outcomes_for(program.id, expected.grade)) == expected.count, (program.id, expected.grade)
            checked += 1
    assert checked >= 30
    assert {item.subject for item in registry.programs.values()} == {
        Subject.MATHEMATICS, Subject.SCIENCE, Subject.PHYSICS, Subject.CHEMISTRY, Subject.BIOLOGY}


def test_unknown_expected_counts_stay_unknown(registry):
    rows = {(row["program_id"], row["grade"]): row for row in r.coverage(registry)}
    assert rows[("tymm-2026.kimya.9-12", 9)]["expected"] is None and rows[("tymm-2026.kimya.9-12", 9)]["missing"] is None
    assert rows[("meb-2018.matematik.1-8", 8)]["missing"] == 0


def test_v1_migration_is_deterministic_and_preserves_29_outcomes_and_policies(registry):
    again = r.load()
    assert again.digest == registry.digest and again.outcomes == registry.outcomes
    v1 = legacy.default_registry()
    for item in v1.outcomes:
        migrated = registry.outcomes[r.legacy_global_id(item.outcome_id)]
        assert migrated.official_text_tr == item.outcome_text_tr and migrated.grade == item.grade
        assert item.topic in {migrated.topic_key, *migrated.aliases}
    assert sum(1 for item in registry.outcomes.values() if item.official_text_tr) == len(v1.outcomes) == 29
    migrated_policies = [p for p in registry.policies if p.legacy_id]
    assert sorted(p.legacy_id for p in migrated_policies) == sorted(p.id for p in v1.policies)
    assert all(p.status == "draft" and p.approved_by is None for p in migrated_policies)
    # v1 sözleşmesi ve yöntem denetimi değişmeden çalışır.
    assert legacy.default_registry() is v1


def test_same_official_code_in_different_programs_does_not_collide(registry):
    ids = sorted(identifier for (program, code), identifier in registry.by_code.items() if code == "9.1.1.1")
    assert len(ids) == 4 and len(set(ids)) == 4
    assert all(identifier.endswith("::9.1.1.1") for identifier in ids)


def test_official_text_only_on_legacy_records_and_new_records_carry_page_and_heading(registry):
    for item in registry.outcomes.values():
        assert item.page >= 1 and item.unit_id in registry.units
        if item.official_text_tr:
            assert item.program_id == r.LEGACY_PROGRAM and item.grade == 8
        if item.description_tr:
            assert item.description_review == "unreviewed"
        assert item.review_status == "unreviewed"  # bağımsız insan incelemesi yapılmadı


def test_geometry_is_a_discipline_inside_mathematics(registry):
    pythagoras = registry.outcomes["tymm-2026.matematik.5-8::MAT.8.3.5"]
    assert pythagoras.subject == Subject.MATHEMATICS and pythagoras.discipline == Subject.GEOMETRY
    algebra = registry.outcomes["meb-2018.matematik.1-8::M.8.2.1.3"]  # "Özdeşlikler" geometri sayılmaz
    assert algebra.discipline == Subject.MATHEMATICS


# --- Doğrulama ----------------------------------------------------------------------------------------------------

def _catalog(registry, *program_ids):
    return registry.catalog.model_copy(update={
        "programs": [p for p in registry.catalog.programs if p.id in program_ids],
        "application": [], "exam_scopes": [], "policies": []})


def _file(program_id, units, outcomes):
    return ProgramFile(schema_name="teacherai.curriculum_program", version="2.0.0", program_id=program_id,
                       extraction_tool="test", units=units, outcomes=outcomes)


def _small(registry, program_id="tymm-2026.matematik.9-12", codes=("MAT.9.1.1", "MAT.9.1.2")):
    outcomes = [registry.outcomes[registry.by_code[(program_id, code)]] for code in codes]
    units = [registry.units[item.unit_id] for item in outcomes]
    return list({unit.id: unit for unit in units}.values()), outcomes


def test_validation_reports_duplicates_unknown_refs_cycles_and_version_mismatch(registry):
    units, outcomes = _small(registry)
    first, second = outcomes
    cases = {
        "Yinelenen kazanım": [first, first],
        "Tanımsız ön koşul": [first.model_copy(update={"prerequisites": ["tymm-2026.matematik.9-12::MAT.9.9.9"]})],
        "Ön koşul döngüsü": [first.model_copy(update={"prerequisites": [second.id]}),
                             second.model_copy(update={"prerequisites": [first.id]})],
        "Resmî kod sınıfla uyuşmuyor": [first.model_copy(update={"official_code": "MAT.10.1.1"})],
    }
    for expected, items in cases.items():
        with pytest.raises(r.RegistryError) as error:
            r.build(_catalog(registry, "tymm-2026.matematik.9-12"), [_file("tymm-2026.matematik.9-12", units, items)], EMPTY_V1, "x")
        assert any(expected in problem for problem in error.value.problems), (expected, error.value.problems)
    # Farklı çerçeveden ön koşul: sürüm uyuşmazlığı.
    old_units, old = _small(registry, "meb-2018.matematik.9-12", ("9.1.1.1",))
    mixed = first.model_copy(update={"prerequisites": [old[0].id]})
    with pytest.raises(r.RegistryError) as error:
        r.build(_catalog(registry, "tymm-2026.matematik.9-12", "meb-2018.matematik.9-12"),
                [_file("tymm-2026.matematik.9-12", units, [mixed]), _file("meb-2018.matematik.9-12", old_units, old)], EMPTY_V1, "x")
    assert any("Sürüm uyuşmazlığı" in problem for problem in error.value.problems)


def test_missing_legacy_record_is_reported_not_invented(registry):
    units, outcomes = _small(registry)
    with pytest.raises(r.RegistryError) as error:
        r.build(_catalog(registry, "tymm-2026.matematik.9-12"), [_file("tymm-2026.matematik.9-12", units, outcomes)],
                legacy.default_registry(), "x")
    assert any("v1 kazanımı v2'de yok" in problem for problem in error.value.problems)


def test_draft_annual_plans_cannot_be_registered_as_programs(registry):
    program = registry.catalog.programs[0].model_dump()
    with pytest.raises(ValueError):
        type(registry.catalog.programs[0]).model_validate({**program, "status": "draft"})


# --- Çözümleme ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("grade,program", [
    (5, "tymm-2026.matematik.5-8"), (6, "tymm-2026.matematik.5-8"), (7, "tymm-2026.matematik.5-8"),
    (8, "meb-2018.matematik.1-8"), (9, "tymm-2026.matematik.9-12"), (10, "tymm-2026.matematik.9-12"),
    (11, "tymm-2026.matematik.9-12"), (12, "meb-2018.matematik.9-12")])
def test_2026_2027_mathematics_resolution(registry, grade, program):
    result = resolve(registry, grade=grade)
    assert result.status == "resolved" and result.program_ids == [program]
    assert result.academic_year == "2026-2027" and result.academic_year_origin == "server_clock"
    assert ("by_exclusion" in result.reasons) == (grade == 8)


def test_subject_isolation_and_geometry_uses_mathematics_program(registry):
    assert resolve(registry, Subject.PHYSICS, 10).program_ids == ["tymm-2026.fizik.9-12"]
    assert resolve(registry, Subject.CHEMISTRY, 12).program_ids == ["meb-2018.kimya.9-12"]
    assert resolve(registry, Subject.SCIENCE, 7).program_ids == ["tymm-2026.fen-bilimleri.3-8"]
    assert resolve(registry, Subject.GEOMETRY, 9).program_ids == ["tymm-2026.matematik.9-12"]
    assert resolve(registry, Subject.PHYSICS, 8).reasons == ["no_program_for_grade"]
    assert resolve(registry, Subject.SCIENCE, 10).reasons == ["no_program_for_grade"]
    assert resolve(registry, Subject.UNKNOWN, 9).reasons == ["subject_unsupported"]


def test_unspecified_grade_is_not_guessed(registry):
    result = resolve(registry, grade=None)
    assert result.status == "unresolved" and result.reasons == ["grade_unknown"] and not result.program_ids


def test_graduate_preparing_for_ayt_is_not_a_grade_12_student(registry):
    result = resolve(registry, grade=12, learner_status="graduate", exam="AYT")
    assert result.status == "ambiguous" and result.grade is None and not result.program_ids
    assert result.reasons == ["graduate_exam_scope", "exam_scope_unverified"]
    assert set(result.candidate_program_ids) == {"meb-2018.matematik.9-12", "tymm-2026.matematik.9-12"}
    without_exam = resolve(registry, grade=None, learner_status="graduate")
    assert without_exam.status == "unresolved" and "graduate_exam_scope" in without_exam.reasons


def test_academic_year_transitions(registry):
    summer = resolve(registry, grade=8, today=date(2027, 7, 10))
    assert summer.status == "ambiguous" and "academic_year_transition" in summer.reasons
    declared = resolve(registry, grade=8, today=date(2027, 7, 10), academic_year="2026-2027")
    assert declared.status == "resolved" and declared.academic_year_origin == "declared"
    spring = resolve(registry, grade=6, today=date(2026, 3, 1))
    assert spring.academic_year == "2025-2026" and spring.reasons == ["program_document_missing"]
    assert resolve(registry, grade=8, today=date(2026, 3, 1)).reasons == ["schedule_unverified"]
    assert resolve(registry, grade=9, today=date(2027, 10, 1)).reasons == ["schedule_unverified"]


def test_explicit_program_not_matching_schedule_is_ambiguous(registry):
    result = resolve(registry, grade=8, program_id="tymm-2026.matematik.5-8")
    assert result.status == "ambiguous" and "explicit_program_not_applicable" in result.reasons
    assert resolve(registry, grade=8, program_id="meb-2018.matematik.1-8").status == "resolved"


def test_exam_scope_is_independent_of_school_curriculum(registry):
    student = resolve(registry, grade=8, exam="LGS")
    assert student.status == "resolved" and student.exam_scope_id == "lgs-2027" and "exam_scope_unverified" in student.reasons
    outcome = registry.outcomes["meb-2018.matematik.1-8::M.8.2.2.1"]
    assert r.exam_relevance(registry, outcome) == [{"scope_id": "lgs-2026", "basis": "grade_only_program_unverified"}]
    assert r.exam_relevance(registry, registry.outcomes["tymm-2026.matematik.5-8::MAT.7.2.2"]) == []


# --- Gözatma ve API -----------------------------------------------------------------------------------------------

def test_browse_tree_never_exposes_official_text(registry):
    tree = r.browse(registry, r.LEGACY_PROGRAM, 8)
    assert [unit["title_tr"] for unit in tree][:2] == ["Sayılar ve İşlemler", "Cebir"]
    flat = str(tree)
    assert "Birinci dereceden bir bilinmeyenli denklemleri çözer" not in flat
    assert all("official_text_tr" not in outcome for unit in tree for topic in unit["topics"] for outcome in topic["outcomes"])


def test_curriculum_api_catalog_browse_and_resolve():
    app = create_app()
    with authenticated_client(app) as client:
        catalog = client.get("/api/v1/curriculum/catalog").json()["data"]
        assert len(catalog["programs"]) == 12 and catalog["rights_notice"]
        physics = next(item for item in catalog["subjects"] if item["subject"] == "physics")
        assert not physics["capabilities"]["generation"]
        assert not any(mode["available"] for mode in physics["modes"])
        maths = next(item for item in catalog["subjects"] if item["subject"] == "mathematics")
        modes = {mode["mode"]: mode for mode in maths["modes"]}
        assert modes["question_solving"]["available"] and not modes["topic_explanation"]["available"]
        tree = client.get("/api/v1/curriculum/programs/tymm-2026.matematik.5-8/grades/7").json()["data"]
        assert tree["units"] and tree["units"][0]["outcomes"][0]["description_review"] == "unreviewed"
        assert client.get("/api/v1/curriculum/programs/tymm-2026.matematik.5-8/grades/12").status_code == 404
        resolved = client.get("/api/v1/curriculum/resolve", params={"learner_status": "graduate", "exam": "AYT"}).json()["data"]
        assert resolved["status"] == "ambiguous" and resolved["grade"] is None
    app.state.container = replace(app.state.container)
    with authenticated_client(app) as client:
        client.headers.pop("Authorization")
        assert client.get("/api/v1/curriculum/catalog").status_code == 401


# --- Çıkarıcı -----------------------------------------------------------------------------------------------------

def test_extractor_reads_codes_headings_and_pages_without_copying_statements():
    text = ("İçindekiler M.8.1.1. Çarpanlar ve Katlar Kazanım Sayısı 3 M.8.1.1.1. - M.8.1.1.3.\f"
            "M. 8.1. SAYILAR VE İŞLEMLER M.8.1.1. Çarpanlar ve Katlar Terimler ve kavramlar: çarpan\n"
            "M.8.1.1.1. Verilen pozitif tam sayıların çarpanlarını bulur.\n"
            "M.8.1.1.2.İki doğal sayının EBOB ve EKOK değerini hesaplar.\f")
    result = curriculum_extract.extract("meb-2018.matematik.1-8", text)
    assert [item["official_code"] for item in result["outcomes"]] == ["M.8.1.1.1", "M.8.1.1.2"]
    assert all(item["page"] == 2 for item in result["outcomes"])
    headings = {item["code"]: item["title"] for item in result["units"]}
    assert headings == {"M.8.1": "SAYILAR VE İŞLEMLER", "M.8.1.1": "Çarpanlar ve Katlar"}
    built = curriculum_extract.build_program_file("meb-2018.matematik.1-8", result)
    assert "Verilen pozitif" not in str(built)
    assert built["outcomes"][0]["topic_key"] == "carpanlar_ve_katlar" and built["units"][0]["title_tr"] == "Sayılar ve İşlemler"

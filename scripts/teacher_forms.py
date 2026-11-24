"""Doldurulmuş öğretmen Word formunu (.docx) kanonik katkı taslağına çevirir (TA-007 §14).

    python -m scripts.teacher_forms convert <form.docx> [--topic <taksonomi_anahtarı>] [--write]

Kurallar:

- Yalnız ``word/document.xml`` metni okunur; makro, gömülü nesne veya dış bağlantı çalıştırılmaz/izlenmez.
- Boş bırakılan alan (``[Buraya yazınız.]``) öğe üretmez. Belirsiz yanıt olgu sayılmaz: takma ad/rol/tarih,
  konu veya kullanım izni tek anlamlı değilse dönüşüm durur ve sorun listelenir.
- Kullanım izni "Evet" açıkça seçilmeden katkı içeri alınmaz. Model eğitimi izni yalnız açık "Evet" ile true olur.
- Ad, e-posta, telefon gibi kişisel bilgi görülürse dönüşüm durur.
- Özgün soru, öğretmenin bağımsız cevabı olmadan örnek soru öğesine çevrilmez; cevap türetilmez.
- Çıktı yalnız bir *katkı taslağıdır*; onay, yayım veya bilgi girdisi değildir (bkz. docs/teachers/import-guide.md).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from apps.api.app.features.curriculum import topics
from apps.api.app.features.education.base import Subject
from apps.api.app.features.education.contribution import TeacherContribution

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/contributions"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
PLACEHOLDER = "[Buraya yazınız.]"
MAX_DOCX = 5 * 1024 * 1024
SUBJECTS = {"matematik ve geometri": Subject.MATHEMATICS, "fizik": Subject.PHYSICS, "kimya": Subject.CHEMISTRY,
            "biyoloji": Subject.BIOLOGY, "ortaokul fen bilimleri": Subject.SCIENCE, "fen bilimleri": Subject.SCIENCE}
# Etiket öneki → alan. Formlardaki sabit etiketlerdir; sırası önemlidir.
LABELS = [
    ("takma ad / rol / tarih", "identity"), ("düzey ve program", "level"), ("seçtiğiniz konu", "topic"),
    ("ilk inceleme ve çözüm planı", "unfamiliar_question_approach"), ("sık hata", "common_error"),
    ("tercih ettiğiniz çözüm yöntemi", "preferred_strategy"), ("hangi sınıfta hangi yöntem", "class_level_method"),
    ("ilk açıklama anlaşılmazsa", "alternative_explanation"), ("tahta çiziminin sırası", "visual_strategy"),
    ("kural / yasa / kavram", "scientific_condition"), ("istisna, karşı örnek", "scientific_exception"),
    ("kaynak (kitap", "source"), ("özgün soru", "question"), ("bağımsız cevap", "answer"),
    ("öğrettiği fikir", "question_note"), ("katkımın teacher", "consent_use"),
    ("model ağırlıklarının eğitimi", "consent_training"),
]
# Kişisel bilgi işaretleri (e-posta, cep telefonu). Okul adı serbest metinde güvenilir tanınamaz; formdaki uyarı
# ve inceleme aşaması bunu yakalar.
PERSONAL = [re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), re.compile(r"(?:\+?90|0)?\s?5\d{2}\s?\d{3}\s?\d{2}\s?\d{2}")]
REF = re.compile(r"\b(teacher|expert):([a-z0-9][a-z0-9_-]{2,63})\b")


def _lower(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower()


def paragraphs(path: Path) -> list[str]:
    if path.stat().st_size > MAX_DOCX:
        raise ValueError("Form dosyası çok büyük.")
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("word/document.xml")
        if info.file_size > 4 * MAX_DOCX:
            raise ValueError("Belge içeriği çok büyük.")
        root = ElementTree.fromstring(archive.read(info))  # DTD/varlık genişletmesi yapılmaz
    out = []
    for para in root.iter(f"{W}p"):
        text = "".join(node.text or "" for node in para.iter(f"{W}t")).strip()
        if text:
            out.append(text)
    return out


def fields(paras: list[str]) -> tuple[Subject | None, dict[str, str]]:
    subject = SUBJECTS.get(_lower(paras[0]).strip()) if paras else None
    found: dict[str, list[str]] = {}
    current = None
    for text in paras[1:]:
        lowered = _lower(text)
        label = next((name for prefix, name in LABELS if lowered.startswith(prefix)), None)
        if label:
            current = label
            # Etiket satırında ':' sonrası yanıt (izin satırları gibi) etiketten sonra yazılmış olabilir.
            found.setdefault(label, []).append(text)
            continue
        if re.match(r"^\d\s*\|", text) or lowered.startswith("bilimsel koşullar ve özgün örnek"):
            current = None
            continue
        if current and text != PLACEHOLDER:
            found.setdefault(current, []).append(text)
    return subject, {key: "\n".join(values) for key, values in found.items()}


def _answer(value: str) -> str:
    """Etiket satırını çıkarır; yalnız öğretmenin yazdığı metin kalır."""
    lines = value.split("\n")
    return "\n".join(lines[1:]).strip()


def _choice(value: str) -> bool | None:
    """İzin satırı: yalnız tek seçenek kaldıysa karar verir. İki seçenek de duruyorsa None (belirsiz)."""
    text = _lower(value.split(":", 1)[1] if ":" in value else value)
    yes, no = "evet" in text, "hayır" in text
    if yes == no:
        return None
    return yes


def convert(path: Path, topic: str | None = None) -> tuple[dict | None, list[str]]:
    problems: list[str] = []
    subject, data = fields(paragraphs(path))
    if subject is None:
        problems.append("Form alanı (branş başlığı) tanınmadı.")
    for key, value in data.items():
        if key == "identity":
            continue
        for pattern in PERSONAL:
            if pattern.search(_answer(value) if key not in {"consent_use", "consent_training"} else ""):
                problems.append(f"Kişisel bilgi olabilir ({key}); form içeri alınmadı.")
    identity = _answer(data.get("identity", ""))
    refs = REF.findall(identity)
    dates = re.findall(r"\b(20\d\d-\d\d-\d\d)\b", identity)
    if len(refs) != 1:
        problems.append("Takma ad tek ve 'teacher:…' ya da 'expert:…' biçiminde olmalı.")
    if len(dates) != 1:
        problems.append("Tarih tek ve YYYY-AA-GG biçiminde olmalı.")
    consent = _choice(data.get("consent_use", ""))
    if consent is not True:
        problems.append("Kullanım izni açıkça 'Evet' seçilmedi; katkı içeri alınmaz.")
    training = _choice(data.get("consent_training", ""))
    if training is None:
        training = False  # formdaki varsayılan "Hayır"; iki seçenek de duruyorsa izin yok sayılır
    topic_text = _answer(data.get("topic", ""))
    if topic is None and subject is not None:
        mapping = topics.map_question(type("Q", (), {"question_text": topic_text, "integrity": None})(), subject)
        if mapping.status == "single":
            topic = mapping.keys[0]
        else:
            problems.append(f"Konu tek anlamlı eşlenemedi ({mapping.status}: {', '.join(mapping.keys) or '—'}); "
                            "--topic ile taksonomi anahtarı verin.")
    grades = sorted({int(value) for value in re.findall(r"\b(1[0-2]|[5-9])\s*\.?\s*sınıf", _lower(_answer(data.get("level", ""))))})
    source = _answer(data.get("source", "")) or None
    items = []
    for kind in ("unfamiliar_question_approach", "common_error", "preferred_strategy", "class_level_method",
                 "alternative_explanation", "visual_strategy", "scientific_condition", "scientific_exception"):
        text = _answer(data.get(kind, ""))
        if text:
            items.append({"kind": kind, "topic": topic or "konu_belirsiz", "text_tr": text[:4000], "grades": grades,
                          **({"source_note_tr": source[:1000]} if source and kind.startswith("scientific") else {})})
    question, answer = _answer(data.get("question", "")), _answer(data.get("answer", ""))
    if question and not answer:
        problems.append("Özgün soru bağımsız öğretmen cevabı olmadan verilmiş; örnek soru öğesi oluşturulmadı.")
    elif question:
        items.append({"kind": "example_question", "topic": topic or "konu_belirsiz", "grades": grades,
                      "text_tr": (_answer(data.get("question_note", "")) or "Öğretmenin özgün sorusu.")[:4000],
                      "example": {"question_tr": question[:4000], "answer_key_tr": answer[:4000], "original": True}})
    if not items:
        problems.append("Doldurulmuş katkı alanı yok.")
    if problems:
        return None, problems
    record = {"schema_name": "teacherai.teacher_contribution", "version": "1.0.0", "contributor": ":".join(refs[0]),
              "role": "subject_expert" if refs[0][0] == "expert" else "teacher", "subject": subject.value,
              "submitted_on": dates[0], "consent_use": True, "consent_model_training": training, "items": items}
    TeacherContribution.model_validate(record)
    return record, []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=["convert"])
    parser.add_argument("docx", type=Path)
    parser.add_argument("--topic")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    record, problems = convert(args.docx, args.topic)
    for problem in problems:
        print(f"SORUN: {problem}")
    if record is None:
        return 1
    text = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    if not args.write:
        sys.stdout.write(text)
        return 0
    name = f"{record['contributor'].replace(':', '-')}-{record['subject']}-{record['submitted_on']}.json"
    target = OUT / name
    if target.exists():
        print(f"SORUN: {target.name} zaten var; üzerine yazılmaz (yeni sürüm için yeni dosya).")
        return 1
    target.write_text(text, encoding="utf-8")
    print(f"Katkı taslağı yazıldı: {target.relative_to(ROOT)}. Onay değildir; register.json'a 'submitted' kaydı ekleyin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

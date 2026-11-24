"""Bilgi girdileri ile mevcut belirlenimci denetleyiciler arasındaki sınırlı yetenek eşlemesi (TA-006).

Her kimlik gerçek bir fonksiyona bağlanır (``target``) ve ne kanıtladığını, neyi kanıtlamadığını açıkça yazar.
Bir bilgi girdisinin denetleyiciye bağlanması iddianın yalnız o parçasının sınanabildiğini söyler; bütün iddia
hiçbir zaman ``passed`` gösterilmez. Bu modül denetleyici çalıştırmaz; yalnız kapsamı tanımlar.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import get_args

from ..education.knowledge import CapabilityCheck, KnowledgeEntry, VerifierId

ROOT = "apps.api.app.features"


@dataclass(frozen=True)
class Capability:
    target: str  # "modül:öznitelik"
    proves_tr: str
    does_not_prove_tr: str


CAPABILITIES: dict[str, Capability] = {
    "mathai.equation_roots": Capability("mathai.targets:valid_roots", "Aday köklerin özgün tek değişkenli gerçel denklemi sağlaması, yabancı ve kayıp kök.",
                                        "Görselin doğru okunduğunu, sözel gerekçeyi veya yöntemin uygunluğunu."),
    "mathai.inequality_solution": Capability("mathai.service:MathAIService", "Tek değişkenli eşitsizlikte adım sonrası çözüm kümesi ve yön değişimi.",
                                             "Çok değişkenli eşitsizlikleri ve grafik yorumunu."),
    "mathai.answer_target": Capability("reasoning.target:target_for", "Sorunun istediği hedefin (x, x+2, kök toplamı…) belirlenimci tespiti.",
                                       "Hedefin sorunun bağlamına uygun yorumlandığını (önce bütünlük denetimi gerekir)."),
    "mathai.constant_expression": Capability("mathai.targets:constant", "Değişkensiz kök, üs ve kesir ifadesinin kesin gerçel değeri.",
                                             "İfadenin sorudaki niceliği doğru temsil ettiğini."),
    "integrity.expression_ast": Capability("integrity.expression:parse", "Kök, kesir ve üs kapsamı; tekli eksinin yeri; ifadenin dengeli yapısı.",
                                           "Matematiksel doğruluğu; yalnız yapıyı ayrıştırır."),
    "reasoning.units.dimension": Capability("reasoning.units:same_dimension", "İki niceliğin veya bir formülün boyut uyumu.",
                                            "Doğru fizik yasasının seçildiğini; boyutça doğru formül yanlış yasa olabilir."),
    "reasoning.units.conversion": Capability("reasoning.units:convert", "Önekli ve türetilmiş birimler arasında kesin dönüşüm.",
                                             "Ölçümün doğruluğunu veya anlamlı basamakları."),
    "reasoning.formula.evaluate": Capability("reasoning.formula:check_formula", "Verilen formülde birimli yerine koyma ve sayısal sonuç.",
                                             "Formülün bu duruma uygulanabilir olduğunu (koşullar ayrıca denetlenmez)."),
    "reasoning.formula.dimensions": Capability("reasoning.formula:check_dimensions", "Formül iki tarafının boyut eşitliği.",
                                               "Formülün fiziksel olarak doğru olduğunu."),
    "reasoning.formula.graph_slope": Capability("reasoning.formula:graph_slope", "Grafikte iki nokta arası eğim ve birimi.",
                                                "Grafiğin görselden doğru okunduğunu."),
    "reasoning.formula.graph_area": Capability("reasoning.formula:graph_area", "Parçalı doğrusal grafiğin altındaki alan.",
                                               "Alanın fiziksel yorumunun soruya uygunluğunu."),
    "reasoning.chemistry.parse_species": Capability("reasoning.chemistry:parse_species", "Formülün bileşimi, hâli ve yükü (yazım düzeyinde).",
                                                    "Türün gerçekte var olduğunu veya kararlılığını."),
    "reasoning.chemistry.balance": Capability("reasoning.chemistry:check_reaction", "Atom ve yük dengesi, en küçük tam sayı katsayılar.",
                                              "Tepkimenin gerçekleştiğini, kendiliğindenliği, hızı veya koşulları."),
    "reasoning.chemistry.stoichiometry": Capability("reasoning.chemistry:stoichiometric_amount", "Denkleşmiş denklemden mol oranıyla miktar.",
                                                    "Verimi ve tepkimenin tam yürüdüğü varsayımının geçerliliğini."),
    "reasoning.chemistry.limiting_reactant": Capability("reasoning.chemistry:limiting_amount", "Sınırlayıcı bileşen ve kuramsal ürün miktarı.",
                                                        "Gerçek verimi."),
    "reasoning.chemistry.redox_electrons": Capability("reasoning.chemistry:electron_change", "Yükseltgenme basamağı değişiminden aktarılan elektron sayısı.",
                                                      "Tepkimenin istemli olduğunu."),
    "reasoning.sequence.transcription": Capability("reasoning.sequence:transcribe_template", "Kalıp DNA'dan tamamlayıcı mRNA dizisi.",
                                                   "Gen ifadesinin düzenlenmesini veya biyolojik işlevi."),
    "reasoning.sequence.codon": Capability("reasoning.sequence:codon", "mRNA'da belirli konumdaki kodon.",
                                           "Okuma çerçevesinin biyolojik olarak doğru seçildiğini."),
    "reasoning.evidence.controlled_comparison": Capability("reasoning.evidence:check_controlled_comparison", "Deney gruplarında yalnız bir değişkenin değiştiği.",
                                                           "Deneyin gerçekten yapıldığını veya ölçümlerin doğruluğunu."),
    "reasoning.evidence.claim": Capability("reasoning.evidence:check_claim", "Verilen deney verisinin iddiayı destekleyip desteklemediği.",
                                           "Verinin kaynağını; genellemenin bütün koşullarda geçerli olduğunu."),
    "reasoning.evidence.constant_ratio": Capability("reasoning.evidence:check_constant_ratio", "Tablodaki iki değişkenin oranının sabitliği.",
                                                    "İlişkinin nedensel olduğunu veya yasanın geçerlilik koşullarını."),
    "reasoning.evidence.sequence_order": Capability("reasoning.evidence:check_sequence", "Verilen süreç sırasının modeldeki sırayla uyumu.",
                                                    "Modelin biyolojik olarak doğru olduğunu (model kaynaktan gelmelidir)."),
}


def resolve_target(verifier: str):
    module_name, attribute = CAPABILITIES[verifier].target.split(":")
    return getattr(import_module(f"{ROOT}.{module_name}"), attribute)


def capability_check(entry: KnowledgeEntry) -> CapabilityCheck:
    """Girdinin denetleyici kapsamı. Bağlantı varsa ``partially_checked``, yoksa ``not_checked``; asla ``passed``."""
    verifiers = [link.verifier for link in entry.verifiers]
    unchecked = sorted({CAPABILITIES[name].does_not_prove_tr for name in verifiers}) or ["Bu girdi için belirlenimci denetleyici yok."]
    return CapabilityCheck(entry_id=entry.id, verifiers=verifiers,
                           claim_state="partially_checked" if verifiers else "not_checked", unchecked_tr=unchecked[:8])


def missing_definitions() -> set[str]:
    """Sözleşmedeki kimliklerden tanımı olmayanlar (test boş olmasını bekler)."""
    return set(get_args(VerifierId)) ^ set(CAPABILITIES)

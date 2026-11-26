"""Fizik yanılgı kayıtları (TA-009 §15). AI taslağıdır (``draft``); öğretmen incelemesi olmadan öğretim kararı
değildir. Her kayıt bilgi girdilerine bağlanır ve nasıl yakalandığını söyler:

- ``detection``: fizik doğrulama raporunun ürettiği denetim neden kodu. ``cause_identified=True`` yalnız denetim bu
  yanılgıya özgü değeri (ör. alanı yol sayarak bulunan sayı) yakalıyorsa; aksi halde yalnız sonucun yanlış olduğu
  bilinir, nedeni bilinmez.
- ``detection=None``: yalnız belgelemedir (``documentation_only``); hiçbir denetim bunu yakalamaz.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Misconception:
    id: str
    statement_tr: str
    correction_tr: str
    records: tuple[str, ...]
    detection: str | None
    cause_identified: bool = False
    status: str = "draft"

    @property
    def documentation_only(self) -> bool:
        return self.detection is None


MISCONCEPTIONS = (
    Misconception("motion_requires_force", "Hareketin sürmesi için sürekli bir kuvvet gerekir.",
                  "Net kuvvet sıfırsa cisim sabit hızla hareketine devam eder; kuvvet hızın değişimine yol açar.",
                  ("phys.newton-first-law",), None),
    Misconception("heavier_falls_faster", "Hava direnci yokken ağır cisim daha hızlı düşer.",
                  "Hava direnci ihmal edilince bütün cisimler aynı g ivmesiyle düşer; düşme süresi kütleye bağlı değildir.",
                  ("phys.free-fall",), None),
    Misconception("current_used_up", "Akım dirençten geçerken azalır, tükenir.",
                  "Seri kolda akım her noktada aynıdır; dirençte azalan elektriksel potansiyeldir (yük korunur).",
                  ("phys.kirchhoff-rules", "phys.series-parallel"), "answer_mismatch"),
    Misconception("action_reaction_same_body", "Etki ve tepki aynı cisme etki eder ve birbirini dengeler.",
                  "Etki–tepki çiftinin kuvvetleri farklı cisimlere etki eder; aynı cisim üzerindeki kuvvetleri dengelemez.",
                  ("phys.newton-third-law",), None),
    Misconception("velocity_acceleration_same_direction", "Hız ve ivme her zaman aynı yöndedir.",
                  "Yavaşlayan cisimde ivme hıza zıttır; yukarı atılan top çıkarken hız yukarı, ivme aşağıdır.",
                  ("phys.speed-vs-velocity", "phys.constant-acceleration"), "sign_mismatch"),
    Misconception("vt_area_always_distance", "Hız–zaman grafiğinin altındaki alan her zaman alınan yoldur.",
                  "İşaretli alan yer değiştirmedir; hız işaret değiştiriyorsa alınan yol |v| alanıdır.",
                  ("phys.velocity-time-graph", "phys.distance-vs-displacement"),
                  "misconception_graph_area_as_distance", True),
    Misconception("kinetic_friction_always", "Kuvvet uygulanan cisim mutlaka kayar; sürtünme hep μ_k N'dir.",
                  "Önce f_s ≤ μ_s N ile kayma kararı verilir; kayma yoksa ivme sıfırdır ve statik sürtünme gerektiği kadardır.",
                  ("phys.static-friction-decision", "phys.friction"), "misconception_kinetic_friction_while_static", True),
    Misconception("energy_conserved_with_friction", "Sürtünmeli yüzeyde de mekanik enerji korunur.",
                  "Sürtünmenin işi mekanik enerjiyi azaltır; bu iş hesaba katılmadan korunum uygulanamaz.",
                  ("phys.nonconservative-work", "phys.mechanical-energy-conservation"), "law_not_applicable", True),
    Misconception("mass_equals_weight", "Kütle ve ağırlık aynı niceliktir.",
                  "Kütle (kg) madde miktarıdır; ağırlık (N) yerçekimi kuvvetidir: W = m g.",
                  ("phys.mass-weight",), "dimension_mismatch", True),
    Misconception("internal_resistance_ignored", "Üretecin uç gerilimi her zaman EMK'ya eşittir.",
                  "Akım geçerken uç gerilimi iç dirençteki düşüm kadar azalır: V = ε − I r.",
                  ("phys.internal-resistance",), "answer_mismatch"),
)

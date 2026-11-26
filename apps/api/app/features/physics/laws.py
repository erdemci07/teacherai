"""Fizik yasaları ve makinece denetlenen uygulanabilirlik koşulları (TA-009 §11).

Her koşul sorunun modeline karşı tam olarak bir sonuç verir: ``satisfied``, ``violated`` veya ``unknown``.

- ``violated`` yasayı engeller: başka bir uygulanabilir yasa, hedefli açıklama veya ``unsupported``.
- ``unknown`` hiçbir zaman sessizce ``satisfied`` sayılmaz. Koşul ``assumable`` ise (ör. yer yüzeyi eylemsiz
  referans sistemi) öğrenciye *görünür varsayım* olarak yazılır; değilse sonuç en fazla ``partially_checked`` olur.
- Örtük Türkçe idealleştirmeler ("sürtünmesiz", "ağırlığı önemsiz", "ideal") ``conventions.read`` ile açık
  koşullara çevrilir. Sağlayıcının koşul iddiası (``LawUse.conditions``) yalnız karşılaştırma içindir; durum belirlemez.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from ..education.science import PhysicsModel, ScientificProblemModel
from .conventions import SourceFacts

DIRECT = {"source_text", "student_confirmed", "problem_convention"}


@dataclass(frozen=True)
class ConditionSpec:
    id: str
    text_tr: str
    assumable: bool = False
    assumption_tr: str | None = None


@dataclass(frozen=True)
class Law:
    id: str
    title_tr: str
    formula: str
    conditions: tuple[ConditionSpec, ...]
    solver: str | None  # bu yasayı kullanan belirlenimci çözücü; None: yalnız tanınır, çözülmez
    knowledge: str | None = None  # bilgi kaydı kimliği (knowledge/data/physics.json)


C = ConditionSpec
LAWS: dict[str, Law] = {law.id: law for law in (
    Law("kinematics.constant_acceleration", "Sabit ivmeli doğrusal hareket", r"x = v_0 t + \frac{1}{2} a t^2",
        (C("constant_acceleration", "İvme aralık boyunca sabittir."),
         C("one_dimensional", "Hareket tek doğrultudadır (eksen önce sabitlenir).", True,
           "Hareket tek bir doğrultuda ve seçilen eksende incelendi.")), "kinematics", "phys.kinematics-constant-acceleration"),
    Law("kinematics.free_fall", "Serbest düşme ve atış", r"h = \frac{1}{2} g t^2",
        (C("no_air_resistance", "Hava direnci ihmal edilir.", True, "Hava direnci ihmal edildi."),
         C("uniform_gravity", "Yerçekimi ivmesi sabittir (yüzeye yakın).", True,
           "Yüzeye yakın, sabit yerçekimi ivmesi kabul edildi."),
         C("gravity_value_known", "g değeri soruda verilmiş veya Dünya yüzeyi için standart değerdir.")),
        "kinematics", "phys.free-fall"),
    Law("dynamics.newton_second", "Newton'un ikinci yasası", r"F_{net} = m a",
        (C("inertial_frame", "Referans sistemi eylemsizdir.", True, "Yer eylemsiz referans sistemi kabul edildi."),
         C("constant_mass", "Kütle sabittir.", True, "Cisimlerin kütlesi sabit kabul edildi."),
         C("classical_regime", "Klasik bölge: hızlar ışık hızına göre çok küçüktür."),
         C("forces_established", "Her kuvvet soruda kurulmuştur (sağlayıcının çizdiği ok kanıt değildir).")),
        "dynamics", "phys.newton-second-law"),
    Law("dynamics.friction", "Statik ve kinetik sürtünme", r"f_s \le \mu_s N,\; f_k = \mu_k N",
        (C("sliding_state_decided", "Kayma durumu kinetik sürtünme seçilmeden önce belirlenir (f_s ≤ μ_s N)."),
         C("friction_coefficients_given", "Gereken sürtünme katsayısı soruda verilmiştir.")),
        "dynamics", "phys.friction"),
    Law("dynamics.ideal_string", "Kütlesiz ip ve ideal makara", r"T_1 = T_2",
        (C("massless_string", "İpin kütlesi önemsizdir.", True, "İpin kütlesi önemsiz kabul edildi."),
         C("ideal_pulley", "Makara kütlesiz ve sürtünmesizdir.", True, "Makara kütlesiz ve sürtünmesiz kabul edildi.")),
        "dynamics", "phys.ideal-string"),
    Law("energy.mechanical_conservation", "Mekanik enerjinin korunumu", r"E_k + E_p = \text{sabit}",
        (C("no_nonconservative_work", "Korunumsuz kuvvetlerin işi yoktur veya açıkça hesaba katılmıştır."),),
        "energy", "phys.mechanical-energy-conservation"),
    Law("energy.work_energy", "İş–kinetik enerji teoremi", r"W_{net} = \Delta E_k",
        (C("forces_established", "Her kuvvet soruda kurulmuştur."),), "energy", "phys.work-energy-theorem"),
    Law("momentum.conservation", "Momentumun korunumu", r"\sum p_{önce} = \sum p_{sonra}",
        (C("isolated_system", "Seçilen sistemde net dış itme sıfır veya ihmal edilebilir; sistem sınırı bellidir."),
         C("one_dimensional", "Çarpışma tek doğrultudadır.", True, "Çarpışma tek doğrultuda incelendi.")),
        "momentum", "phys.momentum-conservation"),
    Law("momentum.impulse", "İtme–momentum teoremi", r"F \Delta t = \Delta p",
        (C("constant_or_average_force", "Kuvvet sabittir veya ortalama kuvvet istenmektedir.", True,
           "Kuvvet sabit (veya ortalama) kabul edildi."),), "momentum", "phys.impulse-momentum"),
    Law("circuit.ohm", "Ohm yasası", r"V = I R",
        (C("ohmic_element", "Eleman ohmiktir (direnci akımla değişmez).", True,
           "Direnç ve lambaların dirençleri sabit (ohmik) kabul edildi."),), "dc_circuit", "phys.ohms-law"),
    Law("circuit.kirchhoff", "Kirchhoff yasaları", r"\sum I = 0,\; \sum V = 0",
        (C("lumped_circuit", "Toplu devre modeli (bağlantı telleri ideal).", True,
           "Bağlantı tellerinin direnci önemsiz kabul edildi."),
         C("topology_established", "Devre bağlantıları kesin olarak kurulmuştur (görsel yakınlık bağlantı değildir)."),
         C("ideal_meters", "Ampermetre ideal (direnci sıfır), voltmetre ideal (direnci sonsuz).", True,
           "Ölçü aletleri ideal kabul edildi.")), "dc_circuit", "phys.kirchhoff-laws"),
    # Tanınan ama bu fazda çözülmeyen yasalar (koşulları yine de denetlenir).
    Law("thermo.ideal_gas", "İdeal gaz denklemi", "PV = nRT",
        (C("ideal_gas_regime", "Gaz ideal davranır (düşük basınç, yüksek sıcaklık)."),
         C("absolute_temperature", "Sıcaklık kelvin cinsindendir.")), None, "phys.ideal-gas-law"),
    Law("optics.thin_lens", "İnce mercek denklemi", r"\frac{1}{f} = \frac{1}{d_o} + \frac{1}{d_i}",
        (C("paraxial", "Yakın eksen (paraksiyel) yaklaşımı."), C("sign_convention_stated", "İşaret uzlaşımı bellidir.")),
        None, "phys.thin-lens"),
    Law("fluids.bernoulli", "Bernoulli denklemi", r"P + \frac{1}{2}\rho v^2 + \rho g h = \text{sabit}",
        (C("steady_flow", "Akış kararlıdır."), C("incompressible", "Akışkan sıkıştırılamaz."),
         C("inviscid", "Akışkan viskozitesizdir."), C("streamline", "Aynı akım çizgisi boyunca.")), None,
        "phys.bernoulli"),
    Law("fluids.hydrostatic", "Sıvı basıncı", r"P = \rho g h",
        (C("fluid_at_rest", "Akışkan durgundur."), C("uniform_density", "Özkütle düzgündür.")), None,
        "phys.hydrostatic-pressure"),
    Law("oscillation.pendulum", "Basit sarkaç", r"T = 2\pi\sqrt{L/g}",
        (C("small_amplitude", "Genlik küçüktür."),), None, "phys.simple-pendulum"),
)}


@dataclass(frozen=True)
class ConditionResult:
    law: str
    condition: str
    state: str  # satisfied | violated | unknown
    basis: str  # source_text | idealization | derived | graph | assumption | none
    assumption_tr: str | None = None  # unknown + assumable: öğrenciye görünen varsayım
    detail: str | None = None

    @property
    def blocks(self) -> bool:
        return self.state == "violated"

    @property
    def open(self) -> bool:
        """Bilinmiyor ve görünür varsayım olarak da yazılamıyor: sonuç en fazla kısmi doğrulama."""
        return self.state == "unknown" and self.assumption_tr is None


@dataclass
class Context:
    problem: ScientificProblemModel
    model: PhysicsModel
    facts: SourceFacts
    text: str
    values: dict = field(default_factory=dict)  # nicelik kimliği → Fraction (SI)
    derived: dict = field(default_factory=dict)  # çözücüden: sliding kararı, ivme sabitliği vb.


def evaluate(law_id: str, ctx: Context) -> list[ConditionResult]:
    law = LAWS[law_id]
    out = []
    for spec in law.conditions:
        state, basis, detail = _EVALUATORS.get(spec.id, _unknown)(ctx)
        assumption = spec.assumption_tr if state == "unknown" and spec.assumable else None
        out.append(ConditionResult(law_id, spec.id, state, basis if not assumption else "assumption", assumption, detail))
    return out


def _unknown(ctx: Context):
    return "unknown", "none", None


def _stated(name: str):
    def check(ctx: Context):
        if name in ctx.facts.stated:
            return "satisfied", "idealization", ctx.facts.stated[name]
        return "unknown", "none", None
    return check


def _constant_acceleration(ctx: Context):
    if ctx.derived.get("acceleration_constancy") == "varying":
        return "violated", "graph", "Grafikteki eğim aralık boyunca değişiyor."
    if ctx.derived.get("acceleration_constancy") == "constant":
        return "satisfied", "graph", "Grafik doğrusal: eğim (ivme) sabit."
    phases = ctx.model.phases
    if any(p.acceleration_kind == "varying" for p in phases):
        return "violated", "source_text", "İvme değişiyor."
    for name in ("constant_acceleration", "constant_velocity", "free_fall", "starts_from_rest"):
        if name in ctx.facts.stated and name != "starts_from_rest":
            return "satisfied", "idealization", ctx.facts.stated[name]
    if ctx.derived.get("net_force_constant"):
        return "satisfied", "derived", "Net kuvvet sabit olduğundan ivme sabittir (Newton'un ikinci yasası)."
    if ctx.derived.get("free_fall_constant") and not any(p.acceleration_kind == "varying" for p in phases):
        return "satisfied", "derived", "Yalnız düzgün yerçekimi etkiliyor: ivme g ve sabit (hava direnci ihmal edildi)."
    if any(p.acceleration_kind in {"constant", "zero"} and p.acceleration_basis in DIRECT for p in phases):
        return "satisfied", "source_text", None
    return "unknown", "none", None


def _forces_established(ctx: Context):
    unproven = [f.id for f in ctx.model.forces if f.provenance not in DIRECT | {"derived", "background_knowledge"}]
    if unproven:
        return "unknown", "none", "Kaynağa bağlanamayan kuvvet(ler): " + ", ".join(unproven)
    return "satisfied", "source_text", None


def _classical(ctx: Context):
    speeds = [abs(v) for key, v in ctx.values.items() if ctx.derived.get("kinds", {}).get(key) in {"speed", "velocity"}]
    if any(v >= Fraction(299792458, 10) for v in speeds):
        return "violated", "derived", "Hız ışık hızının onda birinden büyük: klasik yasa uygulanmaz."
    return "satisfied", "derived", None


def _sliding_decided(ctx: Context):
    decision = ctx.derived.get("sliding")
    if decision in {"static", "kinetic", "frictionless"}:
        return "satisfied", "derived", {"static": "Kayma yok: statik sürtünme f_s ≤ μ_s N ile dengeler.",
                                        "kinetic": "Kayma var: kinetik sürtünme kullanıldı.",
                                        "frictionless": "Sürtünme yok."}[decision]
    return "unknown", "none", None


def _coefficients(ctx: Context):
    if ctx.derived.get("friction_needed") is False:
        return "satisfied", "derived", None
    return ("satisfied", "source_text", None) if ctx.derived.get("friction_coefficients") else ("unknown", "none", None)


def _no_nonconservative(ctx: Context):
    if ctx.derived.get("nonconservative_work_accounted"):
        return "satisfied", "derived", "Sürtünmenin işi enerji denklemine katıldı."
    if "frictionless" in ctx.facts.stated and "frictionless" not in ctx.facts.contradicted:
        return "satisfied", "idealization", ctx.facts.stated["frictionless"]
    if ctx.facts.contradicted.get("frictionless") and "frictionless" not in ctx.facts.stated:
        return "violated", "source_text", "Soru sürtünmeli; sürtünmenin işi hesaba katılmadan enerji korunmaz."
    if ctx.derived.get("vertical_only") and "no_air_resistance" in ctx.facts.stated:
        return "satisfied", "idealization", ctx.facts.stated["no_air_resistance"]
    return "unknown", "none", None


def _isolated(ctx: Context):
    collisions = ctx.model.collisions
    if any(c.external_impulse == "present" for c in collisions):
        return "violated", "source_text", "Sisteme net dış itme etkiyor."
    if "isolated_system" in ctx.facts.stated or ("frictionless" in ctx.facts.stated and collisions):
        return "satisfied", "idealization", ctx.facts.stated.get("isolated_system") or ctx.facts.stated["frictionless"]
    if collisions and all(c.external_impulse == "none_stated" for c in collisions):
        return "unknown", "none", "Sağlayıcı dış itmenin olmadığını belirtti ama kaynakta yazılı değil."
    return "unknown", "none", None


def _gravity_known(ctx: Context):
    if "g" in ctx.facts.conventions:
        return "satisfied", "problem_convention", ctx.facts.conventions["g"].quote
    if ctx.facts.off_earth:
        return "violated", "source_text", f"Dünya dışı ortam ({ctx.facts.off_earth}) ve g verilmemiş: değer uydurulmaz."
    return "satisfied", "assumption", "Soru g vermediği için standart değer 9,80665 m/s² kullanıldı (öğrenciye gösterilir)."


def _topology(ctx: Context):
    circuit = ctx.model.circuit
    if circuit is None:
        return "unknown", "none", None
    uncertain = [e.id for e in circuit.elements if not e.connection_certain]
    if uncertain:
        return "unknown", "none", "Bağlantısı kesin olmayan eleman(lar): " + ", ".join(uncertain)
    if any(e.provenance not in DIRECT | {"visual_reading", "derived"} for e in circuit.elements):
        return "unknown", "none", "Kaynağa bağlanamayan devre elemanı var."
    return "satisfied", "source_text", None


def _ideal_meters(ctx: Context):
    circuit = ctx.model.circuit
    meters = [e for e in circuit.elements if e.kind in {"ammeter", "voltmeter"}] if circuit else []
    if not meters:
        return "satisfied", "derived", None
    if all(("ideal_ammeter" if e.kind == "ammeter" else "ideal_voltmeter") in ctx.facts.stated for e in meters):
        return "satisfied", "idealization", None
    return "unknown", "none", None


def _absolute_temperature(ctx: Context):
    return "unknown", "none", None


_EVALUATORS = {
    "constant_acceleration": _constant_acceleration,
    "no_air_resistance": _stated("no_air_resistance"),
    "massless_string": _stated("massless_string"),
    "ideal_pulley": _stated("ideal_pulley"),
    "forces_established": _forces_established,
    "classical_regime": _classical,
    "sliding_state_decided": _sliding_decided,
    "friction_coefficients_given": _coefficients,
    "no_nonconservative_work": _no_nonconservative,
    "isolated_system": _isolated,
    "gravity_value_known": _gravity_known,
    "topology_established": _topology,
    "ideal_meters": _ideal_meters,
    "absolute_temperature": _absolute_temperature,
}

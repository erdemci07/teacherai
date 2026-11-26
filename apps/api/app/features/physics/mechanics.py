"""Belirlenimci mekanik çözücüleri (TA-009 §12). Kesin rasyonel aritmetik; karekök gerekirse ``units.Q.sqrt``.

Denklemleri sunucu kendisi kurar: sağlayıcının denklemleri yetkili değildir. Desteklenen biçimler:

- **Kinematik:** sabit ivmeli doğrusal hareketin beş bağıntısı (bilinen üç nicelikten yalnız hedef), aynı nicelik
  kimliğini paylaşan evrelerin zinciri (yatay atış), serbest düşme (g uzlaşımı), yön değiştiren harekette alınan
  yol ≠ yer değiştirme.
- **Dinamik:** tek cisim (yatay/eğik düzlem, uygulanan kuvvetin bileşenleri, statik–kinetik sürtünme kararı),
  makaradan geçen iple bağlı iki cisim (masa/eğik düzlem + asılı), Atwood.
- **Enerji:** kinetik ve potansiyel enerji, iş, mekanik enerji korunumu (sürtünme işi hesaba katılarak), güç.
- **Momentum:** tek doğrultuda tamamen esnek olmayan, esnek ve patlama; itme = momentum değişimi.

Desteklenmeyen yapı ``unsupported`` döner; çözüm uydurulmaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from ..reasoning.units import DimensionError, Q
from . import conventions
from .values import Value

ROLES = ("v0", "v", "a", "t", "x")


@dataclass
class Solution:
    status: str = "unsupported"  # solved | unsupported | ambiguous | blocked
    value: Fraction | None = None
    exact: bool = True
    reason: str = "no_solver"
    laws: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    derived: dict = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    used: dict = field(default_factory=dict)  # sembol → (değer metni, köken)


class Unsupported(Exception):
    pass


def _sqrt(value: Fraction) -> tuple[Fraction, bool]:
    try:
        root = Q(value).sqrt()
    except DimensionError as exc:
        raise Unsupported(str(exc)) from exc
    return root.value, root.exact


def _fmt(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{float(value):.6g}"


# --------------------------------------------------------------------------- kinematik

RELATIONS = (("x", "v = v0 + a t"), ("v", "x = v0 t + ½ a t²"), ("t", "v² = v0² + 2 a x"),
             ("a", "x = (v0 + v)/2 · t"), ("v0", "x = v t − ½ a t²"))


def suvat(known: dict[str, Fraction], target: str) -> tuple[Fraction, bool, str]:
    """Sabit ivmeli hareketin beş bağıntısından, hedefi ve bilinen üç niceliği içeren ilki seçilir.
    Döndürür (değer, kesin mi, bağıntı). Çift pozitif kök gibi belirsizlik ``Unsupported``."""
    if target in known:
        return known[target], True, "verilen"
    for lacks, relation in RELATIONS:
        if lacks == target or not (set(ROLES) - {lacks, target}) <= set(known):
            continue
        try:
            return _solve(lacks, target, known) + (relation,)
        except ZeroDivisionError as exc:
            raise Unsupported("division_by_zero") from exc
    raise Unsupported("insufficient_kinematics")


def _solve(lacks: str, target: str, k: dict[str, Fraction]) -> tuple[Fraction, bool]:
    half = Fraction(1, 2)
    v0, v, a, t, x = (k.get(r) for r in ROLES)
    if lacks == "x":  # v = v0 + a t
        if target == "t" and a == 0:
            raise Unsupported("zero_acceleration")
        return {"v": lambda: v0 + a * t, "v0": lambda: v - a * t, "a": lambda: (v - v0) / t,
                "t": lambda: (v - v0) / a}[target](), True
    if lacks == "v":  # x = v0 t + ½ a t²
        if target == "t":
            return _positive_time(half * a, v0, -x)
        return {"x": lambda: v0 * t + half * a * t * t, "a": lambda: 2 * (x - v0 * t) / (t * t),
                "v0": lambda: (x - half * a * t * t) / t}[target](), True
    if lacks == "t":  # v² = v0² + 2 a x (hız büyüklüğü)
        if target in {"v", "v0"}:
            inside = v0 * v0 + 2 * a * x if target == "v" else v * v - 2 * a * x
            return _sqrt(inside)
        if target == "x" and a == 0:
            raise Unsupported("zero_acceleration")
        return {"x": lambda: (v * v - v0 * v0) / (2 * a), "a": lambda: (v * v - v0 * v0) / (2 * x)}[target](), True
    if lacks == "a":  # x = (v0 + v)/2 · t
        return {"x": lambda: (v0 + v) / 2 * t, "t": lambda: 2 * x / (v0 + v), "v": lambda: 2 * x / t - v0,
                "v0": lambda: 2 * x / t - v}[target](), True
    # lacks == "v0": x = v t − ½ a t²
    if target == "t":
        return _positive_time(-half * a, v, -x)
    return {"x": lambda: v * t - half * a * t * t, "a": lambda: 2 * (v * t - x) / (t * t),
            "v": lambda: (x + half * a * t * t) / t}[target](), True


def _positive_time(a2: Fraction, b: Fraction, c: Fraction) -> tuple[Fraction, bool]:
    """a2 t² + b t + c = 0 için tek pozitif kök; iki pozitif kök varsa belirsiz."""
    if a2 == 0:
        if b == 0:
            raise Unsupported("degenerate_time")
        return -c / b, True
    disc = b * b - 4 * a2 * c
    if disc < 0:
        raise Unsupported("no_real_time")
    root, exact = _sqrt(disc)
    times = sorted({(-b + root) / (2 * a2), (-b - root) / (2 * a2)})
    positive = [item for item in times if item > 0]
    if len(positive) != 1:
        raise Unsupported("ambiguous_time" if positive else "no_positive_time")
    return positive[0], exact


def solve_kinematics(model, values: dict[str, Value], facts, target_id: str | None, target_kind: str) -> Solution:
    """Evre zinciri: her turda en az üç bilineni olan evre çözülür; paylaşılan nicelik kimlikleri aktarılır."""
    sol = Solution(laws=["kinematics.constant_acceleration"])
    gravity = None
    if any(p.free_fall or p.axis == "vertical" for p in model.phases):
        gravity = conventions.gravity(facts)
        if gravity is None:
            sol.status, sol.reason = "blocked", "gravity_value_unknown"
            return sol
        sol.laws.append("kinematics.free_fall")
        sol.used["g"] = (_fmt(gravity.value) + " m/s²", gravity.origin)
        # Yalnız düzgün yerçekimi etkiliyorsa (hava direnci ihmal: görünür varsayım) ivme g'dir ve sabittir.
        sol.derived["free_fall_constant"] = True
    down_positive = "aşağı" in (model.sign_convention or "").lower()
    solved: dict[str, Fraction] = {qid: v.si for qid, v in values.items()}
    for _ in range(6):
        progress = False
        for phase in model.phases:
            acceleration = None
            if phase.acceleration_kind == "zero":
                acceleration = Fraction(0)
            elif (phase.free_fall or phase.axis == "vertical") and gravity is not None and not phase.acceleration:
                acceleration = gravity.value if down_positive else -gravity.value
            mapping = {"v0": phase.initial_velocity, "v": phase.final_velocity, "a": phase.acceleration,
                       "t": phase.duration, "x": phase.displacement}
            known = {role: solved[qid] for role, qid in mapping.items() if qid and qid in solved}
            if "a" not in known and acceleration is not None:
                known["a"] = acceleration
            for role, qid in mapping.items():
                if qid and qid not in solved and len(known) >= 3:
                    try:
                        value, exact, relation = suvat(known, role)
                    except Unsupported as exc:
                        sol.reason = str(exc)
                        continue
                    solved[qid] = value
                    known[role] = value
                    sol.exact = sol.exact and exact
                    sol.steps.append(f"{phase.id}: {relation} → {role} = {_fmt(value)}")
                    progress = True
            if phase.distance and phase.distance not in solved and {"v0", "a"} <= set(known):
                distance = _distance(known)
                if distance is not None:
                    solved[phase.distance] = distance
                    sol.steps.append(f"{phase.id}: alınan yol (yön değişimi ayrı hesaplanır) = {_fmt(distance)}")
                    progress = True
        if target_id in solved and target_id not in values:
            break
        if not progress:
            break
    if target_id and target_id in solved:
        sol.status, sol.value, sol.reason = "solved", solved[target_id], "kinematics_solved"
        if target_kind in {"speed", "distance", "height"}:
            sol.value = abs(sol.value)
    elif sol.reason == "no_solver":
        sol.reason = "insufficient_kinematics"
    return sol


def _distance(known: dict[str, Fraction]) -> Fraction | None:
    """Sabit ivmede alınan yol: hız işaret değiştiriyorsa dönüş noktasına kadar ve sonrası ayrı toplanır."""
    v0, a = known["v0"], known["a"]
    t = known.get("t")
    if t is None:
        if "v" not in known or a == 0:
            return None
        t = (known["v"] - v0) / a
    if a == 0 or v0 == 0 or (v0 > 0) == (a > 0):
        return abs(v0 * t + Fraction(1, 2) * a * t * t)
    turn = -v0 / a
    if turn >= t:
        return abs(v0 * t + Fraction(1, 2) * a * t * t)
    first = abs(v0 * turn + Fraction(1, 2) * a * turn * turn)
    rest = t - turn
    return first + abs(Fraction(1, 2) * a * rest * rest)


# --------------------------------------------------------------------------- dinamik

@dataclass
class _Body:
    id: str
    mass: Fraction
    surface: object | None
    forces: list


def _trig(facts, function: str, degrees: Fraction) -> Fraction:
    choice = conventions.trig_value(facts, function, degrees)
    if choice is None:
        raise Unsupported(f"trig_value_unknown:{function}({_fmt(degrees)})")
    return choice.value


def _bodies(model, values: dict[str, Value]) -> dict[str, _Body]:
    surfaces = {item.id: item for item in model.surfaces}
    out = {}
    for body in model.bodies:
        if not body.mass or body.mass not in values:
            raise Unsupported(f"mass_unknown:{body.entity}")
        out[body.entity] = _Body(body.entity, values[body.mass].si, surfaces.get(body.surface) if body.surface else None,
                                 [f for f in model.forces if f.on == body.entity])
    return out


def _applied(body: _Body, values, facts, sol: Solution) -> tuple[Fraction, Fraction]:
    """Uygulanan kuvvetlerin (yüzey boyunca, yüzeye dik dışa doğru) bileşenleri."""
    along, normal_out = Fraction(0), Fraction(0)
    for force in body.forces:
        if force.kind not in {"applied", "spring", "electric", "magnetic", "other"}:
            continue
        if not force.magnitude or force.magnitude not in values:
            raise Unsupported(f"force_magnitude_unknown:{force.id}")
        magnitude = values[force.magnitude].si
        if force.direction in {"+x", "up_incline"}:
            along += magnitude
        elif force.direction in {"-x", "down_incline"}:
            along -= magnitude
        elif force.direction == "+y":
            normal_out += magnitude
        elif force.direction == "-y":
            normal_out -= magnitude
        elif force.direction == "angle" and force.angle_deg is not None:
            angle = Fraction(force.angle_deg)
            along += magnitude * _trig(facts, "cos", angle)
            normal_out += magnitude * _trig(facts, "sin", angle)
            sol.steps.append(f"{force.id}: bileşenler F·cos{_fmt(angle)}°, F·sin{_fmt(angle)}°")
        else:
            raise Unsupported(f"force_direction_unsupported:{force.id}")
    return along, normal_out


def _incline(body: _Body, facts) -> tuple[Fraction, Fraction]:
    """(sin α, cos α) — yatay için (0, 1)."""
    if body.surface is None or body.surface.kind == "horizontal":
        return Fraction(0), Fraction(1)
    if body.surface.kind != "incline" or body.surface.angle_deg is None:
        raise Unsupported("surface_unsupported")
    angle = Fraction(body.surface.angle_deg)
    return _trig(facts, "sin", angle), _trig(facts, "cos", angle)


def _friction(body: _Body, values, facts, sol: Solution) -> tuple[Fraction | None, Fraction | None]:
    """(μ_s, μ_k). Sürtünmesiz yalnız kaynakta yazılıysa; tek katsayı verilmişse ikisi eşit alınır (görünür varsayım)."""
    surface = body.surface
    if surface is None:
        return Fraction(0), Fraction(0)
    if surface.friction == "none":
        if "frictionless" not in facts.stated:
            sol.assumptions.append("Yüzey sürtünmesiz kabul edildi (soruda açıkça yazılı değil).")
        return Fraction(0), Fraction(0)
    mu_s = values[surface.mu_static].si if surface.mu_static and surface.mu_static in values else None
    mu_k = values[surface.mu_kinetic].si if surface.mu_kinetic and surface.mu_kinetic in values else None
    if mu_s is None and mu_k is None:
        if "frictionless" in facts.stated and "frictionless" not in facts.contradicted:
            return Fraction(0), Fraction(0)
        raise Unsupported("friction_unknown")
    if mu_s is None or mu_k is None:
        sol.assumptions.append("Tek sürtünme katsayısı verildiği için statik ve kinetik katsayılar eşit alındı.")
        mu_s = mu_s if mu_s is not None else mu_k
        mu_k = mu_k if mu_k is not None else mu_s
    if mu_s < 0 or mu_k < 0:
        raise Unsupported("negative_friction_coefficient")
    return mu_s, mu_k


def solve_dynamics(model, values: dict[str, Value], facts, target_kind: str, target_entity: str | None,
                   at_rest: bool) -> Solution:
    sol = Solution(laws=["dynamics.newton_second"])
    gravity = conventions.gravity(facts)
    if gravity is None:
        sol.status, sol.reason = "blocked", "gravity_value_unknown"
        return sol
    g = gravity.value
    sol.used["g"] = (_fmt(g) + " m/s²", gravity.origin)
    try:
        bodies = _bodies(model, values)
        if len(bodies) == 1 and not model.strings:
            result = _single(next(iter(bodies.values())), values, facts, g, at_rest, sol)
        elif len(bodies) == 2 and len(model.strings) == 1:
            sol.laws.append("dynamics.ideal_string")
            result = _pair(bodies, model.strings[0], values, facts, g, at_rest, sol)
        else:
            raise Unsupported("dynamics_configuration_unsupported")
    except Unsupported as exc:
        sol.status, sol.reason = "unsupported", str(exc)
        return sol
    sol.derived["net_force_constant"] = True
    key = {"acceleration": "a", "acceleration_magnitude": "a", "tension": "T", "normal_force": "N",
           "friction_force": "f", "net_force": "F"}.get(target_kind)
    value = result.get(key) if key else None
    if isinstance(value, dict):
        value = value.get(target_entity) if target_entity else (next(iter(value.values())) if len(value) == 1 else None)
    if value is None:
        sol.status, sol.reason = "unsupported", "dynamics_target_unsupported"
        sol.derived["acceleration"] = result.get("a")
        return sol
    sol.status, sol.value, sol.reason = "solved", value, "dynamics_solved"
    sol.derived["acceleration"] = result.get("a")
    return sol


def _single(body: _Body, values, facts, g, at_rest, sol: Solution) -> dict:
    sin_a, cos_a = _incline(body, facts)
    along, out = _applied(body, values, facts, sol)
    gravity_along = -body.mass * g * sin_a  # eğik düzlemde aşağı (+ yön: yukarı)
    normal = body.mass * g * cos_a - out
    if normal < 0:
        raise Unsupported("body_leaves_surface")
    drive = along + gravity_along
    mu_s, mu_k = _friction(body, values, facts, sol)
    sol.derived["friction_needed"] = bool(mu_s or mu_k)
    sol.derived["friction_coefficients"] = mu_s is not None
    if mu_s == 0 and mu_k == 0:
        sol.derived["sliding"] = "frictionless"
        a = drive / body.mass
        friction = Fraction(0)
    elif at_rest and abs(drive) <= mu_s * normal:
        sol.laws.append("dynamics.friction")
        sol.derived["sliding"] = "static"
        sol.steps.append(f"Kayma denetimi: |F_sürükleyen| = {_fmt(abs(drive))} N ≤ μ_s N = {_fmt(mu_s * normal)} N → cisim kaymaz")
        a, friction = Fraction(0), abs(drive)
        # Yanılgı izi: kaymadığı hâlde kinetik sürtünmeyle bulunan ivme (TA-009 §15).
        sol.derived["misconception_value"] = ("kinetic_friction_while_static",
                                              (drive - (1 if drive > 0 else -1) * mu_k * normal) / body.mass)
    else:
        sol.laws.append("dynamics.friction")
        sol.derived["sliding"] = "kinetic"
        friction = mu_k * normal
        direction = 1 if drive > 0 else -1
        if not at_rest:
            direction = 1  # hareket yönü sağlayıcı modelinden alınmaz; ilk hız yönü + kabul edilir
        a = (drive - direction * friction) / body.mass
        sol.steps.append(f"Kayma var: f_k = μ_k N = {_fmt(friction)} N")
    sol.steps.append(f"N = {_fmt(normal)} N; a = {_fmt(a)} m/s²")
    return {"a": a, "N": {body.id: normal}, "f": friction, "F": body.mass * a}


def _pair(bodies: dict[str, _Body], link, values, facts, g, at_rest, sol: Solution) -> dict:
    first, second = (bodies[b] for b in link.bodies)
    hanging = [b for b in (first, second) if b.surface is None or b.surface.kind == "vertical"]
    if len(hanging) == 2:  # Atwood
        heavy, light = (first, second) if first.mass >= second.mass else (second, first)
        total = heavy.mass + light.mass
        a = (heavy.mass - light.mass) * g / total
        tension = 2 * heavy.mass * light.mass * g / total
        sol.steps.append(f"Atwood: a = (m₁ − m₂) g / (m₁ + m₂) = {_fmt(a)} m/s²")
        sol.derived["sliding"] = "frictionless"
        sol.derived["friction_needed"] = False
        return {"a": a, "T": tension, "F": {heavy.id: heavy.mass * a, light.id: light.mass * a}}
    if len(hanging) != 1:
        raise Unsupported("pulley_configuration_unsupported")
    hang = hanging[0]
    table = first if hang is second else second
    sin_a, cos_a = _incline(table, facts)
    along, out = _applied(table, values, facts, sol)
    normal = table.mass * g * cos_a - out
    mu_s, mu_k = _friction(table, values, facts, sol)
    sol.derived["friction_needed"] = bool(mu_s or mu_k)
    sol.derived["friction_coefficients"] = mu_s is not None
    # + yön: asılı cisim aşağı, masadaki cisim makaraya doğru (eğik düzlemde yukarı).
    drive = hang.mass * g - table.mass * g * sin_a + along
    total = table.mass + hang.mass
    if mu_s == 0 and mu_k == 0:
        sol.derived["sliding"] = "frictionless"
        a = drive / total
    elif at_rest and abs(drive) <= mu_s * normal:
        sol.laws.append("dynamics.friction")
        sol.derived["sliding"] = "static"
        sol.steps.append(f"Kayma denetimi: |sürükleyen| = {_fmt(abs(drive))} N ≤ μ_s N = {_fmt(mu_s * normal)} N → sistem durur")
        a = Fraction(0)
        sol.derived["misconception_value"] = ("kinetic_friction_while_static",
                                              (drive - (1 if drive > 0 else -1) * mu_k * normal) / total)
    else:
        sol.laws.append("dynamics.friction")
        sol.derived["sliding"] = "kinetic"
        friction = mu_k * normal
        a = (drive - (friction if drive > 0 else -friction)) / total
    tension = hang.mass * (g - a)
    sol.steps.append(f"Sistem: a = {_fmt(a)} m/s²; asılı cisim için T = m(g − a) = {_fmt(tension)} N")
    return {"a": a, "T": tension, "N": {table.id: normal}, "F": {table.id: table.mass * a, hang.id: hang.mass * a}}


# --------------------------------------------------------------------------- enerji ve momentum

def solve_energy(model, values: dict[str, Value], facts, target_kind: str, target_id: str | None) -> Solution:
    """Hareket evresi + yükseklik/yol: v² = v0² + 2 g h − 2 (f_k d)/m (sürtünme işi hesaba katılır)."""
    sol = Solution(laws=["energy.mechanical_conservation"])
    gravity = conventions.gravity(facts)
    if gravity is None:
        sol.status, sol.reason = "blocked", "gravity_value_unknown"
        return sol
    g = gravity.value
    sol.used["g"] = (_fmt(g) + " m/s²", gravity.origin)
    if len(model.bodies) != 1 or len(model.phases) != 1:
        sol.reason = "energy_configuration_unsupported"
        return sol
    body, phase = model.bodies[0], model.phases[0]
    mass = values[body.mass].si if body.mass in values else None
    height = next((v.si for v in values.values() if v.kind == "height"), None)
    v0 = values[phase.initial_velocity].si if phase.initial_velocity in values else (
        Fraction(0) if "starts_from_rest" in facts.stated else None)
    if target_kind == "kinetic_energy" and mass is not None and phase.final_velocity in values:
        speed = values[phase.final_velocity].si
        sol.status, sol.value, sol.reason = "solved", mass * speed * speed / 2, "kinetic_energy"
        sol.laws = ["energy.work_energy"]
        return sol
    if target_kind == "potential_energy" and mass is not None and height is not None:
        sol.status, sol.value, sol.reason = "solved", mass * g * height, "potential_energy"
        return sol
    if target_kind not in {"speed", "velocity"} or height is None or v0 is None:
        sol.reason = "energy_target_unsupported"
        return sol
    loss = Fraction(0)
    surface = next((s for s in model.surfaces if s.id == body.surface), None)
    if surface is not None and surface.friction == "present":
        if mass is None or not surface.mu_kinetic or surface.mu_kinetic not in values or phase.distance not in values:
            sol.status, sol.reason = "blocked", "friction_work_unknown"
            return sol
        angle = Fraction(surface.angle_deg or 0)
        cos_a = _trig(facts, "cos", angle) if surface.kind == "incline" else Fraction(1)
        loss = values[surface.mu_kinetic].si * mass * g * cos_a * values[phase.distance].si
        sol.derived["nonconservative_work_accounted"] = True
        sol.steps.append(f"Sürtünmenin işi: μ_k m g cosα · d = {_fmt(loss)} J")
        inside = v0 * v0 + 2 * g * height - 2 * loss / mass
    else:
        inside = v0 * v0 + 2 * g * height
    if inside < 0:
        sol.status, sol.reason = "solved", "body_does_not_reach"
        sol.value = Fraction(0)
        return sol
    root, exact = _sqrt(inside)
    sol.status, sol.value, sol.exact, sol.reason = "solved", root, exact, "energy_conservation"
    sol.steps.append(f"½ m v² = ½ m v0² + m g h − W_sürtünme → v = {_fmt(root)} m/s")
    return sol


def solve_momentum(model, values: dict[str, Value], target_id: str | None, target_kind: str) -> Solution:
    sol = Solution(laws=["momentum.conservation"])
    if len(model.collisions) != 1:
        sol.reason = "momentum_configuration_unsupported"
        return sol
    collision = model.collisions[0]
    masses = {b.entity: values[b.mass].si for b in model.bodies if b.mass in values}
    if set(collision.bodies) - set(masses):
        sol.reason = "mass_unknown"
        return sol
    m1, m2 = (masses[b] for b in collision.bodies)
    before = [values[q].si if q and q in values else None for q in collision.velocities_before] + [None, None]
    after_ids = list(collision.velocities_after) + [None, None]
    after = [values[q].si if q and q in values else None for q in after_ids[:2]]
    u1, u2 = before[0], before[1]
    if u1 is None or u2 is None:
        sol.reason = "initial_velocity_unknown"
        return sol
    total = m1 * u1 + m2 * u2
    if collision.kind == "perfectly_inelastic":
        common = total / (m1 + m2)
        results = {after_ids[0]: common, after_ids[1]: common}
        sol.steps.append(f"Yapışık: v' = (m₁u₁ + m₂u₂)/(m₁ + m₂) = {_fmt(common)} m/s")
    elif collision.kind == "elastic":
        v1 = ((m1 - m2) * u1 + 2 * m2 * u2) / (m1 + m2)
        v2 = ((m2 - m1) * u2 + 2 * m1 * u1) / (m1 + m2)
        results = {after_ids[0]: v1, after_ids[1]: v2}
        sol.steps.append(f"Esnek: v₁' = {_fmt(v1)} m/s, v₂' = {_fmt(v2)} m/s")
    elif after[0] is not None and after_ids[1]:
        results = {after_ids[1]: (total - m1 * after[0]) / m2}
    elif after[1] is not None and after_ids[0]:
        results = {after_ids[0]: (total - m2 * after[1]) / m1}
    else:
        sol.reason = "collision_kind_unknown"
        return sol
    if target_id in results:
        sol.status, sol.value, sol.reason = "solved", results[target_id], "momentum_solved"
        if target_kind == "speed":
            sol.value = abs(sol.value)
        energy_before = (m1 * u1 * u1 + m2 * u2 * u2) / 2
        finals = [results.get(after_ids[0], after[0]), results.get(after_ids[1], after[1])]
        if None not in finals:
            energy_after = (m1 * finals[0] ** 2 + m2 * finals[1] ** 2) / 2
            sol.derived["kinetic_energy_change"] = energy_after - energy_before
    else:
        sol.reason = "momentum_target_unsupported"
    return sol

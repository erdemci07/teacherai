"""Fizik doğrulama hattı (TA-009 §9–§13). Sağlayıcının modeli yetkili değildir; desteklenen denetimler geçene kadar
yalnız öneridir. Ayrılan adımlar: kaynak yorumu → kanıt → nicelikler → sistem → varsayımlar → yasa uygulanabilirliği
→ belirlenimci çözüm → istenen hedef → türlü cevap karşılaştırması. Açıklama ve tahta bu raporu kullanır.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from ..education.physics import PhysicsCheck, PhysicsCondition, PhysicsReport, ValueUse
from ..education.science import ScientificProblemModel
from ..reasoning import formula, quantities
from ..reasoning.units import UnitError, parse_unit
from . import circuits, conventions, graphs, laws, mechanics
from .values import Value, resolve

DYNAMICS_TARGETS = {"acceleration", "acceleration_magnitude", "tension", "normal_force", "friction_force", "net_force"}
KINEMATIC_TARGETS = {"speed", "velocity", "displacement", "distance", "time", "height"}
C_LIGHT = Fraction(299792458)
MATERIAL = {"answer_mismatch", "intermediate_not_requested", "law_not_applicable", "dimension_inconsistent",
            "implausible_value", "energy_increase_without_input"}


def verify(problem: ScientificProblemModel, source_text: str, claims: list[str],
           confirmed: tuple[str, ...] = ()) -> PhysicsReport:
    model = problem.physics
    report = PhysicsReport()
    if model is None:
        report.notes_tr.append("Fiziksel model yok; fizik doğrulaması yapılmadı.")
        return report
    report.domain = model.domain
    checks: list[PhysicsCheck] = []

    def add(id_, area, status, reason, detail=None):
        reason, _, extra = reason.partition(":")  # "trig_value_unknown:sin(37)" → neden + ayrıntı
        detail = detail or (extra or None)
        checks.append(PhysicsCheck(id=id_, area=area, status=status, reason=reason, detail=detail,
                                   material=status == "failed" and reason in MATERIAL))

    facts = conventions.read(source_text)
    resolved = resolve(problem, source_text, facts, confirmed)
    values = resolved.values
    for item in resolved.problems:
        add(f"value_{item}", "source", "unsupported", "value_unparsed")
    referenced = _referenced(model)
    resolved.unverified = [item for item in resolved.unverified if item in referenced]
    resolved.visual = [item for item in resolved.visual if item in referenced]
    for item in resolved.unverified:
        add(f"value_{item}", "source", "not_checked", "value_not_anchored",
            "Değer kaynağa, uzlaşıma veya kaynaklı sabite bağlanamadı; yalnız sağlayıcı önerisi.")
    target = model.target
    report.target_kind = target.kind if target else None
    _dimensions(problem, add)
    ctx = laws.Context(problem, model, facts, source_text, {k: v.si for k, v in values.items()},
                       {"kinds": {k: v.kind for k, v in values.items()}})
    graph_value = _graph(problem, model, target, ctx, add)
    # Sağlayıcının yasa iddiaları, sunucunun kendi çözümündeki düzeltmeler (ör. sürtünme işini eklemek) uygulanmadan,
    # yalnız kaynak ve grafik olgularına karşı değerlendirilir: sürtünmeyi yok sayan korunum iddiası böyle yakalanır.
    for use in model.laws:
        if use.law not in laws.LAWS:
            continue
        for result in laws.evaluate(use.law, ctx):
            if result.state == "violated":
                add(f"law_{use.law}_{result.condition}", "law", "failed", "law_not_applicable",
                    f"{laws.LAWS[use.law].title_tr}: {result.detail or result.condition}")
    solution = _dispatch(problem, model, values, facts, target, ctx) if graph_value is None else graph_value
    ctx.derived.update(solution.derived)
    for law_id in dict.fromkeys(solution.laws):
        for result in laws.evaluate(law_id, ctx):
            report.conditions.append(_condition(result))
    blocked = [c for c in report.conditions if c.state == "violated" and c.law in solution.laws]
    open_conditions = [c for c in report.conditions if c.state == "unknown" and c.assumption_tr is None]
    report.laws = list(dict.fromkeys(solution.laws))[:12]
    report.assumptions_tr = list(dict.fromkeys(
        [*solution.assumptions, *[c.assumption_tr for c in report.conditions if c.assumption_tr]]))[:16]
    report.steps_tr = solution.steps[:24]
    report.values_used = _values_used(values, solution)
    _plausibility(problem, model, values, solution, add)
    if solution.status == "needs_clarification":
        report.clarification_needed = True
        report.clarification_tr = solution.reason
    if blocked:
        add("law_blocked", "law", "unsupported", "law_condition_violated",
            "; ".join(f"{c.law}: {c.detail or c.condition}" for c in blocked)[:400])
    if solution.status == "solved" and not blocked:
        report.computed = _show(solution.value, target.kind if target else None)
        add("solution", "solution", "passed" if solution.exact else "partially_checked", solution.reason)
        _answer(report, solution, problem, target, claims, add)
    elif solution.status != "needs_clarification" and not blocked:
        add("solution", "solution", "unsupported", solution.reason or "no_solver")
    report.checks = sorted(checks, key=lambda c: (not c.material, c.status != "failed"))[:64]
    report.material_count = sum(1 for c in checks if c.material)
    report.capability = _capability(report, solution, resolved, open_conditions, blocked)
    return report


def _dispatch(problem, model, values, facts, target, ctx) -> mechanics.Solution:
    if target is None:
        return mechanics.Solution(reason="target_missing")
    kind = target.kind
    at_rest = "starts_from_rest" in facts.stated or any(
        p.initial_velocity in values and values[p.initial_velocity].si == 0 for p in model.phases)
    if model.domain == "dc_circuit" and model.circuit is not None:
        return _circuit(model, values, target)
    if model.domain == "momentum":
        return mechanics.solve_momentum(model, values, target.quantity, kind)
    if model.domain == "energy":
        return mechanics.solve_energy(model, values, facts, kind, target.quantity)
    if model.domain == "dynamics":
        if kind in DYNAMICS_TARGETS:
            return mechanics.solve_dynamics(model, values, facts, kind, target.entity, at_rest)
        if kind in KINEMATIC_TARGETS and model.phases:
            dyn = mechanics.solve_dynamics(model, values, facts, "acceleration", target.entity, at_rest)
            if dyn.status != "solved":
                return dyn
            return _kinematics_with(model, values, facts, target, dyn)
    if model.domain == "kinematics":
        return mechanics.solve_kinematics(model, values, facts, target.quantity, kind)
    return mechanics.Solution(reason="domain_unsupported")


def _kinematics_with(model, values, facts, target, dyn) -> mechanics.Solution:
    phase = model.phases[0]
    aid = phase.acceleration or "derived_acceleration"
    injected = {**values, aid: Value(aid, "a", dyn.value, (1, 0, -2, 0, 0, 0, 0), "acceleration", "derived", "a")}
    phases = [phase.model_copy(update={"acceleration": aid, "acceleration_kind": "constant"}), *model.phases[1:]]
    kin = mechanics.solve_kinematics(model.model_copy(update={"phases": phases}), injected, facts, target.quantity,
                                     target.kind)
    kin.laws = [*dyn.laws, *kin.laws]
    kin.steps = [*dyn.steps, *kin.steps]
    kin.assumptions = [*dyn.assumptions, *kin.assumptions]
    kin.derived = {**dyn.derived, **kin.derived, "net_force_constant": True}
    kin.used = {**dyn.used, **kin.used}
    return kin


def _circuit(model, values, target) -> mechanics.Solution:
    sol = mechanics.Solution(laws=["circuit.ohm", "circuit.kirchhoff"])
    if target.kind == "resistance" and len(target.between) == 2:
        value = circuits.equivalent_resistance(model.circuit, values, *target.between)
        if value is None:
            sol.reason = "equivalent_resistance_unsupported"
            return sol
        sol.status, sol.value, sol.reason = "solved", value, "equivalent_resistance"
        sol.steps.append(f"Eşdeğer direnç (bağlantı grafiğinden) = {mechanics._fmt(value)} Ω")
        return sol
    solved = circuits.solve(model.circuit, values)
    sol.steps.extend(solved.steps)
    if solved.status == "needs_clarification":
        sol.status = "needs_clarification"
        sol.reason = ("Devrede bağlantısı kesin olmayan eleman var: " + ", ".join(solved.uncertain) +
                      ". Seri/paralel kararı tahminle verilmez; bağlantının öğrenciye sorulması gerekir.")
        return sol
    if solved.status != "solved":
        sol.reason = solved.reason
        return sol
    element = target.element
    current, voltage = solved.currents.get(element), solved.voltages.get(element)
    resistance = None
    item = next((e for e in model.circuit.elements if e.id == element), None)
    if item is not None and item.value in values and item.kind in {"resistor", "bulb"}:
        resistance = values[item.value].si
    value = {"current": abs(current) if current is not None else None,
             "voltage": abs(voltage) if voltage is not None else None,
             "power": (current * current * resistance) if current is not None and resistance is not None else None,
             }.get(target.kind)
    if value is None:
        sol.reason = "circuit_target_unsupported"
        return sol
    sol.status, sol.value, sol.reason = "solved", value, "nodal_analysis"
    return sol


def _graph(problem, model, target, ctx, add) -> mechanics.Solution | None:
    """Hız–zaman grafiği: sabitlik koşulu ve (hedef grafikten okunuyorsa) yer değiştirme/yol."""
    graphs_by_id = {g.id: g for g in problem.graphs}
    for phase in model.phases:
        if not phase.graph or phase.graph not in graphs_by_id:
            continue
        facts = graphs.velocity_time(graphs_by_id[phase.graph])
        if facts.status != "ready":
            add(f"graph_{phase.graph}", "graph", "unsupported", facts.reason)
            continue
        ctx.derived["acceleration_constancy"] = "constant" if facts.constant_slope else "varying"
        add(f"graph_{phase.graph}", "graph", "passed", "graph_read",
            f"Yer değiştirme (işaretli alan) = {mechanics._fmt(facts.displacement)} m; alınan yol (|v| alanı) = "
            f"{mechanics._fmt(facts.distance)} m")
        if target is not None and target.kind in {"displacement", "distance"}:
            sol = mechanics.Solution(status="solved", reason="graph_area", laws=[])
            sol.value = facts.displacement if target.kind == "displacement" else facts.distance
            if facts.displacement != facts.distance:  # yanılgı izi: alanı yol (veya yolu yer değiştirme) saymak
                sol.derived["misconception_value"] = (
                    "graph_area_as_distance" if target.kind == "distance" else "distance_as_displacement",
                    facts.displacement if target.kind == "distance" else facts.distance)
            sol.steps.append("Hız–zaman grafiğinin altındaki alan: yer değiştirme işaretli, alınan yol |v| alanıdır.")
            return sol
    return None


def _answer(report, solution, problem, target, claims, add):
    symbols = {q.symbol: q for q in problem.known + problem.unknown if q.symbol}
    kinds = {symbol: q.kind for symbol, q in symbols.items() if q.kind}
    unit = None
    if target.unit is not None:
        try:
            unit = parse_unit(target.unit.original)
        except UnitError:
            unit = None
    spec = quantities.KINDS.get(target.kind)
    expected = quantities.Typed(solution.value, spec.dim if spec else (unit.dim if unit else None), target.kind,
                                representation=target.representation, entity=target.entity, state=target.state,
                                exact=solution.exact)
    outcomes = []
    for text in claims:
        parsed = quantities.parse_claim(text, kinds)
        if parsed is None:
            continue
        quantity = symbols.get(parsed.symbol or "")
        if quantity is not None and target.quantity and quantity.id != target.quantity:
            outcomes.append(("mismatch", ("intermediate_not_requested",), text, None))
            continue
        claimed = parsed.typed
        if quantity is not None:
            claimed = replace(claimed, entity=quantity.entity, state=quantity.state, kind=claimed.kind or quantity.kind)
        policy = quantities.Policy(mode="exact" if solution.exact and not claimed.decimals else "claim_precision",
                                   unit_when_missing=unit)
        result = quantities.compare(expected, claimed, policy)
        outcomes.append((result.status, result.reasons, text, claimed))
    if not outcomes:
        report.answer = "absent" if not claims else "undecidable"
        add("answer", "answer", "not_checked", "claim_unparsed" if claims else "claim_absent")
        return
    decided = [o for o in outcomes if o[0] != "undecidable"]
    if not decided:
        report.answer, report.answer_reasons = "undecidable", list(outcomes[0][1])[:8]
        add("answer", "answer", "not_checked", outcomes[0][1][0] if outcomes[0][1] else "claim_undecidable")
        return
    if any(o[0] == "mismatch" for o in decided):
        bad = next(o for o in decided if o[0] == "mismatch")
        report.answer, report.answer_reasons = "mismatch", list(bad[1])[:8]
        reason = "intermediate_not_requested" if "intermediate_not_requested" in bad[1] else "answer_mismatch"
        add("answer", "answer", "failed", reason,
            f"Bağımsız değer {report.computed}; son cevap {bad[2]} ({', '.join(bad[1])}).")
        trace = solution.derived.get("misconception_value")
        claimed = bad[3]
        if trace and claimed is not None and claimed.value is not None and _same_value(claimed, trace[1], unit):
            # Yanılgı adlandırılır; maddi sayım yukarıdaki cevap uyuşmazlığıdır (çift sayılmaz).
            add("misconception", "answer", "partially_checked", f"misconception_{trace[0]}",
                "Cevap bilinen bir yanılgıyla elde edilen değerle aynı.")
        return
    report.answer = "matched"
    add("answer", "answer", "passed", "answer_matches_target", f"Bağımsız değer {report.computed}.")


def _same_value(claimed, value: Fraction, unit) -> bool:
    got = claimed.value if claimed.dim is not None or unit is None else claimed.value * unit.scale
    return abs(got - value) <= max(abs(value) * Fraction(1, 10**6), Fraction(1, 10**9))


def _dimensions(problem, add):
    """Sağlayıcı denklemlerinin boyut tutarlılığı (yasanın doğru seçildiğini kanıtlamaz)."""
    units = {q.symbol: q.unit.original for q in problem.known + problem.unknown
             if q.symbol and q.unit is not None and q.unit.status == "parsed"}
    for index, equation in enumerate(problem.physics.equations):
        outcome = formula.check_dimensions(equation, units)
        if outcome.outcome == "failed":
            add(f"equation_{index}", "dimension", "failed", "dimension_inconsistent", equation[:400])
        elif outcome.outcome == "partially_checked":
            add(f"equation_{index}", "dimension", "passed", "dimensions_consistent", equation[:400])
        else:
            add(f"equation_{index}", "dimension", "not_checked", outcome.reason, equation[:400])


def _plausibility(problem, model, values: dict[str, Value], solution, add):
    """Sınırlı ve belgelenmiş akla yatkınlık denetimleri. İhlal maddi çelişkidir."""
    for value in values.values():
        rule = {"mass": lambda v: v > 0, "resistance": lambda v: v > 0, "capacitance": lambda v: v > 0,
                "speed": lambda v: v < C_LIGHT, "efficiency": lambda v: 0 <= v <= 1,
                "kinetic_energy": lambda v: v >= 0, "time": lambda v: v >= 0}.get(value.kind or "")
        if rule is not None and not rule(value.si):
            add(f"plausible_{value.id}", "plausibility", "failed", "implausible_value",
                f"{value.symbol or value.id} = {value.text} fiziksel olarak olanaksız.")
    for surface in model.surfaces:
        for mu in (surface.mu_static, surface.mu_kinetic):
            if mu in values and values[mu].si < 0:
                add(f"plausible_{mu}", "plausibility", "failed", "implausible_value", "Sürtünme katsayısı negatif olamaz.")
    change = solution.derived.get("kinetic_energy_change")
    if change is not None and change > 0 and not any(c.kind == "explosion" for c in model.collisions):
        add("energy_balance", "plausibility", "failed", "energy_increase_without_input",
            "Çarpışmada kinetik enerji artıyor; enerji girdisi olmadan olanaksız.")
    if solution.status == "solved" and solution.value is not None:
        kind = problem.physics.target.kind if problem.physics.target else None
        if kind in {"speed", "velocity"} and abs(solution.value) >= C_LIGHT:
            add("plausible_result", "plausibility", "failed", "implausible_value", "Hız ışık hızından büyük çıktı.")


def _capability(report, solution, resolved, open_conditions, blocked) -> str:
    if solution.status != "solved" or blocked or report.clarification_needed:
        return "unsupported"
    if resolved.unverified or any(c.reason == "value_not_anchored" for c in report.checks):
        return "interpreted"
    if any(c.condition == "forces_established" and c.state != "satisfied" for c in report.conditions):
        return "interpreted"
    if open_conditions or resolved.visual or report.answer != "matched":
        return "partially_checked"
    if any(c.status in {"failed", "unsupported"} for c in report.checks):
        return "partially_checked"
    return "verified"


def _referenced(model) -> set[str]:
    """Fiziksel modelin gerçekten kullandığı nicelikler (kullanılmayan bir değer sonucu sınırlamaz)."""
    refs = [b.mass for b in model.bodies] + [f.magnitude for f in model.forces]
    refs += [s.mu_static for s in model.surfaces] + [s.mu_kinetic for s in model.surfaces]
    for phase in model.phases:
        refs += [phase.initial_velocity, phase.final_velocity, phase.displacement, phase.distance, phase.duration,
                 phase.acceleration]
    for collision in model.collisions:
        refs += [*collision.velocities_before, *collision.velocities_after]
    if model.circuit is not None:
        refs += [e.value for e in model.circuit.elements] + [e.internal_resistance for e in model.circuit.elements]
    return {ref for ref in refs if ref}


def _condition(result) -> PhysicsCondition:
    return PhysicsCondition(law=result.law, condition=result.condition, state=result.state, basis=result.basis,
                            assumption_tr=result.assumption_tr, detail=str(result.detail)[:400] if result.detail else None)


def _values_used(values: dict[str, Value], solution) -> list[ValueUse]:
    out = [ValueUse(symbol=v.symbol or v.id, value=v.text[:256], origin=v.origin) for v in values.values()]
    for symbol, (text, origin) in solution.used.items():
        source = None
        if origin == "standard_constant":
            source = "Soru değer vermediği için standart değer kullanıldı: " + text
        out.append(ValueUse(symbol=symbol, value=text, origin=origin, source=source))
    return out[:32]


def _show(value: Fraction | None, kind: str | None) -> str | None:
    if value is None:
        return None
    unit = {"speed": "m/s", "velocity": "m/s", "acceleration": "m/s²", "acceleration_magnitude": "m/s²", "time": "s",
            "displacement": "m", "distance": "m", "height": "m", "tension": "N", "normal_force": "N",
            "friction_force": "N", "net_force": "N", "kinetic_energy": "J", "potential_energy": "J", "energy": "J",
            "current": "A", "voltage": "V", "resistance": "Ω", "power": "W"}.get(kind or "", "")
    return f"{mechanics._fmt(value)} {unit}".strip()

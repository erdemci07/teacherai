"""Doğru akım devreleri: topoloji grafiğinden değiştirilmiş düğüm analizi (TA-009 §12, §14).

Seri/paralel kararı görsel yakınlıktan değil yalnız düğüm grafiğinden çıkar. Kesin rasyonel Gauss eliminasyonu
kullanılır; tekil sistem (kısa devre edilmiş ideal kaynak, yüzen düğüm) ``unsupported`` olur.

- Direnç ve lamba: ohmik direnç (lamba direnci sabit kabulü görünür varsayımdır).
- Üreteç: EMK ve iç direnç (seri); ``positive_node`` artı ucu belirtir.
- Anahtar: kapalıysa ideal tel, açıksa devre dışı; durumu bilinmiyorsa çözülmez.
- İdeal ampermetre: sıfır gerilimli kaynak (akımı ölçülür); ideal voltmetre: açık devre (gerilimi ölçülür).
- Bağlantısı kesin olmayan eleman varsa çözüm yapılmaz: hedefli açıklama gerekir (tahmin yok).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from ..education.science import CircuitModel
from .values import Value

MAX_UNKNOWNS = 40


@dataclass
class CircuitSolution:
    status: str = "unsupported"  # solved | unsupported | needs_clarification
    reason: str = ""
    potentials: dict[str, Fraction] = field(default_factory=dict)
    currents: dict[str, Fraction] = field(default_factory=dict)  # eleman → akım (nodes[0] → nodes[1] yönünde)
    voltages: dict[str, Fraction] = field(default_factory=dict)  # eleman → V(nodes[0]) − V(nodes[1])
    uncertain: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)


class _Singular(Exception):
    pass


def _solve_linear(matrix: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction]:
    n = len(rhs)
    rows = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if rows[r][col] != 0), None)
        if pivot is None:
            raise _Singular
        rows[col], rows[pivot] = rows[pivot], rows[col]
        lead = rows[col][col]
        rows[col] = [value / lead for value in rows[col]]
        for r in range(n):
            if r != col and rows[r][col] != 0:
                factor = rows[r][col]
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[col])]
    return [rows[i][n] for i in range(n)]


def _resistance(element, values: dict[str, Value]) -> Fraction | None:
    if element.value and element.value in values:
        return values[element.value].si
    return None


def solve(circuit: CircuitModel, values: dict[str, Value]) -> CircuitSolution:
    sol = CircuitSolution()
    uncertain = [e.id for e in circuit.elements if not e.connection_certain]
    if uncertain:
        sol.status, sol.reason, sol.uncertain = "needs_clarification", "connection_uncertain", uncertain
        return sol
    switches = [e for e in circuit.elements if e.kind == "switch" and e.closed is None]
    if switches:
        sol.status, sol.reason, sol.uncertain = "needs_clarification", "switch_state_unknown", [e.id for e in switches]
        return sol
    batteries = [e for e in circuit.elements if e.kind == "battery"]
    if not batteries:
        sol.reason = "no_source"
        return sol
    ground = _negative(batteries[0])
    connected = {n for e in circuit.elements for n in e.nodes}
    nodes = [n for n in circuit.nodes if n != ground and n in connected]  # yalıtık düğüm denklem sistemine girmez
    index = {n: i for i, n in enumerate(nodes)}
    resistors, sources = [], []  # sources: (eleman, artı düğüm, eksi düğüm, emk)
    for element in circuit.elements:
        a, b = element.nodes
        if element.kind in {"resistor", "bulb"}:
            r = _resistance(element, values)
            if r is None or r <= 0:
                sol.reason = f"resistance_unknown:{element.id}"
                return sol
            resistors.append((element, a, b, r))
        elif element.kind == "battery":
            emf = _resistance(element, values)
            if emf is None:
                sol.reason = f"emf_unknown:{element.id}"
                return sol
            plus = element.positive_node or a
            minus = b if plus == a else a
            internal = values[element.internal_resistance].si if element.internal_resistance in values else Fraction(0)
            if internal:
                inner = f"{element.id}__inner"
                nodes.append(inner)
                index[inner] = len(nodes) - 1
                sources.append((element, inner, minus, emf))
                resistors.append((element, plus, inner, internal))  # iç direnç: artı uç → iç düğüm
            else:
                sources.append((element, plus, minus, emf))
        elif element.kind in {"wire", "ammeter"} or (element.kind == "switch" and element.closed):
            sources.append((element, a, b, Fraction(0)))
        # açık anahtar ve ideal voltmetre: akım yolu yok
    size = len(nodes) + len(sources)
    if size > MAX_UNKNOWNS:
        sol.reason = "circuit_too_large"
        return sol
    matrix = [[Fraction(0)] * size for _ in range(size)]
    rhs = [Fraction(0)] * size

    def node(name):
        return index.get(name)

    for _, a, b, r in resistors:
        g = 1 / r
        for p, q in ((a, b), (b, a)):
            if node(p) is not None:
                matrix[node(p)][node(p)] += g
                if node(q) is not None:
                    matrix[node(p)][node(q)] -= g
    for k, (_, plus, minus, emf) in enumerate(sources):
        row = len(nodes) + k
        for name, sign in ((plus, 1), (minus, -1)):
            if node(name) is not None:
                matrix[node(name)][row] += sign
                matrix[row][node(name)] += sign
        rhs[row] = emf
    try:
        solution = _solve_linear(matrix, rhs)
    except _Singular:
        sol.reason = "singular_circuit"
        return sol
    potential = {n: solution[i] for n, i in index.items()}
    potential[ground] = Fraction(0)
    sol.potentials = {n: v for n, v in potential.items() if "__" not in n}
    for element, a, b, r in resistors:
        if element.kind == "battery":
            continue
        sol.voltages[element.id] = potential[a] - potential[b]
        sol.currents[element.id] = (potential[a] - potential[b]) / r
    for k, (element, plus, minus, _) in enumerate(sources):
        # MNA'da kaynak akımı artı düğümden devreye giren akımın negatifidir.
        current = -solution[len(nodes) + k]
        sol.currents[element.id] = current if element.kind == "battery" else -current
        terminal = (element.positive_node or element.nodes[0], _negative(element)) if element.kind == "battery" else None
        sol.voltages[element.id] = potential[terminal[0]] - potential[terminal[1]] if terminal else Fraction(0)
    for element in circuit.elements:
        if element.kind == "voltmeter" or (element.kind == "switch" and not element.closed):
            a, b = element.nodes
            sol.voltages[element.id] = potential[a] - potential[b]
            sol.currents[element.id] = Fraction(0)
    if not _kirchhoff(circuit, sol, potential, resistors, sources, solution, len(nodes)):
        sol.reason = "kirchhoff_check_failed"
        return sol
    sol.status, sol.reason = "solved", "nodal_analysis"
    sol.steps.append("Düğüm gerilimleri değiştirilmiş düğüm analiziyle (kesin kesirler) bulundu; seri/paralel kararı "
                     "yalnız bağlantı grafiğinden çıktı.")
    return sol


def _negative(battery) -> str:
    plus = battery.positive_node or battery.nodes[0]
    return battery.nodes[1] if plus == battery.nodes[0] else battery.nodes[0]


def _kirchhoff(circuit, sol, potential, resistors, sources, solution, offset) -> bool:
    """Her düğümde akımların toplamı sıfır (yük korunumu) — çözümün bağımsız denetimi."""
    balance = {n: Fraction(0) for n in potential}
    for _, a, b, r in resistors:
        current = (potential[a] - potential[b]) / r
        balance[a] -= current
        balance[b] += current
    for k, (_, plus, minus, _) in enumerate(sources):
        current = solution[offset + k]  # artı düğümden kaynağa giren akım
        balance[plus] -= current
        balance[minus] += current
    return all(value == 0 for value in balance.values())


def equivalent_resistance(circuit: CircuitModel, values: dict[str, Value], a: str, b: str) -> Fraction | None:
    """Yalnız dirençlerden oluşan ağda a–b arasındaki eşdeğer direnç: 1 V test kaynağı ile (kaynaklar sıfırlanır)."""
    from ..education.science import CircuitElement

    elements = [e for e in circuit.elements if e.kind in {"resistor", "bulb", "wire", "ammeter"}
                or (e.kind == "switch" and e.closed)]
    if any(not e.connection_certain for e in circuit.elements):
        return None
    test = CircuitElement(id="test_source", kind="battery", nodes=[a, b], positive_node=a, value="test_emf",
                          provenance="derived")
    probe = circuit.model_copy(update={"elements": [*elements, test]})
    solved = solve(probe, {**values, "test_emf": Value("test_emf", None, Fraction(1), (2, 1, -3, -1, 0, 0, 0),
                                                         "voltage", "derived", "1 V")})
    if solved.status != "solved" or not solved.currents.get("test_source"):
        return None
    return 1 / solved.currents["test_source"]

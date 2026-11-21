r"""Sınırlı kimyasal formül ve tepkime ayrıştırıcısı, atom ve yük korunumu (TA-004).

Desteklenen güvenli alt küme:

- Element sembolleri büyük/küçük harfe duyarlıdır: ``CO`` (karbon + oksijen) ile ``Co`` (kobalt) farklıdır.
- Katsayı türün başındaki tam sayıdır (``2H₂``); alt simge elementten veya ayraçtan sonra gelir (``H₂O``,
  ``Ca(OH)₂``). ASCII rakamlar ve LaTeX ``_2`` / ``_{2}`` da alt simge sayılır. En çok iki düzey ayraç;
  açılış ve kapanış türü eşleşmelidir (``Ca(OH]2`` → ``mismatched_bracket``), boş grup reddedilir
  (``Ca()2`` → ``empty_group``).
- İyon yükü yalnızca açık üst simge (``Fe³⁺``, ``SO₄²⁻``) veya şapka (``Fe^{3+}``, ``Fe^3+``) ile yazılır.
  ``Fe2+`` gibi ASCII yazımda 2'nin alt simge mi yük mü olduğu belirsizdir; tahmin edilmez.
- Fiziksel hâl: ``(s)``, ``(l)``, ``(g)``, ``(aq)``. Oklar: ``→``, ``->``, ``⟶`` (tek yönlü) ve
  ``⇌``, ``<=>``, ``⇄`` (tersinir); LaTeX ``\rightarrow``, ``\to``, ``\longrightarrow``,
  ``\rightleftharpoons``. ``\mathrm{…}``, ``\text{…}`` sarmalayıcıları açılır. ``=`` tepkime oku değildir.
- Türler arasındaki düz ``+`` ayraçtır; boşluklu (``A + B``) veya boşluksuz (``2H₂+O₂``) olabilir. ``⁺``/``⁻``
  ve ``^{…}``/``^…`` içindeki işaret yüktür. ``Na++Cl-`` veya ``Na+ +Cl-`` gibi yalnız ASCII ile yazılmış,
  işaretin yük mü ayraç mı olduğu belirsiz biçimler tahmin edilmez: ``ambiguous_charge_notation``.

Gösterim kaynağı: Vision istemi bugün yalnız matematik sorusunu kabul eder (``valid_math_question``) ve
kimya türü üretmez. İfadeleri LaTeX biçiminde yazar; paket okumaları Unicode alt/üst simge kullanır.
Desteklenen biçimler bu iki kaynağa göre seçildi.

Dengeli bir denklem tepkimenin o koşulda gerçekleştiğini kanıtlamaz. Mekanizma ve kendiliğinden
olma ``unsupported`` kalır. Hidrat noktası, yapı formülleri ve izotop gösterimi desteklenmez (korunur).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction

from .units import parse_number

ELEMENTS = frozenset(
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr "
    "Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir "
    "Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl "
    "Mc Lv Ts Og".split()
)
MAX_SPECIES_CHARS = 48
MAX_EQUATION_CHARS = 240
MAX_SPECIES = 8
MAX_COUNT = 99
_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")
STATES = {"s", "l", "g", "aq"}
FORWARD_ARROWS = ("⟶", "→", "->")
REVERSIBLE_ARROWS = ("⇌", "⇄", "<=>", "<->")
_LATEX = (
    (re.compile(r"[\\](?:mathrm|text|ce)\{([^{}]*)\}"), r"\1"),
    (re.compile(r"[\\](?:rightleftharpoons|leftrightharpoons|rightleftarrows)(?![A-Za-z])"), "⇌"),
    (re.compile(r"[\\](?:longrightarrow|rightarrow|to)(?![A-Za-z])"), "→"),
    (re.compile(r"_\{(\d+)\}|_(\d+)"), lambda m: m.group(1) or m.group(2)),
    (re.compile(r"[\\][,;:! ]"), " "),
)


def normalize(text: str) -> str:
    """LaTeX kimya yazımını ayrıştırıcının Unicode/ASCII alt kümesine çevirir; tahmin yapmaz."""
    for pattern, replacement in _LATEX:
        text = pattern.sub(replacement, text)
    return text


class ChemistryError(ValueError):
    def __init__(self, status: str, reason: str):
        super().__init__(reason)
        self.status = status  # invalid | unsupported | ambiguous
        self.reason = reason


@dataclass(frozen=True)
class Species:
    original: str
    coefficient: int
    formula: str
    composition: tuple[tuple[str, int], ...]
    charge: int
    state: str | None

    @property
    def atoms(self) -> Counter:
        return Counter({element: count * self.coefficient for element, count in self.composition})


@dataclass(frozen=True)
class Reaction:
    original: str
    reactants: tuple[Species, ...]
    products: tuple[Species, ...]
    reversible: bool


def parse_species(text: str) -> Species:
    source = normalize(text).strip()
    if not source or len(source) > MAX_SPECIES_CHARS:
        raise ChemistryError("unsupported", "species_budget")
    rest = source
    coefficient = 1
    match = re.match(r"^(\d+)\s*", rest)
    if match:
        coefficient = int(match.group(1))
        if not 1 <= coefficient <= MAX_COUNT:
            raise ChemistryError("invalid", "coefficient_range")
        rest = rest[match.end():]
    state = None
    match = re.search(r"\((s|l|g|aq)\)\s*$", rest)
    if match:
        state = match.group(1)
        rest = rest[: match.start()].rstrip()
    rest, charge = _charge(rest)
    if re.search(r"[·•.]", rest):
        raise ChemistryError("unsupported", "hydrate_or_structure")
    if rest == "e" and charge == -1:
        # Elektron: atom taşımaz, yalnızca yük.
        return Species(source, coefficient, rest, (), charge, state)
    composition = _composition(rest.translate(_SUB))
    return Species(source, coefficient, rest, tuple(sorted(composition.items())), charge, state)


def _charge(text: str) -> tuple[str, int]:
    match = re.search(r"(?:\^\{?\s*(\d*)\s*([+-])\s*\}?|([⁰¹²³⁴⁵⁶⁷⁸⁹]*)([⁺⁻]))\s*$", text)
    if match:
        digits = match.group(1) if match.group(2) else match.group(3).translate(_SUP)
        sign = match.group(2) or match.group(4).translate(_SUP)
        magnitude = int(digits) if digits else 1
        if not 1 <= magnitude <= 8:
            raise ChemistryError("invalid", "charge_range")
        return text[: match.start()], magnitude if sign == "+" else -magnitude
    if re.search(r"\d[+-]$", text) or re.search(r"[A-Za-z)][+-]$", text):
        # "Fe2+": 2 alt simge mi yük mü? "Na+": tek yük de olabilir ama yazım kuralı belirsiz.
        if re.search(r"\d[+-]$", text):
            raise ChemistryError("ambiguous", "ambiguous_charge_notation")
        return text[:-1], 1 if text.endswith("+") else -1
    return text, 0


def _composition(text: str) -> Counter:
    counts, position = _group(text, 0, 0)
    if position != len(text):
        raise ChemistryError("invalid", "unexpected_character")
    if not counts:
        raise ChemistryError("invalid", "empty_formula")
    return counts


def _group(text: str, position: int, depth: int) -> tuple[Counter, int]:
    if depth > 2:
        raise ChemistryError("unsupported", "nesting_budget")
    counts: Counter = Counter()
    while position < len(text):
        char = text[position]
        if char in "([":
            inner, position = _group(text, position + 1, depth + 1)
            if position >= len(text):
                raise ChemistryError("invalid", "unbalanced_parenthesis")
            if text[position] != (")" if char == "(" else "]"):
                raise ChemistryError("invalid", "mismatched_bracket")
            if not inner:
                raise ChemistryError("invalid", "empty_group")
            position += 1
            multiplier, position = _count(text, position)
            for element, count in inner.items():
                counts[element] += count * multiplier
        elif char in ")]":
            if depth == 0:
                raise ChemistryError("invalid", "unbalanced_parenthesis")
            return counts, position
        elif char.isupper():
            symbol = char
            if position + 1 < len(text) and text[position + 1].islower():
                symbol += text[position + 1]
            if symbol not in ELEMENTS:
                raise ChemistryError("invalid", "unknown_element")
            position += len(symbol)
            count, position = _count(text, position)
            counts[symbol] += count
        else:
            raise ChemistryError("invalid", "unexpected_character")
        if sum(counts.values()) > 999:
            raise ChemistryError("unsupported", "atom_budget")
    return counts, position


def _count(text: str, position: int) -> tuple[int, int]:
    match = re.match(r"\d+", text[position:])
    if not match:
        return 1, position
    value = int(match.group(0))
    if not 1 <= value <= MAX_COUNT:
        raise ChemistryError("invalid", "subscript_range")
    return value, position + match.end()


def parse_reaction(text: str) -> Reaction:
    source = " ".join(normalize(text).split())
    if len(source) > MAX_EQUATION_CHARS:
        raise ChemistryError("unsupported", "equation_budget")
    arrows = [(arrow, True) for arrow in REVERSIBLE_ARROWS if arrow in source] + [
        (arrow, False) for arrow in FORWARD_ARROWS if arrow in source
    ]
    if not arrows:
        raise ChemistryError("invalid", "missing_arrow")
    arrow, reversible = arrows[0]
    if source.count(arrow) != 1 or (not reversible and "<" in source):
        raise ChemistryError("invalid", "multiple_arrows")
    left, right = source.split(arrow)
    reactants, products = _side(left), _side(right)
    return Reaction(source, reactants, products, reversible)


def _side(text: str) -> tuple[Species, ...]:
    parts = _split_side(text.strip())
    if not parts or len(parts) > MAX_SPECIES:
        raise ChemistryError("unsupported", "species_count")
    return tuple(parse_species(part) for part in parts)


def _split_side(text: str) -> list[str]:
    """Bir taraftaki türleri düz ``+`` ayraçlarından böler.

    ``^`` ile işaretli (``Fe^3+``, ``^{3+}``) veya Unicode (``⁺``) işaret yüktür. Düz ``+`` iki yanı da boşluklu
    ya da iki yanı da boşluksuzsa ayraçtır (``A + B``, ``2H₂+O₂``). Yalnız solu bitişik, sağı boşluk veya
    sonsa türün sonundaki ASCII yüktür (``Na+ + Cl-``). Ardışık düz ``++`` veya yalnız sağı bitişik ``+``
    (``Na+ +Cl-``) yük ile ayracı ayırt edilemez kıldığından tahmin edilmez.
    """
    cuts, depth, marked = [], 0, set()
    for i, char in enumerate(text):
        if char in "{}":
            depth += 1 if char == "{" else -1
            continue
        if char != "+" or depth:
            continue
        if re.search(r"\^\d*$", text[:i]):
            marked.add(i)
            continue
        before, after = text[i - 1] if i else "", text[i + 1] if i + 1 < len(text) else ""
        if after == "+" or (before == "+" and i - 1 not in marked):
            raise ChemistryError("ambiguous", "ambiguous_charge_notation")
        if not before or (not after and before.isspace()):
            raise ChemistryError("invalid", "empty_species")
        if before.isspace() == after.isspace() and after:
            cuts.append(i)
        elif before.isspace():
            raise ChemistryError("ambiguous", "ambiguous_charge_notation")
    parts = [text[a + 1:b].strip() for a, b in zip([-1, *cuts], [*cuts, len(text)])]
    if any(not part for part in parts):
        raise ChemistryError("invalid", "empty_species")
    return parts


@dataclass(frozen=True)
class BalanceResult:
    atoms_balanced: bool
    charge_balanced: bool
    differences: dict[str, int]
    charge_difference: int


def balance(reaction: Reaction) -> BalanceResult:
    left, right = Counter(), Counter()
    for item in reaction.reactants:
        left.update(item.atoms)
    for item in reaction.products:
        right.update(item.atoms)
    elements = sorted(set(left) | set(right))
    differences = {element: right[element] - left[element] for element in elements if right[element] != left[element]}
    charge = sum(item.coefficient * item.charge for item in reaction.products) - sum(
        item.coefficient * item.charge for item in reaction.reactants
    )
    return BalanceResult(not differences, charge == 0, differences, charge)


def check_reaction(text: str) -> tuple[str, str, BalanceResult | None]:
    """(outcome, reason, sonuç). Denge, tepkimenin gerçekleştiğinin kanıtı değildir."""
    try:
        reaction = parse_reaction(text)
    except ChemistryError as exc:
        return "unsupported", exc.reason, None
    result = balance(reaction)
    if not result.atoms_balanced:
        return "failed", "atoms_not_conserved", result
    if not result.charge_balanced:
        return "failed", "charge_not_conserved", result
    return "passed", "atoms_and_charge_conserved", result


def stoichiometric_amount(reaction_text: str, given_formula: str, given_mol: str, wanted_formula: str) -> Fraction:
    """Dengeli ve açıkça verilmiş tepkimede mol oranı: n(B) = n(A) · katsayı(B) / katsayı(A)."""
    reaction = parse_reaction(reaction_text)
    if not balance(reaction).atoms_balanced:
        raise ChemistryError("invalid", "unbalanced_reaction")
    species = {item.formula: item for item in reaction.reactants + reaction.products}
    if given_formula not in species or wanted_formula not in species:
        raise ChemistryError("invalid", "species_not_in_reaction")
    amount, _, _ = parse_number(given_mol)
    return amount * Fraction(species[wanted_formula].coefficient, species[given_formula].coefficient)


def same_species(left: str, right: str) -> bool:
    """Tür kimliği bileşim ve yüktür; hâl yalnız iki tarafta da yazılıysa karşılaştırılır.

    ``CO`` ≠ ``Co``; ``Fe²⁺`` ≠ ``Fe³⁺``; ``H₂O(l)`` ≠ ``H₂O(g)``.

    Hâl politikası: iki tarafta da yazılı ve farklıysa farklı türdür. Bir tarafta yazılmamışsa o hâl
    *bilinmiyor* sayılır ve karşılaştırmaya girmez (``H₂O`` = ``H₂O(l)``). Yazılmamış hâl farklılığın
    kanıtı değildir; katı karşılaştırma, kaynakta hâli yazılmamış doğru bir türü çelişki sayardı.

    Katsayı kimliğe girmez: katsayı miktardır (``2H₂O`` ile ``H₂O`` aynı türdür). Çağıranlar buna uygundur:
    stokiyometri ve sınırlayıcı tür hesabı türleri zaten katsayısız ``formula`` ile eşler; bilimsel matrisin
    ``species_distinct`` vakaları (``2H₂`` / ``H₂O``) bileşimle ayrılır.
    """
    a, b = parse_species(left), parse_species(right)
    states_differ = a.state is not None and b.state is not None and a.state != b.state
    return (a.composition, a.charge) == (b.composition, b.charge) and not states_differ


# --------------------------------------------------------------------------- TA-004 paket denetimleri


def balance_coefficients(text: str) -> tuple[int, ...]:
    """Verilen türler için en küçük pozitif tam sayı katsayıları (kesirli Gauss eleminasyonu).

    Çözüm uzayı tek boyutlu değilse (birden çok bağımsız denkleştirme veya hiç yok) tahmin edilmez.
    Denkleştirme, tepkimenin gerçekleştiğini kanıtlamaz. Yüklü türlerde yük de korunur.
    """
    reaction = parse_reaction(text)
    species = list(reaction.reactants) + list(reaction.products)
    if any(item.coefficient != 1 for item in species):
        raise ChemistryError("unsupported", "coefficients_already_given")
    elements = sorted({element for item in species for element, _ in item.composition})
    rows = [[Fraction(dict(item.composition).get(element, 0) * (1 if i < len(reaction.reactants) else -1))
             for i, item in enumerate(species)] for element in elements]
    rows.append([Fraction(item.charge * (1 if i < len(reaction.reactants) else -1)) for i, item in enumerate(species)])
    columns = len(species)
    pivots, row = [], 0
    for column in range(columns):
        pivot = next((r for r in range(row, len(rows)) if rows[r][column] != 0), None)
        if pivot is None:
            continue
        rows[row], rows[pivot] = rows[pivot], rows[row]
        rows[row] = [value / rows[row][column] for value in rows[row]]
        for r in range(len(rows)):
            if r != row and rows[r][column] != 0:
                factor = rows[r][column]
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[row])]
        pivots.append(column)
        row += 1
    free = [column for column in range(columns) if column not in pivots]
    if len(free) != 1:
        raise ChemistryError("unsupported", "not_uniquely_balanceable")
    solution = [Fraction(0)] * columns
    solution[free[0]] = Fraction(1)
    for index, column in enumerate(pivots):
        solution[column] = -rows[index][free[0]]
    if any(value <= 0 for value in solution):
        raise ChemistryError("unsupported", "no_positive_balance")
    denominator = 1
    for value in solution:
        denominator = denominator * value.denominator // math.gcd(denominator, value.denominator)
    integers = [int(value * denominator) for value in solution]
    divisor = 0
    for value in integers:
        divisor = math.gcd(divisor, value)
    result = tuple(value // divisor for value in integers)
    if max(result) > MAX_COUNT:
        raise ChemistryError("unsupported", "coefficient_range")
    return result


def element_amount(formula: str, mol: str, element: str) -> Fraction:
    """Tam ayrışma *verildiğinde* bir elementten oluşan iyonun mol sayısı: n · alt simge."""
    species = parse_species(formula)
    count = dict(species.composition).get(element)
    if count is None:
        raise ChemistryError("invalid", "element_not_in_formula")
    amount, _, _ = parse_number(mol)
    return amount * species.coefficient * count


def limiting_amount(reaction_text: str, amounts: dict[str, str], wanted: str) -> tuple[Fraction, str]:
    """Başlangıç miktarlarıyla tam tepkimede oluşan ürün ve sınırlayıcı tür."""
    reaction = parse_reaction(reaction_text)
    if not balance(reaction).atoms_balanced:
        raise ChemistryError("invalid", "unbalanced_reaction")
    reactants = {item.formula: item for item in reaction.reactants}
    products = {item.formula: item for item in reaction.products}
    if wanted not in products or not amounts or not set(amounts) <= set(reactants):
        raise ChemistryError("invalid", "species_not_in_reaction")
    if set(amounts) != set(reactants):
        raise ChemistryError("unsupported", "missing_reactant_amount")
    extents = {name: parse_number(value)[0] / reactants[name].coefficient for name, value in amounts.items()}
    limiting = min(extents, key=lambda name: extents[name])
    return extents[limiting] * products[wanted].coefficient, limiting


def electron_change(text: str) -> int:
    """Tek elementli bir değişimde verilen (pozitif) veya alınan (negatif) elektron sayısı.

    Yalnızca her iki tarafta da aynı tek element varsa ve elektron yazılmamışsa hesaplanır:
    ``Fe²⁺ → Fe³⁺`` için +1 (elektron kaybı, yükseltgenme), ``Cl₂ → 2Cl⁻`` için −2.
    """
    reaction = parse_reaction(text)
    species = list(reaction.reactants) + list(reaction.products)
    elements = {element for item in species for element, _ in item.composition}
    if len(elements) != 1 or any(not item.composition for item in species):
        raise ChemistryError("unsupported", "not_single_element_change")
    if not balance(reaction).atoms_balanced:
        raise ChemistryError("invalid", "atoms_not_conserved")
    before = sum(item.coefficient * item.charge for item in reaction.reactants)
    after = sum(item.coefficient * item.charge for item in reaction.products)
    return after - before

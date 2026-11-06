from fractions import Fraction

import pytest

from unitcalc import (BASE, DimensionError, ParseError, Quantity, Unit, UnitError, UnknownUnitError,
                      parse_quantity, parse_unit)


def dims(**kw):
    return tuple(kw.get(b, 0) for b in BASE)


# ---- units ----

def test_base_order():
    assert BASE == ("kg", "m", "s", "A", "K", "mol", "cd")


def test_atoms_prefixes_and_whole_symbol_priority():
    cases = {
        "km": (1000, dims(m=1)), "kg": (1, dims(kg=1)), "g": (Fraction(1, 1000), dims(kg=1)),
        "mL": (Fraction(1, 10 ** 6), dims(m=3)), "dam": (10, dims(m=1)), "hm": (100, dims(m=1)),
        "h": (3600, dims(s=1)), "min": (60, dims(s=1)), "cd": (1, dims(cd=1)), "ms": (Fraction(1, 1000), dims(s=1)),
        "Pa": (1, dims(kg=1, m=-1, s=-2)), "hPa": (100, dims(kg=1, m=-1, s=-2)), "kmol": (1000, dims(mol=1)),
        "uV": (Fraction(1, 10 ** 6), dims(kg=1, m=2, s=-3, A=-1)), "GHz": (10 ** 9, dims(s=-1)),
    }
    for text, (factor, d) in cases.items():
        u = parse_unit(text)
        assert isinstance(u, Unit)
        assert isinstance(u.factor, Fraction) and u.factor == factor, text
        assert u.dims == d, text
        assert u.symbol == text


def test_unknown_units():
    for text in ("hh", "kmin", "da", "foo", "Kg", "mmin"):
        with pytest.raises(UnknownUnitError) as ei:
            parse_unit(text)
        assert ei.value.symbol == text
        assert isinstance(ei.value, UnitError)
    with pytest.raises(UnknownUnitError) as ei:
        parse_unit("m*kfoo/s")
    assert ei.value.symbol == "kfoo"


def test_canonical_symbols():
    cases = {
        "kg*m/s^2": "kg*m/s^2", "kg*m*s^-2": "kg*m/s^2", "m/s/s": "m/s^2", "J/(kg*K)": "J/(kg*K)",
        "1/s": "1/s", "s^-1": "1/s", "(m/s)^2": "m^2/s^2", "(m/s)^-2": "s^2/m^2", "m*m*m": "m^3",
        "kg*m^-1*s^-2": "kg/(m*s^2)", "N*m": "N*m", "s^-1*m^-1": "1/(s*m)", " kg * m / s ^ 2 ": "kg*m/s^2",
        "km/h": "km/h", "W/m^2/K": "W/(m^2*K)",
    }
    for text, sym in cases.items():
        assert parse_unit(text).symbol == sym, text


def test_symbol_terms_cancel_immediately():
    assert parse_unit("s/s*m*s").symbol == "m*s"
    assert parse_unit("m*s/m").symbol == "s"
    for text in ("m/m", "m^0", "", "   ", "1"):
        u = parse_unit(text)
        assert u.symbol == "" and u.dims == dims() and u.factor == 1


def test_one_and_nested_parentheses():
    assert parse_unit("1/(1/s)").symbol == "s"
    assert parse_unit("((m))").symbol == "m"
    assert parse_unit("m/(s/kg)").symbol == "m*kg/s"
    u = parse_unit("1/h")
    assert u.factor == Fraction(1, 3600) and u.dims == dims(s=-1)


def test_parse_unit_errors_positions():
    for text, pos in (("kg*", 3), ("m^x", 2), ("m^2.5", 3), ("(m/s", 4), ("2*m", 0), ("m s", 2),
                      ("m^2^3", 3), ("m·s", 1), ("-1/s", 0), ("m^", 2)):
        with pytest.raises(ParseError) as ei:
            parse_unit(text)
        assert ei.value.pos == pos, text
        assert isinstance(ei.value, UnitError)


def test_unit_algebra_and_equality():
    n = parse_unit("N")
    assert n == parse_unit("kg*m/s^2") and hash(n) == hash(parse_unit("kg*m/s^2"))
    assert n != parse_unit("J")
    assert parse_unit("km") != parse_unit("m")
    m2 = parse_unit("m") ** 2
    assert m2 == parse_unit("m^2") and m2.symbol == "m^2"
    v = parse_unit("km") / parse_unit("h")
    assert v.symbol == "km/h" and v.factor == Fraction(5, 18)
    assert (parse_unit("N") * parse_unit("m")).symbol == "N*m"
    with pytest.raises(TypeError):
        parse_unit("m") ** 0.5


# ---- quantities ----

def test_quantity_construction():
    q = Quantity(3, "m/s")
    assert q.value == 3 and q.unit.symbol == "m/s"
    assert Quantity(2).unit.symbol == ""
    assert Quantity(2, parse_unit("kg")).unit.symbol == "kg"
    for bad in (True, "3", None):
        with pytest.raises(TypeError):
            Quantity(bad, "m")
    with pytest.raises(TypeError):
        Quantity(1, 5)
    with pytest.raises(UnknownUnitError):
        Quantity(1, "parsec")


def test_to_is_exact_single_rounding():
    v = Quantity(36, "km/h").to("m/s")
    assert v.value == 10.0 and isinstance(v.value, float) and v.unit.symbol == "m/s"
    assert Quantity(0.1, "km").to("m").value == 100.0
    assert Quantity(1, "kW*h").to("J").value == 3.6e6
    assert Quantity(1, "kW*h").to(parse_unit("MJ")).value == 3.6
    same = Quantity(3, "m").to("m")
    assert same.value == 3.0 and isinstance(same.value, float)
    with pytest.raises(DimensionError):
        Quantity(1, "m").to("s")


def test_to_base():
    assert str(Quantity(1, "N").to_base()) == "1 kg*m/s^2"
    assert Quantity(2, "V").to_base().unit.symbol == "kg*m^2/(s^3*A)"
    assert str(Quantity(72, "km/h").to_base()) == "20 m/s"
    q = Quantity(2, "L").to_base()
    assert q.unit.symbol == "m^3" and q.value == 0.002
    assert Quantity(5, "g*cd").to_base().unit.symbol == "kg*cd"


def test_simplify():
    assert str((Quantity(2, "kg") * Quantity(3, "m/s^2")).simplify()) == "6 N"
    assert Quantity(10, "J/s").simplify().unit.symbol == "W"
    assert Quantity(5, "1/s").simplify().unit.symbol == "Hz"
    assert Quantity(5, "A*min").simplify().value == 300.0
    assert Quantity(5, "A*min").simplify().unit.symbol == "C"
    assert Quantity(1, "N*m").simplify().unit.symbol == "J"
    assert Quantity(3, "km/h").simplify().unit.symbol == "m/s"
    d = Quantity(1, "km/m").simplify()
    assert d.unit.symbol == "" and d.value == 1000.0


def test_add_sub_use_left_unit():
    r = Quantity(1, "km") + Quantity(250, "m")
    assert r.unit.symbol == "km" and r.value == 1.25
    r = Quantity(250, "m") - Quantity(1, "km")
    assert r.unit.symbol == "m" and r.value == -750.0
    with pytest.raises(DimensionError):
        Quantity(1, "m") + Quantity(1, "s")
    with pytest.raises(DimensionError):
        Quantity(1, "m") + 1
    assert (Quantity(2) + 3).value == 5
    s = 10 - Quantity(4)
    assert s.value == 6 and s.unit.symbol == ""
    assert (1 + Quantity(1, "km/m")).value == 1001.0


def test_mul_div():
    p = Quantity(2, "N") * Quantity(3, "m")
    assert p.value == 6 and isinstance(p.value, int) and p.unit.symbol == "N*m"
    assert (Quantity(6, "m") / Quantity(4, "s")).value == 1.5
    assert (3 * Quantity(2, "kg")).unit.symbol == "kg"
    assert (Quantity(9, "m") / 3).value == 3.0
    inv = 2 / Quantity(4, "s")
    assert inv.value == 0.5 and inv.unit.symbol == "1/s"
    r = Quantity(6, "m") / Quantity(3, "m")
    assert r.unit.symbol == "" and r.value == 2.0
    k = Quantity(1, "km") / Quantity(1, "m")
    assert k.unit.symbol == "km/m" and k.value == 1.0
    with pytest.raises(ZeroDivisionError):
        Quantity(1, "m") / 0


def test_float_conversion():
    assert float(Quantity(1, "km") / Quantity(1, "m")) == 1000.0
    assert float(Quantity(3)) == 3.0
    with pytest.raises(DimensionError):
        float(Quantity(1, "m"))


def test_pow_neg_abs():
    q = Quantity(3, "m") ** 2
    assert q.value == 9 and q.unit.symbol == "m^2"
    assert (Quantity(2, "s") ** -1).unit.symbol == "1/s"
    z = Quantity(5, "m") ** 0
    assert z.value == 1 and z.unit.symbol == ""
    with pytest.raises(TypeError):
        Quantity(2, "m") ** 0.5
    assert (-Quantity(2, "m")).value == -2
    assert abs(Quantity(-2.5, "s")).value == 2.5


def test_comparisons():
    assert Quantity(100, "cm") == Quantity(1, "m")
    assert Quantity(0.1, "m") + Quantity(0.2, "m") == Quantity(0.3, "m")
    assert Quantity(1, "m") != Quantity(1, "s")
    assert Quantity(1) == 1 and Quantity(1, "m") != 1
    assert Quantity(999, "m") < Quantity(1, "km") <= Quantity(1000, "m")
    assert not Quantity(1, "km") < Quantity(1000, "m")
    assert Quantity(1, "h") > Quantity(59, "min") >= Quantity(3540, "s")
    with pytest.raises(DimensionError):
        Quantity(1, "m") < Quantity(1, "s")
    with pytest.raises(TypeError):
        hash(Quantity(1, "m"))


def test_str_and_format():
    assert str(Quantity(9.81, "m/s^2")) == "9.81 m/s^2"
    assert str(Quantity(5)) == "5"
    assert str(Quantity(1234567, "mol")) == "1.23457e+06 mol"
    assert str(Quantity(1e-7, "s")) == "1e-07 s"
    assert f"{Quantity(3, 'm/s'):.2f}" == "3.00 m/s"
    assert format(Quantity(2 / 3, "Pa"), ">8.3f") == "   0.667 Pa"
    assert f"{Quantity(0.5):.1%}" == "50.0%"


def test_parse_quantity():
    q = parse_quantity("9.81 m/s^2")
    assert q.value == 9.81 and q.unit.symbol == "m/s^2"
    q = parse_quantity("  5")
    assert q.value == 5 and isinstance(q.value, int) and q.unit.symbol == ""
    q = parse_quantity("-3.5e2 kJ")
    assert q.value == -350.0 and q.unit.symbol == "kJ"
    q = parse_quantity("1e3m")
    assert q.value == 1000.0 and isinstance(q.value, float) and q.unit.symbol == "m"
    assert parse_quantity(".5kg").value == 0.5
    assert isinstance(parse_quantity("5.").value, float)
    assert parse_quantity("+2 N*m").unit.symbol == "N*m"


def test_parse_quantity_errors():
    with pytest.raises(ParseError) as ei:
        parse_quantity("  abc")
    assert ei.value.pos == 2
    with pytest.raises(ParseError) as ei:
        parse_quantity("3 m/")
    assert ei.value.pos == 4
    with pytest.raises(ParseError) as ei:
        parse_quantity("12 kg m")
    assert ei.value.pos == 6
    with pytest.raises(UnknownUnitError):
        parse_quantity("2 e")

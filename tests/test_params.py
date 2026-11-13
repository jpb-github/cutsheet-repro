import pytest

from core.catalogue import get_part
from core.params import Param, ParamError, normalise_values


def test_an_unknown_part_is_a_key_error():
    with pytest.raises(KeyError):
        get_part("nothing")


def test_lengths_are_canonical_in_mm():
    params = (Param("depth", "Depth", "length", "100mm", min=10, max=1000),)
    assert normalise_values(params, {}) == {"depth": "100mm"}
    assert normalise_values(params, {"depth": "18 cm"}) == normalise_values(params, {"depth": "180"}) == {"depth": "180mm"}
    assert normalise_values(params, {"depth": "2in"}) == {"depth": "50.8mm"}
    for bad in ("abc", "5mm", "2000", True, None):
        with pytest.raises(ParamError):
            normalise_values(params, {"depth": bad})
    with pytest.raises(ParamError):
        normalise_values(params, {"other": 1})


def test_other_kinds():
    params = (Param("n", "N", "int", 2, min=1, max=9), Param("w", "W", "choice", "oak", choices=("oak", "pine")),
              Param("flag", "Flag", "bool", False))
    assert normalise_values(params, {"n": "3", "w": " Pine ", "flag": "yes"}) == {"n": 3, "w": "pine", "flag": True}
    for raw in ({"n": "0"}, {"n": "x"}, {"w": "elm"}, {"flag": "maybe"}):
        with pytest.raises(ParamError):
            normalise_values(params, raw)


def test_a_parameter_that_does_not_apply_is_replaced_by_its_default():
    params = (Param("many", "Many", "bool", False),
              Param("one", "One", "length", "100mm", min=10, max=1000, when="!many"),
              Param("a", "A", "length", "200mm", min=10, max=1000, when="many"))
    assert normalise_values(params, {}) == {"many": False, "one": "100mm", "a": "200mm"}
    assert normalise_values(params, {"one": "30cm", "a": "garbage"}) == {"many": False, "one": "300mm", "a": "200mm"}     # a is hidden: ignored
    assert normalise_values(params, {"many": True, "one": "garbage", "a": "40cm"}) == {"many": True, "one": "100mm", "a": "400mm"}
    with pytest.raises(ParamError) as e:
        normalise_values(params, {"many": True, "a": "garbage"})
    assert e.value.param == "a"

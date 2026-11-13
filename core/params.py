"""Parameter types and coercion for the part catalogue.

A Param describes one input of a part (name, kind, default, limits). normalise_values turns raw input (strings from a form or a
command line) into the canonical values used for the cache key and the generator command line: every parameter present
(defaults filled), equivalent inputs equal, JSON-serialisable. Standard library only.

Units: a length is typed in mm, cm or inches ("180", "180mm", "18 cm", "7 in") and is canonical in mm ("180mm"), so every request
that gives the same size is one cache key.
"""
import math
import re
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence


class ParamError(ValueError):
    """An invalid parameter value; .param names the parameter, .message says why."""

    def __init__(self, param: str, message: str):
        super().__init__("%s: %s" % (param, message))
        self.param = param
        self.message = message


@dataclass(frozen=True)
class Param:
    name: str
    label: str
    kind: Literal["length", "choice", "int", "float", "bool"]
    default: object
    min: float | None = None       # for kind "length": in mm
    max: float | None = None
    advanced: bool = False
    help: str = ""
    choices: tuple = ()            # for kind "choice": the allowed values (lower case)


def fmt_mm(mm: float) -> str:
    return ("%.3f" % mm).rstrip("0").rstrip(".")


_NUMBER = r"([0-9]+(?:\.[0-9]+)?)"
UNITS_MM = {"": 1.0, "mm": 1.0, "cm": 10.0, "in": 25.4}


def parse_length_mm(value: object, name: str = "length") -> float:
    """A length typed as "180", "180mm", "18 cm" or "7in" in mm (a bare number is mm). Raises ParamError for anything else."""
    err = ParamError(name, "%s must be a length such as 180mm, 18cm or 7in" % name)
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise err
    if isinstance(value, (int, float)):
        mm = float(value)
    else:
        m = re.fullmatch(r"\s*%s\s*(mm|cm|in)?\s*" % _NUMBER, value, re.I)
        if not m:
            raise err
        mm = float(m.group(1)) * UNITS_MM[(m.group(2) or "").lower()]
    if not math.isfinite(mm):
        raise err
    return mm


def length_mm(canonical: str) -> float:
    """The mm of a canonical length ("175mm" -> 175.0)."""
    return float(canonical.removesuffix("mm"))


def _limits(p: Param, v: float):
    if p.min is not None and v < p.min:
        raise ParamError(p.name, "must be >= %g" % p.min)
    if p.max is not None and v > p.max:
        raise ParamError(p.name, "must be <= %g" % p.max)


def _coerce(p: Param, value: object):
    if p.kind == "length":
        mm = round(parse_length_mm(value, p.name), 3)
        _limits(p, mm)
        return fmt_mm(mm) + "mm"
    if p.kind == "choice":
        text = value.strip().lower() if isinstance(value, str) else None
        if text not in p.choices:
            raise ParamError(p.name, "%s must be one of %s" % (p.name, ", ".join(p.choices)))
        return text
    if p.kind == "int":
        if isinstance(value, bool) or not isinstance(value, (int, str)) or (
                isinstance(value, str) and not re.fullmatch(r"[0-9]+", value.strip())):
            raise ParamError(p.name, "must be a whole number")
        v = int(value)
        _limits(p, v)
        return v
    if p.kind == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ParamError(p.name, "must be a number")
        try:
            v = float(value)
        except ValueError:
            raise ParamError(p.name, "must be a number")
        if not math.isfinite(v):
            raise ParamError(p.name, "must be a finite number")
        _limits(p, v)
        return v
    if p.kind == "bool":
        if isinstance(value, bool):
            return value
        t = value.strip().lower() if isinstance(value, str) else None
        if t in ("true", "1", "yes", "on"):
            return True
        if t in ("false", "0", "no", "off"):
            return False
        raise ParamError(p.name, "must be true or false")
    raise ValueError("unknown parameter kind %r" % p.kind)


def normalise_values(params: Sequence[Param], raw: Mapping[str, object]) -> dict[str, object]:
    """Canonical values of every parameter, in params order; unknown keys are an error."""
    known = {p.name for p in params}
    for key in raw:
        if key not in known:
            raise ParamError(key, "unknown parameter")
    return {p.name: _coerce(p, raw[p.name] if p.name in raw else p.default) for p in params}

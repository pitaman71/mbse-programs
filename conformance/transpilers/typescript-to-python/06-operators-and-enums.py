from enum import IntEnum, StrEnum


class Color(IntEnum):
    Red = 0
    Green = 4
    Blue = 5


class Mode(StrEnum):
    On = "on"
    Off = "off"


maybe: str | None = None
given: str | None = "x"
a = 0
if not a:
    a = 5
b: float | None = None
if b is None:
    b = 7
c = 3
if c:
    c = 4
pick = lambda x: "mid" if x > 2 and x < 10 else "edge"
print(maybe if maybe is not None else "fallback", given if given is not None else "unused", a, b, c, pick(5), pick(20), Color.Blue, Color.Green, Mode.Off)
print("null" if maybe is None else "set", "defined" if given is not None else "undefined", "falsy" if not maybe else "truthy")

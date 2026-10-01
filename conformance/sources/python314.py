#!/usr/bin/env python3
"""The Python 3.14 conformance source: every kind, and the details each keeps, once or more."""
# A comment of its own
from __future__ import annotations

import os.path as osp, sys  # a trailing comment
from . import sibling
from ..package.module import (first as one, second)
from collections.abc import *

type Pair[A, B = int] = tuple[A, B]
type Callback[**P, *Ts] = Callable[P, tuple[*Ts]]

NUMBERS = [0, 1_000, 0x_FF, 0o17, 0b1010, 1.5e-3, 2j, 3.0J, .5, 5.]
TEXTS = ('single', "double", '''triple''', """triple
double""", b'bytes', rb'\d+', R"raw", u'unicode', 'a' "b" f'c{NUMBERS[0]}')
SPECIAL = (None, True, False, ...)
EMPTY = (), [], {}, set()
ONE = (1,)


@decorator
@decorator.attribute(argument, keyword=1)
@(lambda f: f)
class Shape[T: (int, float), *Shapes](Base, metaclass=Meta, **options):
    """A docstring."""

    sides: int = 0
    name: str

    def __init__(self, sides: int, /, name: str = "shape", *args: *Shapes, scale: T = 1, **kwargs) -> None:
        self.sides, self.name = sides, name
        super().__init__(*args, **kwargs)

    @property
    def area(self) -> float:
        return self.sides ** 2 * -self.scale ** 0.5

    async def fetch(self, *, retries=3):
        async with session() as s, lock:
            async for item in s.stream():
                await item
        return [x async for x in self.stream() if await x]

    def generate(self):
        yield
        yield self
        yield from range(10)
        received = yield 1, 2
        return received


def operators(a, b, c):
    result = a + b - c * a / b // c % a @ b ** c
    result = a << b >> c & a ^ b | c
    result = ~a + +b - -c
    result = not a and b or c
    result = a < b <= c > a >= b == c != a is b is not c in a not in b
    result = a if b else c if a else b
    result = (a + b) * c, a - (b - c), (a ** b) ** c, (-a) ** b, (await_ := a)
    result += 1
    result -= 1
    result *= 2
    result @= m
    result /= 2
    result //= 2
    result %= 2
    result **= 2
    result <<= 1
    result >>= 1
    result &= 1
    result ^= 1
    result |= 1
    return result


def containers(items, key):
    pairs = {key: value, **items, 'k': 1}
    unique = {1, 2, *items}
    listed = [1, *items, 2]
    squares = [x * x for x in items if x if not x < 0]
    table = {k: v for k, v in items.items()}
    distinct = {x for row in items for x in row}
    lazy = (x for x in items)
    total = sum(x for x in items)
    head, *tail = items
    [first, second] = items
    (one,) = items
    del head, tail[0], items.attribute
    return items[0], items[1:2], items[::2], items[a:b, c], items[...], items[*key]


def strings(value, width):
    text = f'{value!r:>{width}} {value = } {value:=10} {{escaped}} {value!s} {value!a:{width}.{width}}'
    template = t'{value} and {value!r:>{width}}'
    nested = f"{f'{value}'}"
    raw = rf'\d{value}'
    multiline = f"""
    {value}
    """
    return text, template, nested, raw, multiline


def statements(path):
    global NUMBERS
    counter = 0

    def inner():
        nonlocal counter
        counter = counter + 1

    assert path, "a message"
    assert path
    pass
    if (size := len(path)) > 10:
        pass
    elif size > 5:
        pass
    else:
        pass
    while counter < 10:
        counter += 1
        if counter == 5:
            continue
        break
    else:
        pass
    for index, value in enumerate(path):
        pass
    else:
        pass
    with open(path) as handle, open(path) as (a, b):
        pass
    try:
        raise ValueError("bad") from None
    except (ValueError, TypeError) as error:
        raise
    except OSError:
        pass
    except:
        pass
    else:
        pass
    finally:
        pass
    try:
        pass
    except* ValueError as group:
        pass
    try:
        pass
    except ValueError, TypeError:
        pass
    try:
        pass
    finally:
        pass
    return lambda: 0, lambda x, /, y=1, *z, w, **v: x


def patterns(command):
    match command:
        case 0 | -1 | 1.5 | -2 + 3j | "text" | b"bytes" | None | True | False:
            pass
        case [first, *rest] | (first, *_) | []:
            pass
        case {"key": value, 1: _, **others}:
            pass
        case Point(x=0, y=yy) | Point(1, 2) | Point():
            pass
        case [Point(x=0) as origin, *_] if origin:
            pass
        case (1 | 2) as small:
            pass
        case constants.RED:
            pass
        case first, second:
            pass
        case name:
            pass
        case _:
            pass


# A comment before the end
print(Shape, operators, containers, strings, statements, patterns, sep="\n")  # the end

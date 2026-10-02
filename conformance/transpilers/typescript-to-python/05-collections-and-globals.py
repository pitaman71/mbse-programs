import functools
import json
import math
from types import SimpleNamespace
values = [5, 3, 8, 1]
doubled = [v * 2 for v in values]
big = [v for v in values if v > 2]
sum = functools.reduce(lambda a, b: a + b, values, 0)
values.append(9)
word = "  Hello World  "
point = SimpleNamespace(x=3, y=4, label="p")
print(" ".join(map(str, doubled)), len(big), sum, len(values), "has 8" if 8 in values else "no 8")
print(word.strip().upper(), word.strip().lower(), "abc"[1:], 1 if word.strip().startswith("Hello") else 0)
print(point.x + point.y, point.label, ",".join(map(str, list(vars(point)))), math.floor(7.8), max(3, 9, 2), 2 ** 10)
print(json.dumps([1, 2, 3], separators=(',', ':')), int("42") + 1, str(str(12)) + "!", abs(-4))

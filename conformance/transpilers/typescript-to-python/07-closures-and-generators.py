def counter():
    count = 0

    def _function1():
        nonlocal count
        count += 1
        return count

    return _function1


next = counter()
next()
next()


def range_(n: float):
    for i in range(0, n):
        yield i * i


squares: list[float] = []
for s in range_(4):
    squares.append(s)
seen = set([1, 2, 2, 3])
ages = dict()
ages["ada"] = 36
ages["bob"] = 7
names: list[str] = []
for a in ages:
    names.append(str(a))
print(next(), ",".join(map(str, squares)), len(seen), "has" if 2 in seen else "lacks", len(ages), ages.get("ada"), len(names))

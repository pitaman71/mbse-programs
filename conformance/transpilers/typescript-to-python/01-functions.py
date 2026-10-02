def fib(n: float) -> float:
    return n if n < 2 else fib(n - 1) + fib(n - 2)


def greet(name: str, greeting: str = "hello") -> str:
    return f"{greeting}, {name}!"


def total(*values) -> float:
    sum = 0
    for v in values:
        sum += v
    return sum


square = lambda x: x * x


def describe(n: float) -> str:
    if n % 2 == 0:
        return "even"
    return "odd"


print(fib(15), greet("Ada"), greet("Bob", "hi"), total(1, 2, 3, 4), square(7), describe(3), describe(10))

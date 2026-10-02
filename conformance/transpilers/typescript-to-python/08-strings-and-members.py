calls = 0


class Tally:
    items: list[float]

    def __init__(self):
        self.items = []

    def add(self, n: float) -> None:
        global calls
        calls += 1
        self.items.append(n)

    def sums(self) -> str:
        running = 0
        steps: list[str] = []
        for n in self.items:
            running += n
            steps.append("" + str(running))
        return "+".join(map(str, steps))


t = Tally()
t.add(1)
t.add(2)
t.add(3)
print("total " + str(1) + str(2), t.sums(), calls, f"{calls} calls", "x" + str(len(t.items)) + "y")

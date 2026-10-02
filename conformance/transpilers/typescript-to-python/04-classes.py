class Shape:
    count = 0

    def __init__(self, name: str):
        self.name = name
        Shape.count += 1

    def area(self) -> float:
        return 0

    def describe(self) -> str:
        return f"{self.name} of area {self.area()}"


class Rect(Shape):
    _width: float

    def __init__(self, width: float, height: float):
        super().__init__("rect")
        self.height = height
        self._width = width

    def area(self) -> float:
        return self._width * self.height

    @property
    def width(self) -> float:
        return self._width

    @width.setter
    def width(self, value: float):
        self._width = value


class Square(Rect):
    def __init__(self, side: float):
        super().__init__(side, side)


r = Rect(3, 4)
r.width = 5
s = Square(2)
print(r.describe(), s.describe(), r.width, Shape.count, "yes" if isinstance(s, Rect) else "no")

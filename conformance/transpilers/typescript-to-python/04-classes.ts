class Shape {
  static count = 0;
  constructor(public name: string) { Shape.count++; }
  area(): number { return 0; }
  describe(): string { return `${this.name} of area ${this.area()}`; }
}
class Rect extends Shape {
  #width: number;
  constructor(width: number, private height: number) { super("rect"); this.#width = width; }
  area(): number { return this.#width * this.height; }
  get width(): number { return this.#width; }
  set width(value: number) { this.#width = value; }
}
class Square extends Rect {
  constructor(side: number) { super(side, side); }
}
const r = new Rect(3, 4);
r.width = 5;
const s = new Square(2);
console.log(r.describe(), s.describe(), r.width, Shape.count, s instanceof Rect ? "yes" : "no");

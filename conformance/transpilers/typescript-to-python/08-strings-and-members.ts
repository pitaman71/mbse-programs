let calls = 0;
class Tally {
  items: number[] = [];
  add(n: number): void { calls++; this.items.push(n); }
  sums(): string {
    let running = 0;
    const steps: string[] = [];
    this.items.forEach(n => { running += n; steps.push("" + running); });
    return steps.join("+");
  }
}
const t = new Tally();
t.add(1); t.add(2); t.add(3);
console.log("total " + 1 + 2, t.sums(), calls, `${calls} calls`, "x" + t.items.length + "y");

function counter(): () => number {
  let count = 0;
  return () => { count += 1; return count; };
}
const next = counter();
next(); next();
function* range(n: number) { for (let i = 0; i < n; i++) yield i * i; }
const squares: number[] = [];
for (const s of range(4)) squares.push(s);
const seen = new Set([1, 2, 2, 3]);
const ages = new Map<string, number>();
ages.set("ada", 36);
ages.set("bob", 7);
const names: string[] = [];
ages.forEach(a => names.push(String(a)));
console.log(next(), squares.join(","), seen.size, seen.has(2) ? "has" : "lacks", ages.size, ages.get("ada"), names.length);

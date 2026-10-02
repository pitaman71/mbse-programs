function fib(n: number): number { return n < 2 ? n : fib(n - 1) + fib(n - 2); }
function greet(name: string, greeting: string = "hello"): string { return `${greeting}, ${name}!`; }
function total(...values: number[]): number { let sum = 0; for (const v of values) sum += v; return sum; }
const square = (x: number) => x * x;
const describe = (n: number): string => {
  if (n % 2 === 0) { return "even"; }
  return "odd";
};
console.log(fib(15), greet("Ada"), greet("Bob", "hi"), total(1, 2, 3, 4), square(7), describe(3), describe(10));

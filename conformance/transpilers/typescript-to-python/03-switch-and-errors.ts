function classify(n: number): string {
  switch (n) {
    case 0:
      return "zero";
    case 1:
    case 2:
      return "small";
    default:
      return "large";
  }
}
let log = "";
for (const n of [0, 1, 2, 7]) {
  switch (n % 3) {
    case 0: log += "a"; break;
    case 1: log += "b"; break;
    default: log += "c";
  }
}
class Oops extends Error {}
function risky(n: number): string {
  try {
    if (n > 1) throw new Oops("too big: " + n);
    return "fine";
  } catch (e) {
    return "caught " + e.message;
  } finally {
    log += "!";
  }
}
console.log(classify(0), classify(2), classify(9), log, risky(1), risky(5), log);

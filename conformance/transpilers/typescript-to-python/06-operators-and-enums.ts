enum Color { Red, Green = 4, Blue }
enum Mode { On = "on", Off = "off" }
let maybe: string | null = null;
let given: string | undefined = "x";
let a = 0;
a ||= 5;
let b: number | null = null;
b ??= 7;
let c = 3;
c &&= 4;
const pick = (x: number) => x > 2 && x < 10 ? "mid" : "edge";
console.log(maybe ?? "fallback", given ?? "unused", a, b, c, pick(5), pick(20), Color.Blue, Color.Green, Mode.Off);
console.log(maybe === null ? "null" : "set", given !== undefined ? "defined" : "undefined", !maybe ? "falsy" : "truthy");

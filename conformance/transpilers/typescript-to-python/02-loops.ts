let out: string[] = [];
for (let i = 0; i < 5; i++) out.push(String(i));
for (let i = 10; i > 0; i -= 3) out.push(String(i));
for (let i = 1; i <= 3; i++) { if (i === 2) continue; out.push("c" + i); }
let j = 0;
for (j = 0; j < 3; j = j + 1) out.push("j" + j);
let k = 0;
while (k < 3) { k++; }
do { k += 10; } while (k < 25);
for (const x of ["a", "b"]) out.push(x);
let n = 0;
while (true) { n++; if (n > 4) break; }
console.log(out.join(","), k, n);

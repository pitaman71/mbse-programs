out: list[str] = []
for i in range(0, 5):
    out.append(str(i))
for i in range(10, 0, -3):
    out.append(str(i))
for i in range(1, 4):
    if i == 2:
        continue
    out.append("c" + str(i))
j = 0
j = 0
while j < 3:
    out.append("j" + str(j))
    j = j + 1
k = 0
while k < 3:
    k += 1
while True:
    k += 10
    if not k < 25:
        break
for x in ["a", "b"]:
    out.append(x)
n = 0
while True:
    n += 1
    if n > 4:
        break
print(",".join(map(str, out)), k, n)

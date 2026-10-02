def classify(n: float) -> str:
    if n == 0:
        return "zero"
    elif n == 1 or n == 2:
        return "small"
    else:
        return "large"


log = ""
for n in [0, 1, 2, 7]:
    _subject1 = n % 3
    if _subject1 == 0:
        log += "a"
    elif _subject1 == 1:
        log += "b"
    else:
        log += "c"


class Oops(Exception):
    pass


def risky(n: float) -> str:
    global log
    try:
        if n > 1:
            raise Oops("too big: " + str(n))
        return "fine"
    except Exception as e:
        return "caught " + str(str(e))
    finally:
        log += "!"


print(classify(0), classify(2), classify(9), log, risky(1), risky(5), log)

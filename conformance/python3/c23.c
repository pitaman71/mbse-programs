/* The C conformance source: every statement, declaration and member kind of Programs.C, and the constructs C11 to
   C23 add, with the GNU extensions mbse-programs keeps. */
#include <stdio.h>
#include "local.h"
#include_next <limits.h>
#define VERSION 202311L
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define LOG(format, ...) printf(format, __VA_ARGS__)
#pragma once
_Pragma("GCC diagnostic push")
#embed "data.bin"
#
#if defined(DEBUG) && VERSION >= 202311L
#define TRACE 1
#elif !defined(NDEBUG) && __has_include(<assert.h>)
#define TRACE 2
#else
#define TRACE 0
#endif
#ifdef __GNUC__
int gnu;
#elifdef __clang__
int clang;
#elifndef _MSC_VER
int other;
#endif
// Declarations and their specifiers
typedef unsigned long long u64, *u64p;
static const volatile int counter = 0;
extern _Thread_local int tls;
thread_local int tls2;
_Alignas(16) char buffer[64];
alignas(int) char aligned;
_Atomic(int) atomic_count;
_Atomic int atomic_flag;
_Noreturn void fail(void);
[[noreturn]] void stop(void);
[[deprecated("old"), gnu::unused]] int legacy;
int marked [[maybe_unused]], *pointer;
constexpr int answer = 42;
constexpr bool yes = true;
void *nothing = nullptr;
_BitInt(24) bits = 1wb;
unsigned _BitInt(8) small = 255uwb;
typeof(answer) same;
typeof_unqual(const int) unqualified;
__typeof__(answer + 1) gnu_same;
_Complex double complex_value;
float _Imaginary imaginary_value;
_Decimal64 money = 1.5dd;
_Float128 wide;
size_t length;
long double precise = 1.0L;
int big = 1'000'000;
int hexadecimal = 0x1F, octal = 017, binary = 0b1010;
double floating = 0x1.8p3 + .5 + 1e-3;
char letter = 'a', escaped = '\n', wide_letter = L'w';
char *text = "a\tb" "c";
char8_t *utf8 = u8"text";
static_assert(sizeof(int) >= 2, "int is too small");
static_assert(1);
_Static_assert(1, "old");
[[maybe_unused]];
int (*handlers[4])(int);
void (*signal_handler(int, void(*)(int)))(int);
int vla(int n, int a[static n], int b[*], int c[const 3]);
void variadic(int count, ...);
int old(a, b)
    int a;
    char *b;
{
    return a;
}
int x __attribute__((aligned(16))) = 0;
int noinline(void) __attribute__((noinline, format(printf, 1, 2)));
int renamed asm("renamed_symbol") = 1;
int lookup(void) __asm__("lookup2");
__extension__ typedef long long ll;
__declspec(dllexport) int exported;
asm("nop");
// Structs, unions and enumerations
struct point {
    int x, y;
    unsigned flag : 1;
    int : 0;
    union {
        int i;
        float f;
    };
    struct {
        int depth;
    } nested;
    static_assert(sizeof(int) >= 2);
#ifdef EXTRA
    int extra;
#endif
    // a member's comment
    int last; /* trailing */
};
union value {
    int i;
    double d;
} initial = {.d = 1.0};
struct [[deprecated]] old_point;
enum color : unsigned char {
    RED,
    GREEN [[deprecated]] = 2,
#ifdef BLUE
    BLUE,
#endif
    // a comment
    WHITE,
};
enum {
    ANONYMOUS
} anonymous;
struct __attribute__((packed)) packed {
    _Pragma("pack(1)")
    char c;
};
// Statements
int statements(int n) {
    int total = 0, *p = &total;
    for (int i = 0; i < n; i++) {
        if (i % 2 == 0)
            continue;
        else if (i > 10)
            break;
        else {
            total += i;
        }
    }
    for (total = 0; total < n; ++total) {}
    _Pragma("GCC unroll 2")
    for (;;)
        break;
    while (n-- > 0)
        total--;
    do {
        total++;
    } while (total < 3);
    switch (n) {
        case 0:
        case 1:
            total = 1;
            break;
        case 2 ... 4: {
            total = 2;
            break;
        }
        case 5:
            [[fallthrough]];
        case 6:
            __attribute__((fallthrough));
        default:
            total = 0;
    }
    switch (n)
        case 7:
            total = 7;
    goto done;
again:
    total = MAX(total, 1);
    [[gnu::cold]] if (total) {}
    void *target = p;
    static void *labels[] = {&&again, &&done};
    goto *target;
done:
    ;
    int after = total;
    {
        int inner = after;
        (void)inner;
    }
    asm volatile("mov %1, %0" : "=r" (total) : [in] "r" (after) : "memory", "cc");
    asm goto("jmp %l0" : : : : again);
    static_assert(sizeof total == sizeof(int));
#if TRACE
    printf("%d\n", total);
#endif
    return total;
    ;
}
// Expressions
void expressions(int a, int b, int *p, struct point *s) {
    int values[] = {1, 2, [5] = 6, [7 ... 8] = 9};
    struct point origin = {.x = 0, .y = 0, .nested.depth = 1};
    struct point copy = (struct point){1, 2};
    int empty[3] = {};
    a = b + a * b - a / b % 3;
    a = (a << 2) >> 1 & b | a ^ ~b;
    a = !a && b || a != b && a == b;
    a = a < b ? a : b > a ? b : a;
    a = b ?: a;
    a += 1, b -= 2;
    a *= 3;
    a /= 4;
    a %= 5;
    a <<= 1;
    a >>= 1;
    a &= 1;
    a |= 2;
    a ^= 3;
    a = -a + +b;
    a = *p + p[1] + s->x + (*s).y;
    a++;
    --b;
    a = sizeof a + sizeof(int) + alignof(int) + _Alignof(double);
    a = (int)3.5 + (unsigned char)b;
    a = _Generic(a, int: 1, char*: 2, default: 3);
    a = offsetof(struct point, y);
    a = ({
        int t = a;
        t * 2;
    });
    a = __extension__ 1;
    a = (a);
    a = 'ab';
    printf("%d %s\n", a, "done");
    _Pragma("GCC diagnostic pop");
}

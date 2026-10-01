// The C++20 conformance source: every construct tree-sitter-cpp parses, once or more.
/* A block comment */
module;
#include <compare>
#include "local.h"
#define VERSION 3
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define LOG(format, ...) printf(format, __VA_ARGS__)
#if defined(VERSION) && VERSION > 2
#pragma once
#elif !defined(OTHER)
#error "unsupported"
#else
#line 100 "fallback.cpp"
#endif
#ifdef DEBUG
#undef DEBUG
#endif
#ifndef NDEBUG
#define NDEBUG
#endif
export module geometry.shapes:core;
import std;
export import :detail;
import <vector>;
import "legacy.h";

export namespace geo::inline v1 {
    struct Point {
        double x = 0, y = 0;
        auto operator<=>(const Point &) const = default;
        bool operator==(const Point &other) const noexcept;
    };
}

export {
    int exported(int);
}

namespace {
    int hidden;
}

inline namespace detail {
    namespace alias = geo::v1;
}

namespace outer::middle::inner {
    using namespace std;
    using std::vector;
    using enum Color;
}

extern "C" {
    int puts(const char *);
}
extern "C" int printf(const char *, ...);

typedef unsigned long size_type, *size_pointer;
typedef int (*callback)(int, void *);
using Function = void (*)(int) noexcept;
using Matrix = double[3][3];

static_assert(sizeof(int) >= 4, "int too small");
static_assert(true);

enum Color { Red, Green = 2, Blue, };
enum class Mode : unsigned char {
    Off,
    // the default
    On
};
enum struct Opaque : int;
union Value {
    int i;
    float f;
};

template <typename T>
concept Number = std::is_arithmetic_v<T>;

template <class T>
concept Container = requires(T t, const T &c) {
    t.begin();
    typename T::value_type;
    { c.size() } noexcept -> std::convertible_to<std::size_t>;
    requires Number<typename T::value_type>;
};

template <typename T, int N = 3, template <class> class Wrapper = std::vector, typename... Rest>
requires Number<T> && (N > 0) || Container<T>
class [[nodiscard]] Vector final : public Base<T>, private virtual Other, protected Mixin<N>... {
public:
    using value_type = T;
    static constexpr int size = N;
    Vector() : data{}, count(0) {}
    explicit Vector(T fill) noexcept;
    explicit(N > 1) Vector(T a, T b);
    Vector(const Vector &) = delete;
    Vector(Vector &&) noexcept = default;
    virtual ~Vector() = default;
    Vector &operator=(Vector &&other) & noexcept;
    T &operator[](int i) { return data[i]; }
    const T &operator[](int i) const { return data[i]; }
    operator bool() const { return count != 0; }
    explicit operator T *() const;
    friend Vector operator+(const Vector &a, const Vector &b);
    friend class Inspector;
    template <typename U> requires Number<U>
    U convert() const;
    virtual void draw() const = 0;
    void update() override final;
    int bits : 4;
    mutable int cache;
protected:
    T data[N];
private:
    int count;
};

template <>
struct Traits<int> {
    static const bool exact = true;
};

template class Vector<double>;
extern template class Vector<float>;

template <typename T>
T Vector<T>::convert() const { return T{}; }

template <typename... Ts>
auto sum(Ts... values) -> decltype((values + ...)) {
    return (... + values);
}

template <typename... Ts>
void forward_all(Ts &&...args) {
    consume(std::forward<Ts>(args)...);
    int count = sizeof...(Ts);
    auto product = (args * ... * 1);
}

int operator""_km(unsigned long long value);

[[deprecated("use g")]] int f(int a, int b = 2, ...) __attribute__((noinline));
__declspec(dllexport) alignas(16) char buffer[64];

int (*pick(int which))(int);
void (*handlers[4])(int);
int Point::*member_pointer = &Point::x;
char *const *volatile pointers;
int &&forwarded = 1;
auto [first, second] = std::pair{1, 2};
std::vector<std::vector<int>> nested;
std::array<int, (3 > 2) ? 3 : 2> chosen;

struct Node {
    Node *next;
    struct {
        int depth;
    } info;
};

std::coroutine_handle<> task() {
    co_await std::suspend_always{};
    co_yield 1;
    co_return;
}

int main(int argc, char *argv[]) {
    int a = 1, *b = &a, c[3] = {1, 2, 3}, d{4}, e(5);
    unsigned long long big = 0x1'000'000ULL + 0b1010 + 017 + 42u;
    double real = 1.5e-10 + .5 + 2. + 0x1.8p3 + 1.0f;
    char ch = 'a', newline = '\n', wide = L'w', utf = u8'u';
    const char *text = "plain" u8"utf8" R"raw(raw "text")raw" LR"(wide raw)";
    auto km = 12_km + "sv"_sv;
    bool flag = true && !false || nullptr == b;

    a = b == nullptr ? 0 : *b + -a * ~a / 2 % 3;
    a += 1, a -= 2, a *= 3, a /= 4, a %= 5;
    a <<= 1, a >>= 1, a &= 7, a |= 8, a ^= 9;
    a = (a << 2) >> 1 & 0xff | 0x100 ^ 0x10;
    auto order = a <=> c[0];
    flag = a < 1 || a > 2 || a <= 3 || a >= 4 || a != 5;
    ++a, --a, a++, a--;
    a = sizeof a + sizeof(int) + alignof(double);
    auto object = new Point{1, 2};
    auto array = new int[a][4]();
    auto placed = ::new (buffer) Point();
    delete object;
    ::delete[] array;
    auto cast = (int)real + static_cast<int>(real) + int(real) + int{3};
    auto dynamic = dynamic_cast<Base<int> *>(object);
    auto constant = const_cast<char *>(text);
    auto bits = reinterpret_cast<std::uintptr_t>(text);
    const std::type_info &info = typeid(Point);
    bool safe = noexcept(f(1, 2));
    auto designated = Point{.x = 1, .y = 2};
    std::vector<int> list = {1, 2, 3,};
    int empty[] = {};

    auto lambda = [=, &a, this, *this, value = 2, &ref = a, ...rest = argv]<typename T> requires Number<T>
        (T x) mutable constexpr noexcept -> T { return x + value; };
    auto simple = [] { return 0; };
    auto generic = [](auto &&x) { return x; };

    obj.member = obj->pointer + (obj.*field) + Point::origin.x;
    obj.template get<int>();
    p->~Point();
    matrix[1][2] = vector.at(0);

    if (a > 0) {
        a = 0;
    } else if (a < 0)
        a = 1;
    else {
    }
    if constexpr (sizeof(int) == 4) {}
    if (auto it = map.find(1); it != map.end()) use(it);
    if (int x = f(1, 2)) use(x);
    switch (int mode = get(); mode) {
        case 1:
            break;
        case 2:
        case 3: {
            a = 2;
            [[fallthrough]];
        }
        default:
            a = 3;
    }
    while (a--) continue;
    do {
        a++;
    } while (a < 10);
    for (int i = 0, j = 10; i < j; ++i, --j) {}
    for (;;) break;
    for (auto &[key, value] : map) {}
    for (std::vector<int> v = {1}; int x : v) use(x);
    try {
        throw std::runtime_error("failure");
    } catch (const std::exception &error) {
        throw;
    } catch (...) {
    }
    [[likely]] if (flag) goto done;
    __asm__ volatile("nop" : "=r"(a) : "r"(b) : "memory");
done:
    return argc > 1 ? EXIT_FAILURE : EXIT_SUCCESS;
}

module :private;

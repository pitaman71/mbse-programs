// The C++23 conformance source: what C++23 adds to C++20, and every kind of Programs.Cpp the C++20 source lacks.
module;
#
_Pragma("once")
export module shapes;
export import std;
export template <typename T>
T twice(T value) {
    return value + value;
}
using std::size_t, std::ptrdiff_t;
;
struct Packed {
    unsigned flags : 4 = 1;
    unsigned mode : 2 {3};
    int plain{2};
    int : 0;
#ifdef WIDE
    long wide;
#elifdef NARROW
    short narrow;
#endif
    static int operator()(int x) {
        return x;
    }
    void bind(this Packed &self, int value);
    auto cast(this auto &&self) -> int;
    [[nodiscard]] int value() const & noexcept;
    Packed() try : plain(1) {} catch (...) {}
};
[[using gnu: hot, cold]] void annotated();
enum Level {
    Low [[deprecated]] = 1,
    High
};
constexpr int choose(int x) {
    if consteval {
        return x;
    } else if !consteval {
        return -x;
    }
    [[assume(x > 0)]];
    auto copy = auto(x) + auto{x};
    auto size = 3uz + 4z;
    auto cell = grid[1, 2];
    for (int i = 0; auto v : values) {
        use(v);
    }
done:
}
extern template class Packed<int>;
template class Packed<long>;
int name = typeid(int).hash_code() + typeid(name).hash_code();
bool logic = a && !b || c;
int digraphs[2] = {1, 2};
template <class T>
Packed(T) -> Packed<T>;
module :private;

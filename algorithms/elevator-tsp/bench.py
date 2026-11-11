"""复杂度实测：验证 O(m log m) 时间 / O(m) 状态，并与完整状态版对比。"""

import random
import sys
import time

from author_solution import solve, Stats
from reference_full import solve_full


def gen(family, n, rng):
    if family == "random":
        span = 10**9
        floors = rng.sample(range(span), n)
        arrs = [rng.randint(0, span) for _ in range(n)]
        start = rng.randint(0, span)
    elif family == "f_incr":
        # A - P 严格递增 → |L| = m（左侧卡点全命中）
        floors = list(range(0, 3 * n, 3))
        arrs = [f + i for i, f in enumerate(floors)]
        start = 0
    elif family == "g_incr":
        # A + P 从右往左严格递增 → |R| = m
        floors = list(range(0, 3 * n, 3))
        arrs = [(n - i) * 4 for i in range(n)]
        start = floors[-1]
    elif family == "unimodal":
        # 单峰：左半 f 递增、右半 g 递增 → |L|+|R| ≈ m（作者所说的最坏情形）
        h = n // 2
        floors = list(range(n))
        arrs = []
        for i in range(n):
            if i < h:
                arrs.append(3 * i)
            else:
                arrs.append(3 * h + 2 * (n - i))
        start = 0
    elif family == "sawtooth":
        # 锯齿：交替出现左/右侧卡点，最大化交替转移
        floors = list(range(n))
        arrs = [(i // 2) * 4 + (2 if i % 2 else 0) for i in range(n)]
        start = 0
    elif family == "tiny":
        floors = list(range(n))
        arrs = [i % 3 for i in range(n)]
        start = 0
    else:
        raise ValueError(family)
    return [[a, f] for a, f in zip(arrs, floors)], start


FAMILIES = ["tiny", "random", "g_incr", "f_incr", "sawtooth", "unimodal"]
SIZES = [1000, 3000, 10000, 30000, 100000]


def main():
    rng = random.Random(7)
    print("=" * 78)
    print(f"{'family':<11}{'n':>8}{'|L|':>8}{'|R|':>8}{'states':>8}{'pops':>9}{'time(ms)':>10}{'L+R+2':>8}")
    print("=" * 78)
    table = {}
    for fam in FAMILIES:
        for n in SIZES:
            reqs, start = gen(fam, n, rng)
            st = Stats()
            t0 = time.perf_counter()
            ans = solve(0, start, reqs, st)
            dt = (time.perf_counter() - t0) * 1000
            table[(fam, n)] = (dt, st.distinct, st.n_left + st.n_right)
            print(
                f"{fam:<11}{n:>8}{st.n_left:>8}{st.n_right:>8}{st.distinct:>8}"
                f"{st.pops:>9}{dt:>10.1f}{st.n_left+st.n_right+2:>8}"
            )
    print("=" * 78)

    # 经验指数：用 log(time) ~ k*log(n) 拟合
    import math

    print("\n经验复杂度（对 time ~ n^k 做最小二乘拟合）：")
    for fam in FAMILIES:
        xs = [math.log(n) for n in SIZES]
        ys = [math.log(max(table[(fam, n)][0], 1e-9)) for n in SIZES]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        k = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
        print(f"  {fam:<11} k ≈ {k:.3f}   （n log n 的理论斜率随 n 缓慢上升，纯 n log n 在 10^3~10^5 区间约 1.2~1.3）")

    # 状态数上界检验
    #   去对端转移的状态数 distinct <= Σ((x+1)'-x'+2) <= 2|L| + |R| + 2（裂项相消的尖锐版）
    #   总状态数 = distinct + |L| + |R| = O(n)
    print("\n状态数上界检验：")
    print(f"{'family':<11}{'n':>8}{'distinct':>10}{'2|L|+|R|+2':>12}{'total':>9}{'total/(L+R)':>13}")
    viol = 0
    for fam in FAMILIES:
        for n in SIZES:
            dt, dist_states, lr = table[(fam, n)]
            # 重新取 L / R
            reqs, start = gen(fam, n, rng)
            st = Stats()
            solve(0, start, reqs, st)
            bound = 2 * st.n_left + st.n_right + 2
            total = st.distinct + st.n_left + st.n_right
            if st.distinct > bound:
                viol += 1
                print(f"  违反 2|L|+|R|+2: {fam} n={n} distinct={st.distinct} bound={bound}")
            if fam == "unimodal" or n == SIZES[0]:
                print(
                    f"{fam:<11}{n:>8}{st.distinct:>10}{bound:>12}{total:>9}"
                    f"{total/max(st.n_left+st.n_right,1):>13.2f}"
                )
    print(f"  违反 2|L|+|R|+2 的次数 = {viol}")

    # 与完整状态版对比：同答案 + 状态数差距
    print("\n与「诚实版 O(n²)」(无合并) 对比：")
    print(f"{'family':<11}{'n':>7}{'answer':>14}{'states(O(n))':>14}{'states(O(n²))':>15}{'ratio':>10}")
    for fam in ("unimodal", "sawtooth", "random", "f_incr"):
        for n in (200, 500, 1000):
            reqs, start = gen(fam, n, rng)
            st = Stats()
            a1 = solve(0, start, reqs, st)
            a2, ns = solve_full(0, start, reqs)
            assert a1 == a2, (fam, n, a1, a2)
            print(f"{fam:<11}{n:>7}{a1:>14}{st.distinct:>14}{ns:>15}{ns/max(st.distinct,1):>10.1f}x")


if __name__ == "__main__":
    main()

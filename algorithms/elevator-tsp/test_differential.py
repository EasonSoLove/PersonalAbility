"""差分测试：作者 O(m log m) vs 「诚实版」O(n²) 完整状态空间。

诚实版保留「卡点跳转」原语，只删掉两处合并，因此专门检验：
  * S(x) = max y   —— 「卡在同一卡点的状态只留 y 最大的」
  * y <= x'-1 的批量合并 —— 「先去对侧远端再折返」
这两步正是把 O(n²) 压到 O(n) 的关键，也是最容易出错的地方。
"""

import random
import sys
import time

from author_solution import solve, Stats
from reference_full import solve_full


FAMILIES = {}


def fam(name):
    def deco(fn):
        FAMILIES[name] = fn
        return fn

    return deco


@fam("random")
def _random(n, rng):
    span = rng.choice([n, 10 * n, 10**6])
    floors = rng.sample(range(span + 1), min(n, span + 1))
    arrs = [rng.randint(0, span) for _ in range(n)]
    return arrs, floors, rng.randint(-span, span)


@fam("f_incr")
def _f_incr(n, rng):
    """A-P 严格递增 → 每个点都是左侧卡点（|L| = n）"""
    floors = sorted(rng.sample(range(0, 5 * n), n))
    arrs = [f + i + rng.randint(0, 0) for i, f in enumerate(floors)]
    return arrs, floors, floors[0]


@fam("g_incr")
def _g_incr(n, rng):
    """A+P 从右往左严格递增 → 每个点都是右侧卡点（|R| = n）"""
    floors = sorted(rng.sample(range(0, 5 * n), n))
    arrs = [(n - i) * 3 for i in range(n)]
    return arrs, floors, floors[-1]


@fam("unimodal")
def _unimodal(n, rng):
    """单峰：左半 f 递增、右半 g 递增 → |L|+|R| ~= n（作者说的最坏情形）"""
    h = n // 2
    floors = list(range(n))
    arrs = []
    for i in range(n):
        if i < h:
            arrs.append(3 * i)
        else:
            arrs.append(3 * h + 2 * (n - i))
    return arrs, floors, 0


@fam("tiny_arrivals")
def _tiny(n, rng):
    floors = rng.sample(range(0, 10 * n), n)
    arrs = [rng.randint(0, 3) for _ in range(n)]
    return arrs, floors, rng.randint(0, 10 * n)


@fam("huge_arrivals")
def _huge(n, rng):
    floors = rng.sample(range(0, 10 * n), n)
    arrs = [rng.randint(10**8, 10**9) for _ in range(n)]
    return arrs, floors, rng.randint(0, 10 * n)


@fam("clustered")
def _clustered(n, rng):
    floors = sorted(rng.choice([0, 1, 2, 10**6, 10**6 + 1]) for _ in range(n))
    arrs = [rng.randint(0, 100) for _ in range(n)]
    return arrs, floors, rng.choice([0, 5, 10**6])


def main():
    rng = random.Random(2026)
    bad = 0
    total = 0
    t0 = time.time()
    print(f"{'family':<14}{'n':>6}{'|L|':>6}{'|R|':>6}{'O(nlogn)_states':>17}{'O(n^2)_states':>15}  result")
    for name, gen in FAMILIES.items():
        for n in (20, 60, 150, 400):
            for trial in range(2):
                arrs, floors, start = gen(n, rng)
                reqs = [[a, f] for a, f in zip(arrs, floors)]
                st = Stats()
                a = solve(0, start, reqs, st)
                b, ns = solve_full(0, start, reqs)
                total += 1
                mark = "OK" if a == b else "MISMATCH"
                if a != b:
                    bad += 1
                    print(f"  !! {name} n={n} start={start} author={a} full={b}")
                if trial == 0:
                    print(
                        f"{name:<14}{n:>6}{st.n_left:>6}{st.n_right:>6}"
                        f"{st.distinct:>17}{ns:>15}  {mark}"
                    )
    print(f"\n{total} 组差分对比，不一致 {bad} 组，耗时 {time.time()-t0:.1f}s")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()

"""攻击作者的核心论断：总状态数 = O(|L|+|R|)。

作者在「状态O(n)达成！」一节声称：
    卡住状态恰好 |L|+|R| 个；去对端转移的状态数 <= Σ((x+1)'-x'+2)（裂项相消）= O(n)。
本文件用随机搜索 + 爬山，专门找能让「不同状态数」超出 |L|+|R|+2 的输入。
"""

import random

from author_solution import solve, Stats


def count(reqs, start):
    st = Stats()
    solve(0, start, reqs, st)
    total = st.distinct + st.n_left + st.n_right
    return total, st.distinct, st.n_left, st.n_right


def main():
    rng = random.Random(42)
    violations = 0
    trials = 0

    for n in (6, 8, 10, 14, 20, 30, 60):
        best = (0, None)
        worst_ratio = (0.0, None)
        for _ in range(4000):
            span = rng.choice([n, 2 * n, 5 * n])
            floors = sorted(rng.sample(range(span + 1), min(n, span + 1)))
            amax = rng.choice([n, 4 * n, 50 * n])
            arrs = [rng.randint(0, amax) for _ in floors]
            start = rng.choice([floors[0], floors[-1], rng.randint(-span, 2 * span)])
            reqs = [[a, f] for a, f in zip(arrs, floors)]
            total, d, L, R = count(reqs, start)
            trials += 1

            # 尖锐上界：去对端状态 distinct <= 2|L| + |R| + 2
            if d > 2 * L + R + 2:
                violations += 1
                if violations <= 5:
                    print(
                        f"  违反 2|L|+|R|+2: n={n} distinct={d} L={L} R={R} "
                        f"start={start} reqs={reqs}"
                    )
            ratio = total / max(L + R, 1)
            if ratio > worst_ratio[0]:
                worst_ratio = (ratio, (d, L, R))
            if total > best[0]:
                best = (total, reqs, start, d, L, R)

        m = max(best[4] + best[5], 1)
        print(
            f"n={n:<3} 最大总状态={best[0]:<5} (L={best[4]:<3} R={best[5]:<3} 对端状态={best[3]:<4}) "
            f"总状态/(L+R)={best[0]/m:.2f}  最大比值={worst_ratio[0]:.2f}"
        )

    print(f"\n{trials} 个随机输入中，超出 2|L|+|R|+2 的次数 = {violations}")
    if violations:
        print(">>> 尖锐上界被推翻（但总状态仍可能只是常数因子更大）。")
    else:
        print(">>> 未找到反例：distinct <= 2|L|+|R|+2，总状态数 <= 3(|L|+|R|) = O(n)，支持作者论断。")


if __name__ == "__main__":
    main()

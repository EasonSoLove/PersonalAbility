"""正确性验证：作者 O(m log m) 解  vs  指数级精确暴力。

分层测试
  L0  穷举：请求数 1~3、楼层 0~4、到达时间 0~4、起点 0~4 的所有组合
  L1  随机：请求数 1~9，楼层/到达时间多种量级
  L2  对抗：重复楼层、起点在区间外、到达时间全 0、指数/线性/常数分布、
           卡点密集的「单峰」构造、极端并列
"""

import random
import sys
import time

from author_solution import solve
from reference import brute_force

FAILS = []


def check(requests, start, tag=""):
    exp = brute_force(0, start, requests)
    got = solve(0, start, requests)
    if exp != got:
        FAILS.append((tag, start, sorted(map(tuple, requests)), exp, got))
        return False
    return True


def l0_exhaustive():
    t0 = time.time()
    cnt = 0
    for k in (1, 2, 3):
        arr_rng = range(5) if k <= 2 else range(4)
        for _ in range(1):
            pass
        import itertools
        for reqs in itertools.product(
            [(a, f) for f in range(5) for a in arr_rng], repeat=k
        ):
            for start in range(5):
                check([list(r) for r in reqs], start, f"L0 k={k}")
                cnt += 1
    print(f"L0 exhaustive: {cnt} cases, fails={len(FAILS)}, {time.time()-t0:.1f}s")
    return cnt


def l1_random(iters=2000, seed=1):
    rng = random.Random(seed)
    t0 = time.time()
    for it in range(iters):
        k = rng.randint(1, 9)
        span = rng.choice([3, 5, 10, 30, 100])
        amax = rng.choice([1, 5, 20, 100, 1000])
        floors = [rng.randint(0, span) for _ in range(k)]
        arrs = [rng.randint(0, amax) for _ in range(k)]
        reqs = [[a, f] for a, f in zip(arrs, floors)]
        start = rng.randint(-span // 2, span + span // 2)
        if not check(reqs, start, "L1"):
            print("  FAIL", reqs, start)
    print(f"L1 random: {iters} cases, fails={len(FAILS)}, {time.time()-t0:.1f}s")


def l2_adversarial(seed=2):
    rng = random.Random(seed)
    t0 = time.time()
    cnt = 0
    cases = []

    # 重复楼层
    for _ in range(300):
        k = rng.randint(2, 8)
        fl = rng.choice([1, 2, 3])
        floors = [rng.randint(0, fl) for _ in range(k)]
        arrs = [rng.randint(0, 10) for _ in range(k)]
        cases.append(([[a, f] for a, f in zip(arrs, floors)], rng.randint(-2, fl + 2)))

    # 起点在区间外
    for _ in range(300):
        k = rng.randint(1, 8)
        floors = [rng.randint(0, 20) for _ in range(k)]
        arrs = [rng.randint(0, 40) for _ in range(k)]
        start = rng.choice([-50, -1, 0, 21, 200])
        cases.append(([[a, f] for a, f in zip(arrs, floors)], start))

    # 到达时间全 0 / 全相同
    for _ in range(200):
        k = rng.randint(1, 8)
        floors = [rng.randint(0, 15) for _ in range(k)]
        c = rng.randint(0, 30)
        cases.append(([[c, f] for f in floors], rng.randint(0, 15)))

    # 单峰卡点构造：A_i = P_i + i（左侧卡点全命中）/ A_i = -P_i + 2i
    for k in range(2, 9):
        fl = list(range(k))
        cases.append(([[f + i, f] for i, f in enumerate(fl)], 0))
        cases.append(([[max(0, 3 * i - f), f] for i, f in enumerate(fl)], 0))
        cases.append(([[i * i, f] for i, f in enumerate(fl)], 0))
        cases.append(([[max(0, -f + 2 * i), f] for i, f in enumerate(fl)], 0))
        cases.append(([[2 * i, f] for i, f in enumerate(fl)], 0))
        cases.append(([[max(0, 5 - i), f] for i, f in enumerate(fl)], k - 1))

    # 指数/稀疏
    for _ in range(200):
        k = rng.randint(2, 8)
        floors = sorted(rng.sample(range(0, 40), k))
        arrs = [rng.choice([0, 1, 2, 4, 8, 16, 32, 64, 128]) for _ in range(k)]
        cases.append(([[a, f] for a, f in zip(arrs, floors)], rng.randint(0, 40)))

    # 所有点都是「卡点」的最坏情形搜索：随机搜索使 |L|+|R| 最大
    for _ in range(200):
        k = rng.randint(3, 8)
        floors = sorted(rng.sample(range(0, 20), k))
        arrs = [rng.randint(0, 20) for _ in range(k)]
        cases.append(([[a, f] for a, f in zip(arrs, floors)], rng.randint(0, 20)))

    for reqs, start in cases:
        cnt += 1
        if not check(reqs, start, "L2"):
            print("  FAIL", sorted(map(tuple, reqs)), start)
    print(f"L2 adversarial: {cnt} cases, fails={len(FAILS)}, {time.time()-t0:.1f}s")


if __name__ == "__main__":
    l0_exhaustive()
    l1_random(2000)
    l2_adversarial()
    print("=" * 60)
    if FAILS:
        print(f"总计 {len(FAILS)} 个反例，前 10 个：")
        for f in FAILS[:10]:
            print(f"  tag={f[0]} start={f[1]} reqs={f[2]} 期望={f[3]} 实际={f[4]}")
        sys.exit(1)
    print("全部通过：作者解在以上所有用例上与精确暴力一致。")

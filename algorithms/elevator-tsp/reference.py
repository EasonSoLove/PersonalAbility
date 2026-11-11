"""精确参考解（指数级暴力），作为唯一真值来源。

模型
----
一条数轴，电梯速度 1，可任意掉头/等待。请求 i = (到达时间 A_i, 楼层 P_i)：
电梯在时刻 t 位于 P_i 且 t >= A_i 时该请求被服务。目标：全部服务完成的最早时刻。

关键归一化（在报告中论证）：
  1. 最优路径的「掉头点」一定落在某个请求楼层上（在非请求点掉头/等待纯属浪费，
     等价的等待可以搬到目标请求楼层上），因此可以只枚举「依次停在哪些请求楼层」。
  2. 单调一段路上的中间请求楼层，若经过时已到达则该请求即时被服务（顺带服务）。
  3. 只在「停下来的那个请求楼层」等待（等它到达）——任何中途等待都可以等价改写成
     先停靠该楼层再出发，总时长不变。

于是状态 = (已服务请求集合 mask, 当前所在楼层下标 p)，边权非负，用 Dijkstra 求最短路。
这是对所有合法调度的穷举，因此是精确解。
"""

from heapq import heappush, heappop

INF = float("inf")


def brute_force(n, start, requests):
    positions = sorted({f for _, f in requests} | {start})
    idx = {pos: i for i, pos in enumerate(positions)}
    m = len(positions)
    reqs = [(a, idx[f]) for a, f in requests]
    k = len(reqs)
    full = (1 << k) - 1

    by_pos = [[] for _ in range(m)]
    for i, (a, p) in enumerate(reqs):
        by_pos[p].append((a, i))

    # 预计算 (p, q) 段上按「经过时刻 = t + offset」检查的中间楼层
    segments = [[None] * m for _ in range(m)]
    for p in range(m):
        for q in range(m):
            if p == q:
                continue
            lo, hi = (p, q) if p < q else (q, p)
            segments[p][q] = [
                (abs(positions[r] - positions[p]), by_pos[r]) for r in range(lo + 1, hi + 1)
            ]

    dist = {(0, idx[start]): 0}
    pq = [(0, 0, idx[start])]
    best = INF
    while pq:
        t, mask, p = heappop(pq)
        if dist.get((mask, p), INF) < t:
            continue
        if mask == full:
            if t < best:
                best = t
            continue
        if t >= best:
            continue

        # 动作 1：停留在 p，等 p 上的未服务请求到达并服务
        for a, i in by_pos[p]:
            if not (mask >> i) & 1:
                nt = t if a <= t else a
                nm = mask | (1 << i)
                if nt < dist.get((nm, p), INF):
                    dist[(nm, p)] = nt
                    heappush(pq, (nt, nm, p))

        # 动作 2：移动到 q，路上经过且已到达的请求顺带服务
        for q in range(m):
            if q == p:
                continue
            arr = t + abs(positions[q] - positions[p])
            nm = mask
            for off, lst in segments[p][q]:
                reach = t + off
                for a, i in lst:
                    if not (mask >> i) & 1 and a <= reach:
                        nm |= 1 << i
            if arr < dist.get((nm, q), INF):
                dist[(nm, q)] = arr
                heappush(pq, (arr, nm, q))
    return best


if __name__ == "__main__":
    # 文章里的大巴车例子：start=0，全部即刻到达
    print(brute_force(0, 0, [[0, 0], [0, 10]]))          # 10
    print(brute_force(0, 5, [[0, 0], [0, 10]]))          # 15
    print(brute_force(0, 0, [[100, 0]]))                 # 100
    print(brute_force(0, 0, [[5, 0], [0, 10]]))          # 15  (先去10再回来正好5到)

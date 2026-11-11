"""「诚实版」O(n²) 完整状态空间解 —— 差分测试的靶子。

思路：把作者的 O(n log n) 代码复制过来，只删掉两处「合并/支配」压缩，其余一切保留：

  (1) 删掉 S(x) 合并：作者对「卡在同一个卡点 x」的所有状态只保留 y 最大的一个
      （因为等完的时间恒为 A_x，y 越大越优）。这里改为**每个 (x, y) 都单独入队**；
  (2) 删掉「先到对侧远端再折返到 oppo-1」的合并：作者把 y <= x'-1 的一大批 y
      压缩成同一个目标状态 (x'-1, x+1)。这里改为**逐个 y 直接走到对侧远端**
      （合法动作，只是状态多）。

剩下的「卡点跳转」这一核心原语保持不变，因此本文件：
  * 正确性只依赖「卡点」引理（该引理已由独立指数暴力在 n<=9 上验证）；
  * 状态数 O(L*R) = O(n²)，用来攻击作者最可疑的 O(n) 状态数论证。

如果两者在大量中等规模随机/对抗输入上答案一致，说明状态压缩（合并）是安全的。
"""

from heapq import heapify, heappop, heappush
from math import inf
from bisect import bisect


def solve_full(n, start, requests, max_states=None):
    requests_mapping = {}
    for a, f in requests:
        requests_mapping[f] = max(requests_mapping.get(f, 0), a)
    requests_sorted = sorted(requests_mapping.items())
    N = len(requests_sorted)
    if N == 1:
        return max(requests_sorted[0][1], abs(requests_sorted[0][0] - start)), 0

    left_seq = [requests_sorted[0]]
    for i in range(1, N):
        if requests_sorted[i][1] - requests_sorted[i][0] > left_seq[-1][1] - left_seq[-1][0]:
            left_seq.append(requests_sorted[i])
    left_bis = [r[1] - r[0] for r in left_seq]

    right_seq = [requests_sorted[-1]]
    for i in range(N - 2, -1, -1):
        if requests_sorted[i][1] + requests_sorted[i][0] > right_seq[-1][1] + right_seq[-1][0]:
            right_seq.append(requests_sorted[i])
    right_bis = [r[1] + r[0] for r in right_seq]

    L, R = len(left_seq), len(right_seq)
    left_opposite = [0] * L
    j = 0
    for i in range(L):
        while j < R and right_seq[j][1] <= left_seq[i][1]:
            j += 1
        left_opposite[i] = j
    right_opposite = [0] * R
    j = 0
    for i in range(R):
        while j < L and left_seq[j][1] <= right_seq[i][1]:
            j += 1
        right_opposite[i] = j

    ans = inf
    dist = {}
    pq = []

    def push(c, x, y, is_left):
        key = (x, y, is_left)
        if dist.get(key, inf) > c:
            dist[key] = c
            heappush(pq, (c, x, y, is_left))

    push(max(left_seq[0][1], abs(left_seq[0][0] - start)), 0, 0, True)
    push(max(right_seq[0][1], abs(right_seq[0][0] - start)), 0, 0, False)

    while pq:
        c, x, y, is_left = heappop(pq)
        if dist[(x, y, is_left)] < c:
            continue
        if c >= ans:
            break
        if max_states is not None and len(dist) > max_states:
            raise RuntimeError("state explosion")

        # ---- 原语：一路走到下一个会卡住的位置 ----
        if is_left:
            x2 = bisect(left_bis, c - left_seq[x][0], x)
            if x2 == L:
                ans = min(ans, c + right_seq[y][0] - left_seq[x][0])
                continue
            c += left_seq[x2 - 1][0] - left_seq[x][0]
            x = x2 - 1
        else:
            x2 = bisect(right_bis, c + right_seq[x][0], x)
            if x2 == R:
                ans = min(ans, c + right_seq[x][0] - left_seq[y][0])
                continue
            c += right_seq[x][0] - right_seq[x2 - 1][0]
            x = x2 - 1

        # 现在位于本侧 P_x，时刻 c；下一个本侧卡点是 x+1（必然卡住：先等到它到达）
        if is_left:
            push(left_seq[x + 1][1], x + 1, y, True)
        else:
            push(right_seq[x + 1][1], x + 1, y, False)

        # ---- 选项：奔向对侧最远未完成点 ----
        if is_left:
            t_arr = c + right_seq[y][0] - left_seq[x][0]
            push(max(t_arr, right_seq[y][1]), y, x + 1, False)
        else:
            t_arr = c + right_seq[x][0] - left_seq[y][0]
            push(max(t_arr, left_seq[y][1]), y, x + 1, True)

    return ans, len(dist)


if __name__ == "__main__":
    print(solve_full(0, 0, [[0, 0], [0, 10]]))

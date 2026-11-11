"""作者原文（知乎 @灵剑）给出的 O(m log m) 解法，逐字复刻。

来源：LeetCode 会员题 elevator-requests-iii / 带释放时间的一维 TSP。
原始代码见知乎文章「震撼首发：一个1990年提出的O(n^2)算法首次被改进到了O(n log n)」。

除两处改动外与原文完全一致：
  1. 增加了 `Stats` 统计量（堆弹出次数、入堆次数、二分次数），用于验证复杂度；
  2. 把内部的 `bisect` 包了一层以计数。
"""

from heapq import heapify, heappop, heappush, heapreplace
from math import inf
from bisect import bisect


class Stats:
    __slots__ = ("pops", "pushes", "bisects", "enqueues", "distinct", "n_left", "n_right")

    def __init__(self):
        self.pops = 0        # 出堆次数（含 lazy 删除）
        self.pushes = 0      # 真正入堆次数
        self.bisects = 0     # 二分查找次数
        self.enqueues = 0    # enqueue 调用次数（含被 dist 剪掉的）
        self.distinct = 0    # 实际访问到的不同状态数
        self.n_left = 0      # 左侧卡点数 |L|
        self.n_right = 0     # 右侧卡点数 |R|


def solve(n, start, requests, stats: Stats | None = None):
    stats = stats if stats is not None else Stats()

    def _bisect(a, key, lo):
        stats.bisects += 1
        return bisect(a, key, lo)

    requests_mapping = {}
    for a, f in requests:
        requests_mapping[f] = max(requests_mapping.get(f, 0), a)
    requests_sorted = sorted(requests_mapping.items())
    N = len(requests_sorted)
    if N == 1:
        stats.n_left = stats.n_right = stats.distinct = 1
        return max(requests_sorted[0][1], abs(requests_sorted[0][0] - start))

    # ---------- 找「卡点」：左侧卡点 / 右侧卡点 ----------
    left_seq = [requests_sorted[0]]
    for i in range(1, N):
        if requests_sorted[i][1] - requests_sorted[i][0] > left_seq[-1][1] - left_seq[-1][0]:
            left_seq.append(requests_sorted[i])
    left_seq_bis = [r[1] - r[0] for r in left_seq]          # A - P，严格递增

    right_seq = [requests_sorted[-1]]
    for i in range(N - 2, -1, -1):
        if requests_sorted[i][1] + requests_sorted[i][0] > right_seq[-1][1] + right_seq[-1][0]:
            right_seq.append(requests_sorted[i])
    right_seq_bis = [r[1] + r[0] for r in right_seq]        # A + P，严格递增

    # 对侧卡点：min j s.t. A_j > A_x
    left_opposite = [0] * len(left_seq)
    j = 0
    for i, (_, arrival) in enumerate(left_seq):
        while j < len(right_seq) and right_seq[j][1] <= arrival:
            j += 1
        left_opposite[i] = j
    right_opposite = [0] * len(right_seq)
    j = 0
    for i, (_, arrival) in enumerate(right_seq):
        while j < len(left_seq) and left_seq[j][1] <= arrival:
            j += 1
        right_opposite[i] = j

    stats.n_left = len(left_seq)
    stats.n_right = len(right_seq)
    ans = inf
    dist = {}
    stuck_left = [-1] * len(left_seq)
    stuck_right = [-1] * len(right_seq)

    # (time, type, x, y, is_left)；type 0 普通状态，type 1 卡住状态 S(x)
    queue = [
        (max(left_seq[0][1], abs(left_seq[0][0] - start)), 0, 0, 0, True),
        (max(right_seq[0][1], abs(right_seq[0][0] - start)), 0, 0, 0, False),
    ]
    for c, _, x, y, is_left in queue:
        dist[(x, y, is_left)] = c
    for i, (_, arrival) in enumerate(left_seq):
        queue.append((arrival, 1, i, 0, True))
    for i, (_, arrival) in enumerate(right_seq):
        queue.append((arrival, 1, i, 0, False))
    heapify(queue)

    _lazy_pop = False

    def nonempty():
        return len(queue) - _lazy_pop > 0

    def lazy_pop():
        nonlocal _lazy_pop
        stats.pops += 1
        if _lazy_pop:
            heappop(queue)
        else:
            _lazy_pop = True
        return queue[0]

    def enqueue(c, x, y, is_left):
        nonlocal _lazy_pop
        stats.enqueues += 1
        if (x, y, is_left) not in dist or dist[(x, y, is_left)] > c:
            stats.pushes += 1
            dist[(x, y, is_left)] = c
            if _lazy_pop:
                heapreplace(queue, (c, 0, x, y, is_left))
                _lazy_pop = False
            else:
                heappush(queue, (c, 0, x, y, is_left))

    while nonempty():
        c, type_, x, y, is_left = lazy_pop()
        if c >= ans:
            break
        if type_ == 0:
            if dist[(x, y, is_left)] < c:
                continue
            # 一路走到下一个卡住的位置
            if is_left:
                x2 = _bisect(left_seq_bis, c - left_seq[x][0], x)
                if x2 == len(left_seq_bis):
                    ans = min(ans, c + right_seq[y][0] - left_seq[x][0])
                    continue
                c += left_seq[x2 - 1][0] - left_seq[x][0]
                x = x2 - 1
            else:
                x2 = _bisect(right_seq_bis, c + right_seq[x][0], x)
                if x2 == len(right_seq_bis):
                    ans = min(ans, c + right_seq[x][0] - left_seq[y][0])
                    continue
                c += right_seq[x][0] - right_seq[x2 - 1][0]
                x = x2 - 1
        else:
            if is_left:
                y = stuck_left[x]
            else:
                y = stuck_right[x]
            if y < 0:
                continue
            if is_left:
                if x == len(left_seq) - 1:
                    ans = min(ans, c + right_seq[y][0] - left_seq[x][0])
                    continue
            else:
                if x == len(right_seq) - 1:
                    ans = min(ans, c + right_seq[x][0] - left_seq[y][0])
                    continue

        if is_left:
            stuck_left[x + 1] = max(stuck_left[x + 1], y)
        else:
            stuck_right[x + 1] = max(stuck_right[x + 1], y)

        oppo = left_opposite[x] if is_left else right_opposite[x]
        if y <= oppo - 1:
            # 先去对面最远处、再折返到 oppo-1，中途不会卡住
            if is_left:
                new_dist = right_seq[y][0] * 2 - left_seq[x][0] - right_seq[oppo - 1][0]
            else:
                new_dist = right_seq[x][0] + left_seq[oppo - 1][0] - left_seq[y][0] * 2
            enqueue(c + new_dist, oppo - 1, x + 1, not is_left)
        else:
            if is_left:
                new_dist = right_seq[y][0] - left_seq[x][0]
                if c + new_dist <= right_seq[y][1]:
                    stuck_right[y] = max(stuck_right[y], x + 1)
                else:
                    enqueue(c + new_dist, y, x + 1, not is_left)
            else:
                new_dist = right_seq[x][0] - left_seq[y][0]
                if c + new_dist <= left_seq[y][1]:
                    stuck_left[y] = max(stuck_left[y], x + 1)
                else:
                    enqueue(c + new_dist, y, x + 1, not is_left)
    stats.distinct = len(dist)
    return ans


class Solution:
    def elevatorRequests(self, n: int, start: int, requests: list[list[int]]) -> int:
        return solve(n, start, requests)

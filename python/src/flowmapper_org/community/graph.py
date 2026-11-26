"""Graph algorithms of FlowMapper's Regionalization: Leiden, Louvain, modularity.

Line-by-line ports of ``CommunityDetection.js``. Iteration order (JavaScript
``Map`` insertion order = Python ``dict`` order), floating-point accumulation
order, tie-breaking and the sequence of random numbers drawn from FlowMapper's
``mulberry32`` generator are all reproduced, so a given seed gives the same
partition, bit for bit, as FlowMapper.org.

The graph is undirected and weighted; modularity with resolution ``gamma`` is

    Q = sum_c [ in_c / 2m  -  gamma * (K_c / 2m)^2 ]

where ``in_c`` is twice the weight inside community ``c``, ``K_c`` the sum of
weighted degrees in ``c`` and ``2m`` the sum of all weighted degrees.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence, Tuple

from ._jsmath import js_exp, to_int32, imul

__all__ = [
    "Graph", "mulberry32", "shuffled", "make_graph", "leiden_local_moving", "louvain_local_moving",
    "leiden_refine", "relabel", "aggregate_graph", "leiden", "louvain", "modularity",
]


# ---------------------------------------------------------------------------- PRNG


def mulberry32(a: float) -> Callable[[], float]:
    """FlowMapper's seeded random number generator (uniform in [0, 1)).

    Reproduces the 32-bit integer arithmetic of the JavaScript exactly, so the
    sequence equals the web application's for the same seed.

    JS: CommunityDetection.js:mulberry32
    """
    state = [a]

    def rng() -> float:
        s = to_int32(state[0])
        s = to_int32(s + 0x6D2B79F5)
        state[0] = s
        t = imul(s ^ ((s & 0xFFFFFFFF) >> 15), 1 | s)
        t = to_int32(t + imul(t ^ ((t & 0xFFFFFFFF) >> 7), 61 | t)) ^ t
        return ((t ^ ((t & 0xFFFFFFFF) >> 14)) & 0xFFFFFFFF) / 4294967296

    return rng


def shuffled(n: int, rng: Callable[[], float]) -> List[int]:
    """A random permutation of ``0..n-1`` (Fisher-Yates from the end).

    JS: CommunityDetection.js:shuffled
    """
    a = list(range(n))
    for j in range(n - 1, 0, -1):
        r = math.floor(rng() * (j + 1))
        a[j], a[r] = a[r], a[j]
    return a


# ---------------------------------------------------------------------------- graph


@dataclass
class Graph:
    """Undirected weighted graph as FlowMapper stores it.

    Attributes
    ----------
    n : int
        Number of nodes.
    nbr : list of list of (int, float)
        Neighbours of each node with the edge weight, in insertion order.
    k : list of float
        Weighted degree of each node.
    m2 : float
        Sum of the weighted degrees (twice the total edge weight).
    """

    n: int
    nbr: List[List[Tuple[int, float]]]
    k: List[float]
    m2: float


def make_graph(n: int, edges: Iterable[Sequence]) -> Graph:
    """Build a graph from ``(i, j, w)`` edges; parallel edges add up.

    Self-loops and edges whose weight is not ``> 0`` are ignored.

    JS: CommunityDetection.js:makeGraph
    """
    maps: List[dict] = [dict() for _ in range(n)]
    for e in edges:
        a, b, w = int(e[0]), int(e[1]), e[2]
        if a == b or not (w > 0):
            continue
        w = float(w)
        maps[a][b] = maps[a].get(b, 0) + w
        maps[b][a] = maps[b].get(a, 0) + w
    k = [0.0] * n
    m2 = 0.0
    nbr = []
    for i, m in enumerate(maps):
        lst = []
        ki = 0.0
        for j, w in m.items():
            lst.append((j, w))
            ki += w
        k[i] = ki
        m2 += ki
        nbr.append(lst)
    return Graph(n, nbr, k, m2)


# ---------------------------------------------------------------------------- local moving


def leiden_local_moving(g: Graph, part: List[int], gamma: float, rng: Callable[[], float]) -> bool:
    """Leiden's fast local moving (modifies ``part`` in place).

    A queue holds all nodes in random order. Each node moves to the community
    with the largest gain ``w(v, C) - gamma * k_v * K_C / 2m`` (strictly larger
    than the current best by more than 1e-12; the current community is tried
    first). If every community gives a gain below -1e-12, the node moves to an
    empty community (the most recently emptied, or the largest unused id).
    When a node moves, its neighbours outside the new community that are not
    queued are appended to the queue. Returns True if any node moved.

    JS: CommunityDetection.js:leidenLocalMoving
    """
    n = g.n
    k = g.k
    m2 = g.m2
    if m2 == 0:  # no edges: every gain is NaN in JS, nothing moves
        shuffled(n, rng)
        return False
    nbr = g.nbr
    commK = [0.0] * (n + 1)
    changed = False
    maxId = 0
    for i in range(n):
        commK[part[i]] += k[i]
        if part[i] > maxId:
            maxId = part[i]
    used = [0] * max(n, maxId + 1)
    for i in range(n):
        used[part[i]] = 1
    empty = [i for i in range(len(used)) if not used[i]]
    queue = shuffled(n, rng)
    inQueue = [1] * n
    head = 0
    while head < len(queue):
        v = queue[head]
        head += 1
        inQueue[v] = 0
        cur = part[v]
        wTo: dict = {}
        for u, w in nbr[v]:
            c = part[u]
            wTo[c] = wTo.get(c, 0) + w
        kv = k[v]
        commK[cur] -= kv
        best = cur
        bestGain = wTo.get(cur, 0) - gamma * kv * commK[cur] / m2
        for c, w in wTo.items():
            gain = w - gamma * kv * commK[c] / m2
            if gain > bestGain + 1e-12:
                bestGain = gain
                best = c
        if bestGain < -1e-12 and empty:
            best = empty.pop()
            bestGain = 0
        commK[best] += kv
        if best != cur:
            if commK[cur] <= 1e-12:
                empty.append(cur)
            part[v] = best
            changed = True
            for u, _w in nbr[v]:
                if not inQueue[u] and part[u] != best:
                    inQueue[u] = 1
                    queue.append(u)
    return changed


def louvain_local_moving(g: Graph, part: List[int], gamma: float, rng: Callable[[], float]) -> bool:
    """Louvain's local moving: sweeps over all nodes in a new random order until
    a sweep moves nothing (at most 100 sweeps). Modifies ``part`` in place.

    JS: CommunityDetection.js:louvainLocalMoving
    """
    n = g.n
    k = g.k
    m2 = g.m2
    if m2 == 0:  # no edges: one sweep, nothing moves
        shuffled(n, rng)
        return False
    nbr = g.nbr
    commK = [0.0] * n
    changed = False
    moved = True
    sweeps = 0
    for i in range(n):
        commK[part[i]] += k[i]
    while moved:
        if not (sweeps < 100):
            break
        sweeps += 1
        moved = False
        for v in shuffled(n, rng):
            cur = part[v]
            wTo: dict = {}
            for u, w in nbr[v]:
                c = part[u]
                wTo[c] = wTo.get(c, 0) + w
            kv = k[v]
            commK[cur] -= kv
            best = cur
            bestGain = wTo.get(cur, 0) - gamma * kv * commK[cur] / m2
            for c, w in wTo.items():
                gain = w - gamma * kv * commK[c] / m2
                if gain > bestGain + 1e-12:
                    bestGain = gain
                    best = c
            commK[best] += kv
            if best != cur:
                part[v] = best
                moved = True
                changed = True
    return changed


# ---------------------------------------------------------------------------- refinement


def leiden_refine(g: Graph, part: Sequence[int], gamma: float, rng: Callable[[], float], theta: float) -> List[int]:
    """Leiden refinement as implemented by FlowMapper; returns the refined labels.

    Exactly what the code does (this differs in places from Algorithm A.2 of
    Traag, Waltman & van Eck 2019):

    1. Every node starts in its own refined sub-community (labelled by the node
       index). For each node, ``extW[v]`` = weight from ``v`` to the other
       members of its community in ``part``; for a sub-community ``S`` the array
       keeps ``w(S, C \\ S)``.
    2. Communities are visited in order of their first node; inside community
       ``C`` (total degree ``K_C``) the members are visited once, in a random
       order (one ``shuffled`` call per community).
    3. A node ``v`` is considered only if it is still a singleton and is
       well connected: ``w(v, C - v) >= gamma * k_v * (K_C - k_v) / 2m``.
    4. Candidates are the sub-communities ``S`` of ``C`` that ``v`` has an edge
       to (in the order the edges are first met), that are well connected
       (``w(S, C - S) >= gamma * K_S * (K_C - K_S) / 2m``) and whose gain
       ``w(v, S) - gamma * k_v * K_S / 2m`` is ``>= 0`` (the modularity change
       is ``dQ = gain / m``).
       **Unlike the original, staying alone is not a candidate**: whenever at
       least one candidate exists, ``v`` merges.
    5. With ``theta > 0``: ``S`` is drawn with probability proportional to
       ``exp((dQ_S - max dQ) / theta)`` (shifting by the maximum leaves the
       distribution unchanged). One random number ``r = rng() * sum`` is drawn
       and the first candidate whose cumulative weight reaches ``r`` is taken
       (the last one if rounding leaves ``r`` above the total). The original
       uses ``exp(dH / theta)`` over the same kind of candidates *plus* the
       option of staying.
       With ``theta == 0``: the candidate with the largest gain (first one on
       ties) is taken (greedy refinement).
    6. ``v`` joins ``S``: ``extW[S] += extW[v] - 2 w(v, S)``, ``K_S += k_v``.
       Each node is visited only once, so a sub-community never grows by a
       later merge of an earlier-visited node, and sub-communities are never
       merged with each other.

    In :func:`leiden` the aggregate network is built on the refined partition
    (initialised with the unrefined partition), except when refinement merged
    nothing: then the unrefined partition is aggregated (as in Louvain).

    JS: CommunityDetection.js:leidenRefine
    """
    n = g.n
    k = g.k
    m2 = g.m2
    nbr = g.nbr
    refined = list(range(n))
    refK = list(k)
    refSize = [1] * n
    extW = [0.0] * n
    commK: dict = {}
    members: dict = {}
    m = m2 / 2
    for i in range(n):
        c = part[i]
        commK[c] = commK.get(c, 0) + k[i]
        if c not in members:
            members[c] = []
        members[c].append(i)
    for i in range(n):
        w = 0
        pi = part[i]
        for u, wu in nbr[i]:
            if part[u] == pi:
                w += wu
        extW[i] = w
    if m2 == 0:  # no edges: JS compares with NaN and merges nothing
        for lst in members.values():
            shuffled(len(lst), rng)
        return refined
    for c, lst in members.items():
        KC = commK[c]
        order = [lst[ix] for ix in shuffled(len(lst), rng)]
        for v in order:
            if refSize[refined[v]] != 1:
                continue
            kv = k[v]
            if extW[v] < gamma * kv * (KC - kv) / m2:
                continue
            wToS: dict = {}
            rv = refined[v]
            for u, wu in nbr[v]:
                if part[u] == c and refined[u] != rv:
                    S = refined[u]
                    wToS[S] = wToS.get(S, 0) + wu
            cand = []
            for S, wv in wToS.items():
                if extW[S] < gamma * refK[S] * (KC - refK[S]) / m2:
                    continue
                gain = wv - gamma * kv * refK[S] / m2
                if gain >= 0:
                    cand.append((S, gain))
            if not cand:
                continue
            if theta > 0:
                maxQ = max(c2[1] / m for c2 in cand)
                ws = [js_exp((c2[1] / m - maxQ) / theta) for c2 in cand]
                tot = 0
                for x in ws:
                    tot += x
                r = rng() * tot
                acc = 0
                best = cand[-1][0]
                for q in range(len(cand)):
                    acc += ws[q]
                    if r <= acc:
                        best = cand[q][0]
                        break
            else:
                bc = cand[0]
                for b in cand[1:]:
                    if b[1] > bc[1]:
                        bc = b
                best = bc[0]
            self_ = refined[v]
            extW[best] = extW[best] + extW[self_] - 2 * wToS[best]
            refK[best] += refK[self_]
            refSize[best] += 1
            refK[self_] = 0
            refSize[self_] = 0
            refined[v] = best
    return refined


# ---------------------------------------------------------------------------- aggregation


def relabel(arr: Sequence[int]) -> Tuple[List[int], int]:
    """Labels renumbered 0, 1, ... in order of first appearance; returns (labels, count).

    JS: CommunityDetection.js:relabel
    """
    mp: dict = {}
    out = [0] * len(arr)
    for i, a in enumerate(arr):
        if a not in mp:
            mp[a] = len(mp)
        out[i] = mp[a]
    return out, len(mp)


def aggregate_graph(g: Graph, labels: Sequence[int], count: int) -> Graph:
    """Collapse each community into one node (edges inside a community dropped;
    the aggregated node keeps the summed degree, so ``m2`` is unchanged).

    JS: CommunityDetection.js:aggregateGraph
    """
    maps: List[dict] = [dict() for _ in range(count)]
    k = [0.0] * count
    for i in range(g.n):
        a = labels[i]
        k[a] += g.k[i]
        ma = maps[a]
        for u, w in g.nbr[i]:
            b = labels[u]
            if a != b:
                ma[b] = ma.get(b, 0) + w
    return Graph(count, [list(m.items()) for m in maps], k, g.m2)


def _seed(seed) -> float:
    # JS: seed || 1
    if seed is None or seed == 0 or (isinstance(seed, float) and seed != seed):
        return 1
    return seed


def leiden(g0: Graph, gamma: float = 1.0, seed: float = 1, theta: float = 0.01) -> List[int]:
    """Leiden algorithm (Traag et al. 2019) as in FlowMapper; returns community labels.

    Each level: fast local moving, refinement (:func:`leiden_refine`), then
    aggregation of the refined partition with the moved partition as the start
    of the next level (the moved partition is aggregated instead when the
    refinement merged nothing). Stops when local moving leaves every node in
    its own community, or after 50 levels. Labels are numbered in order of
    first appearance.

    JS: CommunityDetection.js:leiden
    """
    rng = mulberry32(_seed(seed))
    g = g0
    part = list(range(g.n))
    owner = list(range(g0.n))
    for _level in range(50):
        leiden_local_moving(g, part, gamma, rng)
        p_labels, p_count = relabel(part)
        if p_count == g.n:
            break
        r_labels, r_count = relabel(leiden_refine(g, p_labels, gamma, rng, theta))
        if r_count < g.n:
            by_labels, by_count = r_labels, r_count
        else:
            by_labels, by_count = p_labels, p_count
        nxt = aggregate_graph(g, by_labels, by_count)
        nextPart = [0] * by_count
        for i in range(g.n):
            nextPart[by_labels[i]] = p_labels[i]
        owner = [by_labels[o] for o in owner]
        g = nxt
        part = nextPart
    result = [part[o] for o in owner]
    return relabel(result)[0]


def louvain(g0: Graph, gamma: float = 1.0, seed: float = 1) -> List[int]:
    """Louvain algorithm (Blondel et al. 2008) as in FlowMapper; returns labels.

    Each level: Louvain local moving from singletons, then aggregation of the
    moved partition, until nothing moves (at most 50 levels).

    JS: CommunityDetection.js:louvain
    """
    rng = mulberry32(_seed(seed))
    g = g0
    owner = list(range(g0.n))
    for _level in range(50):
        part = list(range(g.n))
        if not louvain_local_moving(g, part, gamma, rng):
            break
        p_labels, p_count = relabel(part)
        if p_count == g.n:
            break
        owner = [p_labels[o] for o in owner]
        g = aggregate_graph(g, p_labels, p_count)
    return relabel(owner)[0]


def modularity(g: Graph, labels: Sequence[int], gamma: float = 1.0) -> float:
    """Modularity of a partition with resolution ``gamma``.

    JS: CommunityDetection.js:modularity
    """
    q = 0
    commK: dict = {}
    inW: dict = {}
    for i in range(g.n):
        li = labels[i]
        commK[li] = commK.get(li, 0) + g.k[i]
        for u, w in g.nbr[i]:
            if labels[u] == li:
                inW[li] = inW.get(li, 0) + w
    m2 = g.m2
    if m2 == 0:
        return math.nan if commK else 0
    for c, K in commK.items():
        q += inW.get(c, 0) / m2 - gamma * (K / m2) * (K / m2)
    return q

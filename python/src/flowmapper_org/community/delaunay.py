"""Port of ``d3.Delaunay`` / ``Delaunator`` / ``d3.Voronoi`` (d3 v6.2.0 bundle).

FlowMapper uses d3-delaunay for the Delaunay neighbours of the nodes (spatial
contiguity when no polygons are joined), for Voronoi cells (region boundaries)
and for nearest-node lookups. The order of neighbours and the exact cell
vertices influence the results (merge tie-breaking, dissolved rings), so the
library is ported line by line instead of using scipy/shapely.

Only what FlowMapper calls is ported: ``Delaunay.from``, ``neighbors``,
``find``, ``voronoi(bounds)`` and ``Voronoi.cellPolygon``.
"""
from __future__ import annotations

import math
from typing import Iterator, List, Optional, Sequence

EPSILON = 2.0 ** -52
_EDGE_STACK_LEN = 512
_INF = math.inf


def _div(a: float, b: float) -> float:
    """IEEE division (JavaScript semantics: x/0 = +-Infinity, 0/0 = NaN)."""
    if b != 0:
        return a / b
    if a != a or a == 0:
        return math.nan
    return math.copysign(_INF, a) * math.copysign(1.0, b)


def _mul(a: float, b: float) -> float:
    # inf * 0 -> NaN without exceptions (Python already does this for floats)
    return a * b


def _truthy(x) -> bool:
    """JavaScript truthiness of a number (0, NaN, undefined are false)."""
    return x is not None and x == x and x != 0


def _pseudo_angle(dx: float, dy: float) -> float:
    p = _div(dx, abs(dx) + abs(dy))
    return (3 - p if dy > 0 else 1 + p) / 4


def _dist(ax, ay, bx, by):
    dx = ax - bx
    dy = ay - by
    return dx * dx + dy * dy


def _orient_if_sure(px, py, rx, ry, qx, qy):
    l = (ry - py) * (qx - px)
    r = (rx - px) * (qy - py)
    return l - r if abs(l - r) >= 3.3306690738754716e-16 * abs(l + r) else 0


def _orient(rx, ry, qx, qy, px, py) -> bool:
    sign = _orient_if_sure(px, py, rx, ry, qx, qy)
    if not _truthy(sign):
        sign = _orient_if_sure(rx, ry, qx, qy, px, py)
        if not _truthy(sign):
            sign = _orient_if_sure(qx, qy, px, py, rx, ry)
    return sign < 0


def _in_circle(ax, ay, bx, by, cx, cy, px, py) -> bool:
    dx = ax - px
    dy = ay - py
    ex = bx - px
    ey = by - py
    fx = cx - px
    fy = cy - py
    ap = dx * dx + dy * dy
    bp = ex * ex + ey * ey
    cp = fx * fx + fy * fy
    return dx * (ey * cp - bp * fy) - dy * (ex * cp - bp * fx) + ap * (ex * fy - ey * fx) < 0


def _circumradius(ax, ay, bx, by, cx, cy):
    dx = bx - ax
    dy = by - ay
    ex = cx - ax
    ey = cy - ay
    bl = dx * dx + dy * dy
    cl = ex * ex + ey * ey
    d = _div(0.5, dx * ey - dy * ex)
    x = (ey * bl - dy * cl) * d
    y = (dx * cl - ex * bl) * d
    return x * x + y * y


def _circumcenter(ax, ay, bx, by, cx, cy):
    dx = bx - ax
    dy = by - ay
    ex = cx - ax
    ey = cy - ay
    bl = dx * dx + dy * dy
    cl = ex * ex + ey * ey
    d = _div(0.5, dx * ey - dy * ex)
    return ax + (ey * bl - dy * cl) * d, ay + (dx * cl - ex * bl) * d


def _quicksort(ids, dists, left, right):
    if right - left <= 20:
        for i in range(left + 1, right + 1):
            temp = ids[i]
            tempDist = dists[temp]
            j = i - 1
            while j >= left and dists[ids[j]] > tempDist:
                ids[j + 1] = ids[j]
                j -= 1
            ids[j + 1] = temp
    else:
        median = (left + right) >> 1
        i = left + 1
        j = right
        ids[median], ids[i] = ids[i], ids[median]
        if dists[ids[left]] > dists[ids[right]]:
            ids[left], ids[right] = ids[right], ids[left]
        if dists[ids[i]] > dists[ids[right]]:
            ids[i], ids[right] = ids[right], ids[i]
        if dists[ids[left]] > dists[ids[i]]:
            ids[left], ids[i] = ids[i], ids[left]
        temp = ids[i]
        tempDist = dists[temp]
        while True:
            i += 1
            while dists[ids[i]] < tempDist:
                i += 1
            j -= 1
            while dists[ids[j]] > tempDist:
                j -= 1
            if j < i:
                break
            ids[i], ids[j] = ids[j], ids[i]
        ids[left + 1] = ids[j]
        ids[j] = temp
        if right - i + 1 >= j - left:
            _quicksort(ids, dists, i, right)
            _quicksort(ids, dists, left, j - 1)
        else:
            _quicksort(ids, dists, left, j - 1)
            _quicksort(ids, dists, i, right)


class Delaunator:
    """Port of Delaunator (bundled in d3 v6.2.0)."""

    def __init__(self, coords: List[float]):
        n = len(coords) >> 1
        self.coords = coords
        maxTriangles = max(2 * n - 5, 0)
        self._triangles = [0] * (maxTriangles * 3)
        self._halfedges = [0] * (maxTriangles * 3)
        self._hashSize = math.ceil(math.sqrt(n))
        self._hullPrev = [0] * n
        self._hullNext = [0] * n
        self._hullTri = [0] * n
        self._hullHash = [-1] * self._hashSize
        self._ids = [0] * n
        self._dists = [0.0] * n
        self._update()

    def _hash_key(self, x, y):
        v = _pseudo_angle(x - self._cx, y - self._cy) * self._hashSize
        if v != v:
            return None
        return math.floor(v) % self._hashSize

    def _update(self):
        coords = self.coords
        hullPrev, hullNext, hullTri, hullHash = self._hullPrev, self._hullNext, self._hullTri, self._hullHash
        n = len(coords) >> 1
        minX = minY = _INF
        maxX = maxY = -_INF
        for i in range(n):
            x = coords[2 * i]
            y = coords[2 * i + 1]
            if x < minX:
                minX = x
            if y < minY:
                minY = y
            if x > maxX:
                maxX = x
            if y > maxY:
                maxY = y
            self._ids[i] = i
        cx = (minX + maxX) / 2
        cy = (minY + maxY) / 2
        minDist = _INF
        i0 = i1 = i2 = None
        for i in range(n):
            d = _dist(cx, cy, coords[2 * i], coords[2 * i + 1])
            if d < minDist:
                i0 = i
                minDist = d
        i0x = coords[2 * i0]
        i0y = coords[2 * i0 + 1]
        minDist = _INF
        for i in range(n):
            if i == i0:
                continue
            d = _dist(i0x, i0y, coords[2 * i], coords[2 * i + 1])
            if d < minDist and d > 0:
                i1 = i
                minDist = d
        if i1 is None:
            i1x = i1y = math.nan
        else:
            i1x = coords[2 * i1]
            i1y = coords[2 * i1 + 1]
        minRadius = _INF
        for i in range(n):
            if i == i0 or i == i1:
                continue
            r = _circumradius(i0x, i0y, i1x, i1y, coords[2 * i], coords[2 * i + 1])
            if r < minRadius:
                i2 = i
                minRadius = r
        if minRadius == _INF:
            for i in range(n):
                a = coords[2 * i] - coords[0]
                self._dists[i] = a if _truthy(a) else (coords[2 * i + 1] - coords[1])
            _quicksort(self._ids, self._dists, 0, n - 1)
            hull = []
            d0 = -_INF
            for i in range(n):
                id_ = self._ids[i]
                if self._dists[id_] > d0:
                    hull.append(id_)
                    d0 = self._dists[id_]
            self.hull = hull
            self.triangles = []
            self.halfedges = []
            return
        i2x = coords[2 * i2]
        i2y = coords[2 * i2 + 1]
        if _orient(i0x, i0y, i1x, i1y, i2x, i2y):
            i1, i2 = i2, i1
            i1x, i2x = i2x, i1x
            i1y, i2y = i2y, i1y
        ccx, ccy = _circumcenter(i0x, i0y, i1x, i1y, i2x, i2y)
        self._cx = ccx
        self._cy = ccy
        for i in range(n):
            self._dists[i] = _dist(coords[2 * i], coords[2 * i + 1], ccx, ccy)
        _quicksort(self._ids, self._dists, 0, n - 1)
        self._hullStart = i0
        hullSize = 3
        hullNext[i0] = hullPrev[i2] = i1
        hullNext[i1] = hullPrev[i0] = i2
        hullNext[i2] = hullPrev[i1] = i0
        hullTri[i0] = 0
        hullTri[i1] = 1
        hullTri[i2] = 2
        for j in range(len(hullHash)):
            hullHash[j] = -1
        for (px, py, pi) in ((i0x, i0y, i0), (i1x, i1y, i1), (i2x, i2y, i2)):
            hk = self._hash_key(px, py)
            if hk is not None:
                hullHash[hk] = pi
        self.trianglesLen = 0
        self._add_triangle(i0, i1, i2, -1, -1, -1)
        xp = yp = None
        for kk in range(len(self._ids)):
            i = self._ids[kk]
            x = coords[2 * i]
            y = coords[2 * i + 1]
            if kk > 0 and abs(x - xp) <= EPSILON and abs(y - yp) <= EPSILON:
                continue
            xp = x
            yp = y
            if i == i0 or i == i1 or i == i2:
                continue
            start = 0
            key = self._hash_key(x, y)
            for j in range(self._hashSize):
                start = hullHash[(key + j) % self._hashSize] if key is not None else None
                if start is None:
                    start = 0  # pragma: no cover - NaN hash (degenerate)
                    break
                if start != -1 and start != hullNext[start]:
                    break
            start = hullPrev[start]
            e = start
            while True:
                q = hullNext[e]
                if _orient(x, y, coords[2 * e], coords[2 * e + 1], coords[2 * q], coords[2 * q + 1]):
                    break
                e = q
                if e == start:
                    e = -1
                    break
            if e == -1:
                continue
            t = self._add_triangle(e, i, hullNext[e], -1, -1, hullTri[e])
            hullTri[i] = self._legalize(t + 2)
            hullTri[e] = t
            hullSize += 1
            nn = hullNext[e]
            while True:
                q = hullNext[nn]
                if not _orient(x, y, coords[2 * nn], coords[2 * nn + 1], coords[2 * q], coords[2 * q + 1]):
                    break
                t = self._add_triangle(nn, i, q, hullTri[i], -1, hullTri[nn])
                hullTri[i] = self._legalize(t + 2)
                hullNext[nn] = nn
                hullSize -= 1
                nn = q
            if e == start:
                while True:
                    q = hullPrev[e]
                    if not _orient(x, y, coords[2 * q], coords[2 * q + 1], coords[2 * e], coords[2 * e + 1]):
                        break
                    t = self._add_triangle(q, i, e, -1, hullTri[e], hullTri[q])
                    self._legalize(t + 2)
                    hullTri[q] = t
                    hullNext[e] = e
                    hullSize -= 1
                    e = q
            self._hullStart = hullPrev[i] = e
            hullNext[e] = hullPrev[nn] = i
            hullNext[i] = nn
            hk = self._hash_key(x, y)
            if hk is not None:
                hullHash[hk] = i
            hk = self._hash_key(coords[2 * e], coords[2 * e + 1])
            if hk is not None:
                hullHash[hk] = e
        hull = [0] * hullSize
        e = self._hullStart
        for i in range(hullSize):
            hull[i] = e
            e = hullNext[e]
        self.hull = hull
        self.triangles = self._triangles[: self.trianglesLen]
        self.halfedges = self._halfedges[: self.trianglesLen]

    def _legalize(self, a):
        triangles, halfedges, coords = self._triangles, self._halfedges, self.coords
        stack: List[int] = []
        ar = 0
        while True:
            b = halfedges[a]
            a0 = a - a % 3
            ar = a0 + (a + 2) % 3
            if b == -1:
                if not stack:
                    break
                a = stack.pop()
                continue
            b0 = b - b % 3
            al = a0 + (a + 1) % 3
            bl = b0 + (b + 2) % 3
            p0 = triangles[ar]
            pr = triangles[a]
            pl = triangles[al]
            p1 = triangles[bl]
            illegal = _in_circle(coords[2 * p0], coords[2 * p0 + 1], coords[2 * pr], coords[2 * pr + 1],
                                 coords[2 * pl], coords[2 * pl + 1], coords[2 * p1], coords[2 * p1 + 1])
            if illegal:
                triangles[a] = p1
                triangles[b] = p0
                hbl = halfedges[bl]
                if hbl == -1:
                    e = self._hullStart
                    while True:
                        if self._hullTri[e] == bl:
                            self._hullTri[e] = a
                            break
                        e = self._hullPrev[e]
                        if e == self._hullStart:
                            break
                self._link(a, hbl)
                self._link(b, halfedges[ar])
                self._link(ar, bl)
                br = b0 + (b + 1) % 3
                if len(stack) < _EDGE_STACK_LEN:
                    stack.append(br)
            else:
                if not stack:
                    break
                a = stack.pop()
        return ar

    def _link(self, a, b):
        self._halfedges[a] = b
        if b != -1:
            self._halfedges[b] = a

    def _add_triangle(self, i0, i1, i2, a, b, c):
        t = self.trianglesLen
        self._triangles[t] = i0
        self._triangles[t + 1] = i1
        self._triangles[t + 2] = i2
        self._link(t, a)
        self._link(t + 1, b)
        self._link(t + 2, c)
        self.trianglesLen += 3
        return t


def _collinear(d: Delaunator) -> bool:
    triangles, coords = d.triangles, d.coords
    for i in range(0, len(triangles), 3):
        a = 2 * triangles[i]
        b = 2 * triangles[i + 1]
        c = 2 * triangles[i + 2]
        cross = (coords[c] - coords[a]) * (coords[b + 1] - coords[a + 1]) - (coords[b] - coords[a]) * (coords[c + 1] - coords[a + 1])
        if cross > 1e-10:
            return False
    return True


class Delaunay:
    """Port of ``d3.Delaunay`` (d3 v6.2.0)."""

    @classmethod
    def from_points(cls, points: Sequence[Sequence[float]]) -> "Delaunay":
        coords: List[float] = []
        for p in points:
            coords.append(float(p[0]))
            coords.append(float(p[1]))
        return cls(coords)

    def __init__(self, points: List[float]):
        self._delaunator = Delaunator(points)
        self.inedges = [-1] * (len(points) // 2)
        self._hullIndex = [-1] * (len(points) // 2)
        self.points = self._delaunator.coords
        self.collinear: Optional[List[int]] = None
        self._init()

    def _init(self):
        d = self._delaunator
        points = self.points
        if d.hull and len(d.hull) > 2 and _collinear(d):
            n = len(points) // 2
            self.collinear = sorted(range(n), key=lambda i: (points[2 * i], points[2 * i + 1]))
            e = self.collinear[0]
            f = self.collinear[-1]
            bounds = [points[2 * e], points[2 * e + 1], points[2 * f], points[2 * f + 1]]
            from ._jsmath import js_cos, js_hypot, js_sin
            r = 1e-8 * js_hypot(bounds[3] - bounds[1], bounds[2] - bounds[0])
            for i in range(n):
                x, y = points[2 * i], points[2 * i + 1]
                points[2 * i] = x + js_sin(x + y) * r
                points[2 * i + 1] = y + js_cos(x - y) * r
            self._delaunator = Delaunator(points)
        else:
            self.collinear = None
        self.halfedges = halfedges = self._delaunator.halfedges
        self.hull = hull = self._delaunator.hull
        self.triangles = triangles = self._delaunator.triangles
        inedges = self.inedges = [-1] * len(self.inedges)
        hullIndex = self._hullIndex = [-1] * len(self._hullIndex)
        for e in range(len(halfedges)):
            p = triangles[e - 2 if e % 3 == 2 else e + 1]
            if halfedges[e] == -1 or inedges[p] == -1:
                inedges[p] = e
        for i in range(len(hull)):
            hullIndex[hull[i]] = i
        if 0 < len(hull) <= 2:
            self.triangles = [-1, -1, -1]
            self.halfedges = [-1, -1, -1]
            self.triangles[0] = hull[0]
            # Int32Array stores hull[1] === undefined as 0
            self.triangles[1] = hull[1] if len(hull) > 1 else 0
            self.triangles[2] = hull[1] if len(hull) > 1 else 0
            inedges[hull[0]] = 1
            if len(hull) == 2:
                inedges[hull[1]] = 0

    def voronoi(self, bounds) -> "Voronoi":
        return Voronoi(self, bounds)

    def neighbors(self, i: int) -> Iterator[int]:
        inedges, hull, _hullIndex, halfedges, triangles, collinear = (
            self.inedges, self.hull, self._hullIndex, self.halfedges, self.triangles, self.collinear)
        if collinear is not None:
            l = collinear.index(i) if i in collinear else -1
            if l > 0:
                yield collinear[l - 1]
            if l < len(collinear) - 1:
                yield collinear[l + 1]
            return
        e0 = inedges[i]
        if e0 == -1:
            return
        e = e0
        p0 = -1
        while True:
            p0 = triangles[e]
            yield p0
            e = e - 2 if e % 3 == 2 else e + 1
            if triangles[e] != i:
                return
            e = halfedges[e]
            if e == -1:
                p = hull[(_hullIndex[i] + 1) % len(hull)]
                if p != p0:
                    yield p
                return
            if e == e0:
                break

    def find(self, x: float, y: float, i: int = 0) -> int:
        x = float(x)
        y = float(y)
        if x != x or y != y:
            return -1
        i0 = i
        while True:
            c = self._step(i, x, y)
            if c >= 0 and c != i and c != i0:
                i = c
            else:
                return c

    def _step(self, i: int, x: float, y: float) -> int:
        inedges, hull, _hullIndex, halfedges, triangles, points = (
            self.inedges, self.hull, self._hullIndex, self.halfedges, self.triangles, self.points)
        if inedges[i] == -1 or not points:
            return (i + 1) % (len(points) >> 1)
        c = i
        dx = x - points[i * 2]
        dy = y - points[i * 2 + 1]
        dc = dx * dx + dy * dy
        e0 = inedges[i]
        e = e0
        while True:
            t = triangles[e]
            dx = x - points[t * 2]
            dy = y - points[t * 2 + 1]
            dt = dx * dx + dy * dy
            if dt < dc:
                dc = dt
                c = t
            e = e - 2 if e % 3 == 2 else e + 1
            if triangles[e] != i:
                break
            e = halfedges[e]
            if e == -1:
                e = hull[(_hullIndex[i] + 1) % len(hull)]
                if e != t:
                    dx = x - points[e * 2]
                    dy = y - points[e * 2 + 1]
                    if dx * dx + dy * dy < dc:
                        return e
                break
            if e == e0:
                break
        return c


class Voronoi:
    """Port of ``d3.Voronoi`` (cell polygons clipped to a rectangle)."""

    def __init__(self, delaunay: Delaunay, bounds=(0, 0, 960, 500)):
        xmin, ymin, xmax, ymax = (float(b) for b in bounds)
        if not (xmax >= xmin) or not (ymax >= ymin):
            raise ValueError("invalid bounds")
        self.delaunay = delaunay
        self.xmax, self.xmin, self.ymax, self.ymin = xmax, xmin, ymax, ymin
        self._init()

    def _init(self):
        d = self.delaunay
        points, hull, triangles = d.points, d.hull, d.triangles
        ntri = len(triangles) // 3
        cc = [0.0] * (ntri * 2)
        j = 0
        for i in range(0, len(triangles), 3):
            t1 = triangles[i] * 2
            t2 = triangles[i + 1] * 2
            t3 = triangles[i + 2] * 2
            x1 = points[t1]
            y1 = points[t1 + 1]
            x2 = points[t2]
            y2 = points[t2 + 1]
            x3 = points[t3]
            y3 = points[t3 + 1]
            dx = x2 - x1
            dy = y2 - y1
            ex = x3 - x1
            ey = y3 - y1
            bl = dx * dx + dy * dy
            cl = ex * ex + ey * ey
            ab = (dx * ey - dy * ex) * 2
            if not _truthy(ab):
                x = (x1 + x3) / 2 - 1e8 * ey
                y = (y1 + y3) / 2 + 1e8 * ex
            elif abs(ab) < 1e-8:
                x = (x1 + x3) / 2
                y = (y1 + y3) / 2
            else:
                dd = 1 / ab
                x = x1 + (ey * bl - dy * cl) * dd
                y = y1 + (dx * cl - ex * bl) * dd
            cc[j] = x
            cc[j + 1] = y
            j += 2
        self.circumcenters = cc
        vectors = [0.0] * (len(points) * 2)
        h = hull[-1]
        p1 = h * 4
        x1 = points[2 * h]
        y1 = points[2 * h + 1]
        for i in range(len(hull)):
            h = hull[i]
            p0, x0, y0 = p1, x1, y1
            p1, x1, y1 = h * 4, points[2 * h], points[2 * h + 1]
            vectors[p0 + 2] = vectors[p1] = y0 - y1
            vectors[p0 + 3] = vectors[p1 + 1] = x1 - x0
        self.vectors = vectors

    # -- cells
    def cell_polygon(self, i: int) -> Optional[List[List[float]]]:
        """Clipped cell of point ``i`` as a closed ring, or None."""
        points = self._clip(i)
        if points is None or not points:
            return None
        poly = [[points[0], points[1]]]
        n = len(points)
        while points[0] == points[n - 2] and points[1] == points[n - 1] and n > 1:
            n -= 2
        for k in range(2, n, 2):
            if points[k] != points[k - 2] or points[k + 1] != points[k - 1]:
                poly.append([points[k], points[k + 1]])
        poly.append(list(poly[0]))
        return poly

    def contains(self, i, x, y) -> bool:
        x = float(x)
        y = float(y)
        if x != x or y != y:
            return False
        return self.delaunay._step(i, x, y) == i

    def _cell(self, i):
        cc = self.circumcenters
        d = self.delaunay
        inedges, halfedges, triangles = d.inedges, d.halfedges, d.triangles
        e0 = inedges[i]
        if e0 == -1:
            return None
        pts = []
        e = e0
        while True:
            t = e // 3
            pts.append(cc[t * 2])
            pts.append(cc[t * 2 + 1])
            e = e - 2 if e % 3 == 2 else e + 1
            if triangles[e] != i:
                break
            e = halfedges[e]
            if e == e0 or e == -1:
                break
        return pts

    def _clip(self, i):
        if i == 0 and len(self.delaunay.hull) == 1:
            return [self.xmax, self.ymin, self.xmax, self.ymax, self.xmin, self.ymax, self.xmin, self.ymin]
        pts = self._cell(i)
        if pts is None:
            return None
        V = self.vectors
        v = i * 4
        if _truthy(V[v]) or _truthy(V[v + 1]):
            return self._clip_infinite(i, pts, V[v], V[v + 1], V[v + 2], V[v + 3])
        return self._clip_finite(i, pts)

    def _clip_finite(self, i, points):
        n = len(points)
        P = None
        x1 = points[n - 2]
        y1 = points[n - 1]
        c1 = self._regioncode(x1, y1)
        e0 = e1 = None
        for j in range(0, n, 2):
            x0, y0 = x1, y1
            x1, y1 = points[j], points[j + 1]
            c0, c1 = c1, self._regioncode(x1, y1)
            if c0 == 0 and c1 == 0:
                e0, e1 = e1, 0
                if P is not None:
                    P.extend((x1, y1))
                else:
                    P = [x1, y1]
            else:
                if c0 == 0:
                    S = self._clip_segment(x0, y0, x1, y1, c0, c1)
                    if S is None:
                        continue
                    sx0, sy0, sx1, sy1 = S
                else:
                    S = self._clip_segment(x1, y1, x0, y0, c1, c0)
                    if S is None:
                        continue
                    sx1, sy1, sx0, sy0 = S
                    e0, e1 = e1, self._edgecode(sx0, sy0)
                    if e0 and e1:
                        self._edge(i, e0, e1, P, len(P))
                    if P is not None:
                        P.extend((sx0, sy0))
                    else:
                        P = [sx0, sy0]
                e0, e1 = e1, self._edgecode(sx1, sy1)
                if e0 and e1:
                    self._edge(i, e0, e1, P, len(P))
                if P is not None:
                    P.extend((sx1, sy1))
                else:
                    P = [sx1, sy1]
        if P is not None:
            e0, e1 = e1, self._edgecode(P[0], P[1])
            if e0 and e1:
                self._edge(i, e0, e1, P, len(P))
        elif self.contains(i, (self.xmin + self.xmax) / 2, (self.ymin + self.ymax) / 2):
            return [self.xmax, self.ymin, self.xmax, self.ymax, self.xmin, self.ymax, self.xmin, self.ymin]
        return P

    def _clip_segment(self, x0, y0, x1, y1, c0, c1):
        while True:
            if c0 == 0 and c1 == 0:
                return [x0, y0, x1, y1]
            if c0 & c1:
                return None
            c = c0 or c1
            # JS evaluates a + b * c / d as a + ((b * c) / d)
            if c & 0b1000:
                x = x0 + _div((x1 - x0) * (self.ymax - y0), y1 - y0)
                y = self.ymax
            elif c & 0b0100:
                x = x0 + _div((x1 - x0) * (self.ymin - y0), y1 - y0)
                y = self.ymin
            elif c & 0b0010:
                y = y0 + _div((y1 - y0) * (self.xmax - x0), x1 - x0)
                x = self.xmax
            else:
                y = y0 + _div((y1 - y0) * (self.xmin - x0), x1 - x0)
                x = self.xmin
            if c0:
                x0, y0 = x, y
                c0 = self._regioncode(x0, y0)
            else:
                x1, y1 = x, y
                c1 = self._regioncode(x1, y1)

    def _clip_infinite(self, i, points, vx0, vy0, vxn, vyn):
        P = list(points)
        p = self._project(P[0], P[1], vx0, vy0)
        if p:
            P[0:0] = [p[0], p[1]]
        p = self._project(P[-2], P[-1], vxn, vyn)
        if p:
            P.extend((p[0], p[1]))
        P = self._clip_finite(i, P)
        if P:
            n = len(P)
            c1 = self._edgecode(P[n - 2], P[n - 1])
            j = 0
            while j < n:
                c0, c1 = c1, self._edgecode(P[j], P[j + 1])
                if c0 and c1:
                    j = self._edge(i, c0, c1, P, j)
                    n = len(P)
                j += 2
        elif self.contains(i, (self.xmin + self.xmax) / 2, (self.ymin + self.ymax) / 2):
            P = [self.xmin, self.ymin, self.xmax, self.ymin, self.xmax, self.ymax, self.xmin, self.ymax]
        return P

    def _edge(self, i, e0, e1, P, j):
        while e0 != e1:
            if e0 == 0b0101:
                e0 = 0b0100
                continue
            elif e0 == 0b0100:
                e0, x, y = 0b0110, self.xmax, self.ymin
            elif e0 == 0b0110:
                e0 = 0b0010
                continue
            elif e0 == 0b0010:
                e0, x, y = 0b1010, self.xmax, self.ymax
            elif e0 == 0b1010:
                e0 = 0b1000
                continue
            elif e0 == 0b1000:
                e0, x, y = 0b1001, self.xmin, self.ymax
            elif e0 == 0b1001:
                e0 = 0b0001
                continue
            elif e0 == 0b0001:
                e0, x, y = 0b0101, self.xmin, self.ymin
            else:  # pragma: no cover - cannot happen for edge codes
                break
            pj = P[j] if j < len(P) else None
            pj1 = P[j + 1] if j + 1 < len(P) else None
            if (pj != x or pj1 != y) and self.contains(i, x, y):
                P[j:j] = [x, y]
                j += 2
        if len(P) > 4:
            ii = 0
            while ii < len(P):
                L = len(P)
                jj = (ii + 2) % L
                kk = (ii + 4) % L
                if (P[ii] == P[jj] and P[jj] == P[kk]) or (P[ii + 1] == P[jj + 1] and P[jj + 1] == P[kk + 1]):
                    del P[jj:jj + 2]
                    ii -= 2
                ii += 2
        return j

    def _project(self, x0, y0, vx, vy):
        t = _INF
        x = y = None
        if vy < 0:
            if y0 <= self.ymin:
                return None
            c = (self.ymin - y0) / vy
            if c < t:
                y = self.ymin
                t = c
                x = x0 + t * vx
        elif vy > 0:
            if y0 >= self.ymax:
                return None
            c = (self.ymax - y0) / vy
            if c < t:
                y = self.ymax
                t = c
                x = x0 + t * vx
        if vx > 0:
            if x0 >= self.xmax:
                return None
            c = (self.xmax - x0) / vx
            if c < t:
                x = self.xmax
                t = c
                y = y0 + t * vy
        elif vx < 0:
            if x0 <= self.xmin:
                return None
            c = (self.xmin - x0) / vx
            if c < t:
                x = self.xmin
                t = c
                y = y0 + t * vy
        return [x, y]

    def _edgecode(self, x, y):
        return ((0b0001 if x == self.xmin else 0b0010 if x == self.xmax else 0)
                | (0b0100 if y == self.ymin else 0b1000 if y == self.ymax else 0))

    def _regioncode(self, x, y):
        return ((0b0001 if x < self.xmin else 0b0010 if x > self.xmax else 0)
                | (0b0100 if y < self.ymin else 0b1000 if y > self.ymax else 0))

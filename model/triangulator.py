from __future__ import annotations
from shapely.geometry import MultiLineString, LineString
from shapely.ops import unary_union
import numpy as np
from geometry import Point2D, Polyline, Triangle


class Triangulator:
    """Устойчивое построение TIN с тремя бэкендами (SciPy → triangle → Numba)."""

    
    def __init__(self, polylines: list[Polyline]):
        self.polylines = polylines
        self.points    = [p for pl in polylines for p in pl]
        self.triangles: list[Triangle] = []

    
    def _prep(self, tol: float = 0.5):
        """Deduplicate + simplify (Douglas–Peucker)"""
        ml = MultiLineString(
            [[(p.x, p.y) for p in pl] for pl in self.polylines]
        )
        merged = unary_union(ml).simplify(tol, preserve_topology=True)

        new: list[Polyline] = []
        to_pl = lambda coords, z: Polyline([Point2D(x, y, z) for x, y in coords], z)

        if isinstance(merged, LineString):
            new.append(to_pl(list(merged.coords), self.polylines[0].elev))
        else:
            for ln, src in zip(merged, self.polylines * 9999):
                new.append(to_pl(list(ln.coords), src.elev))

        self.points = [p for pl in new for p in pl]

    
    def build(self):
        """1) SciPy / Qhull (30 s тайм-аут) → 2) triangle-lib → 3) Bowyer–Watson."""
        # A. нет высоты — TIN не нужен
        if all(p.z == 0 for p in self.points):
            self.triangles = []
            return

        # B. подготовка
        self._prep()

        # ── SciPy ­──────────────────────────────────────────────────
        try:
            from concurrent.futures import ThreadPoolExecutor, TimeoutError
            from scipy.spatial import Delaunay, qhull

            coords = np.unique(np.array([(p.x, p.y) for p in self.points]), axis=0)
            if coords.shape[0] < 3:           # коллинеарный набор
                self.triangles = []
                return

            def _qhull(arr):
                return Delaunay(arr, qhull_options="Qbb Qc Qz QJ").simplices

            with ThreadPoolExecutor(max_workers=1) as ex:
                simp = ex.submit(_qhull, coords).result(timeout=30)

            self.triangles = [
                Triangle(self.points[i], self.points[j], self.points[k])
                for i, j, k in simp
            ]
            return
        except Exception:
            print("[Triangulator] SciPy/Qhull → fallback triangle-lib")

        # ── triangle-lib ­──────────────────────────────────────────
        try:
            import triangle as tr

            simplices = tr.triangulate(
                {"vertices": coords}, "Q"
            )["triangles"]
            self.triangles = [
                Triangle(self.points[i], self.points[j], self.points[k])
                for i, j, k in simplices
            ]
            return
        except Exception:
            print("[Triangulator] triangle-lib → fallback Bowyer–Watson")

        # ── Bowyer–Watson + Numba ­─────────────────────────────────
        self._bowyer_watson()

    # ───────────────────────── Bowyer–Watson fallback ­──────────────
    def _bowyer_watson(self):
        try:
            from numba import njit
        except ModuleNotFoundError:
            njit = lambda f: f

        @njit
        def in_circle(px, py, ax, ay, bx, by, cx, cy):
            ax -= px; ay -= py
            bx -= px; by -= py
            cx -= px; cy -= py
            det = (ax*ax+ay*ay)*(bx*cy-cx*by) \
                - (bx*bx+by*by)*(ax*cy-cx*ay) \
                + (cx*cx+cy*cy)*(ax*by-bx*ay)
            return det > 0.0

        pts = self.points
        xmin = min(p.x for p in pts); xmax = max(p.x for p in pts)
        ymin = min(p.y for p in pts); ymax = max(p.y for p in pts)
        d = max(xmax - xmin, ymax - ymin) * 10
        p1 = Point2D(xmin - d, ymin - d, 0)
        p2 = Point2D(xmax + d, ymin - d, 0)
        p3 = Point2D((xmin + xmax) / 2, ymax + d, 0)

        tris = [(p1, p2, p3)]
        for p in pts:
            bad = [t for t in tris if in_circle(
                p.x, p.y, t[0].x, t[0].y, t[1].x, t[1].y, t[2].x, t[2].y)]
            boundary = []
            for t in bad:
                for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                    rev = (e[1], e[0])
                    if rev in boundary:
                        boundary.remove(rev)
                    else:
                        boundary.append(e)
            for t in bad:
                tris.remove(t)
            for e in boundary:
                tris.append((e[0], e[1], p))

        self.triangles = [
            Triangle(a, b, c) for (a, b, c) in tris
            if p1 not in (a, b, c) and p2 not in (a, b, c) and p3 not in (a, b, c)
        ]

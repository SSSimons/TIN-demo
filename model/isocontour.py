from __future__ import annotations
from typing import List, Tuple, Dict
from collections import defaultdict

from geometry import Point2D, Triangle, Polyline


class IsoContourGenerator:
    # Marching Triangles: генерирует изолинии фиксированного шага Δh по списку треугольников.

    def __init__(self, triangles: List[Triangle]):
        self._tris = triangles

    def generate(self, step: float) -> List[Polyline]:
        if not self._tris:
            return []

        z_min = min(v.z for tri in self._tris for v in tri)
        z_max = max(v.z for tri in self._tris for v in tri)
        if abs(z_max - z_min) < 1e-6:
            return []
        levels = [z_min + k * step for k in range(int((z_max - z_min) / step) + 1)]
        isolines: list[Polyline] = []

        for h in levels:
            segs: list[Tuple[Point2D, Point2D]] = []

            # 1) режем все треугольники
            for tri in self._tris:
                pts = self._slice_triangle(tri, h)
                if len(pts) == 2:
                    segs.append(tuple(pts))

            # 2) склеиваем отрезки в полилинии
            isolines.extend(self._stitch_segments(segs, h))

        return isolines

    
    @staticmethod
    def _slice_triangle(tri: Triangle, h: float) -> List[Point2D]:
        # Пересекаем треугольник плоскостью z=h → 0-2 точки.
        pts = []
        edges = [(tri.a, tri.b), (tri.b, tri.c), (tri.c, tri.a)]

        for p, q in edges:
            dz1 = p.z - h
            dz2 = q.z - h
            if dz1 == 0.0:
                pts.append(p)
            if dz2 == 0.0:
                pts.append(q)
            if dz1 * dz2 < 0.0:            # разные знаки → есть пересечение
                k = dz1 / (dz1 - dz2)
                pts.append(Point2D(p.x + k * (q.x - p.x),
                                   p.y + k * (q.y - p.y),
                                   h))
        # уникализируем
        return list({(pt.x, pt.y): pt for pt in pts}.values())

    
    @staticmethod
    def _stitch_segments(segs: List[Tuple[Point2D, Point2D]], elev: float) -> List[Polyline]:
        # Превращаем набор (p,q) в непрерывные Polyline'ы
        if not segs:
            return []

        # карта точка→список (индекс сегмента, pos 0/1)
        index: Dict[Tuple[float, float], List[Tuple[int, int]]] = defaultdict(list)
        for idx, (p, q) in enumerate(segs):
            index[(p.x, p.y)].append((idx, 0))
            index[(q.x, q.y)].append((idx, 1))

        visited = [False] * len(segs)
        polylines: list[Polyline] = []

        for i, (p_start, q_start) in enumerate(segs):
            if visited[i]:
                continue

            chain = [p_start, q_start]
            visited[i] = True
            cur = q_start

            # расширяем «вперёд»
            while True:
                neighbours = [e for e in index[(cur.x, cur.y)] if not visited[e[0]]]
                if not neighbours:
                    break
                seg_idx, end_flag = neighbours[0]
                visited[seg_idx] = True
                p, q = segs[seg_idx]
                nxt = q if end_flag == 0 else p      # берём другой конец
                chain.append(nxt)
                cur = nxt

            polylines.append(Polyline(chain, elev))

        return polylines

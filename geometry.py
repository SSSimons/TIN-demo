from __future__ import annotations
from dataclasses import dataclass
from typing import List
from PyQt6.QtGui import QPolygonF
from PyQt6.QtCore import QPointF

@dataclass(frozen=True, slots=True)
class Point2D:
    x: float
    y: float
    z: float = 0.0          # высота по умолчанию

    def to_qpoint(self) -> QPointF:
        return QPointF(self.x, self.y)

@dataclass(slots=True)
class Triangle:
    a: Point2D
    b: Point2D
    c: Point2D

    # быстрый доступ к координатам (экономим на namedtuple)
    __iter__ = lambda self: iter((self.a, self.b, self.c))

    # MapCanvas берёт QPolygonF для отрисовки
    def qpoly(self) -> QPolygonF:
        return QPolygonF([self.a.to_qpoint(),
                          self.b.to_qpoint(),
                          self.c.to_qpoint()])

@dataclass(slots=True)
class Polyline:
    pts: List[Point2D]
    elev: float = 0.0

    def __iter__(self):          # поддержка for-in
        return iter(self.pts)

    def qpoly(self) -> QPolygonF:
        return QPolygonF([p.to_qpoint() for p in self.pts])

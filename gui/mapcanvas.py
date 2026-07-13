from __future__ import annotations
from typing import List, Optional

from PyQt6.QtCore    import Qt, QPointF, pyqtSignal, QRectF
from PyQt6.QtGui     import QPainter, QPolygonF, QPen, QColor, QTransform
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

from geometry           import Point2D, Polyline
from model.baryinterpol import barycentric, height as interp_height


class MapCanvas(QOpenGLWidget):
    polylineFinished = pyqtSignal(Polyline)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw:        List[Polyline]   = []
        self._triangles:  List             = []
        self._isolines:   List[Polyline]   = []
        self._triangulator = None

        self._draw_active  = False
        self._current_pts: List[Point2D]   = []

        self._xf = QTransform()       # world → screen
        self.setMouseTracking(True)   # чтобы ловить mouseMoveEvent

        # последнее значение Z при наведении
        self._hover_z: Optional[float] = None

    def wheelEvent(self, ev):
        """
        Зум при вращении колеса мыши:
         • ctrl-free: масштабируем относительно точки курсора
         • вверх — увеличить, вниз — уменьшить
        """
        # Получаем, сколько «щелчков» колеса: обычно 120 единиц за щелчок
        delta = ev.angleDelta().y()
        if delta == 0:
            return

        # во сколько раз зумим: 1.2^(кол-во щелчков)
        # если вращаем вниз (delta<0), factor<1 — «зум-выход»
        steps = delta / 120
        factor = 1.2 ** steps

        # Позиция курсора в экранных (пиксельных) координатах
        pt_screen = ev.position()
        # Переводим её в «мировые» по текущей матрице
        inv, ok = self._xf.inverted()
        if not ok:
            return
        pt_world = inv.map(pt_screen)

        # Составляем новый трансформ:
        # 1) переносим так, чтобы центр зума — pt_world (в мир.коорд)
        # 2) шкалируем
        # 3) возвращаем обратно
        self._xf.translate(pt_world.x(), pt_world.y())
        self._xf.scale(factor, factor)
        self._xf.translate(-pt_world.x(), -pt_world.y())

        # Перерисовываем всё
        self.update()


    def draw_raw_lines(self, lines: List[Polyline]):
        self._triangulator = None
        self._raw = lines
        self._recalc_transform(lines)
        self.update()

    def set_tin(self, triangulator):
        self._triangulator = triangulator
        self._triangles    = triangulator.triangles
        tris = [Polyline([t.a, t.b, t.c], 0) for t in self._triangles]
        self._recalc_transform(tris)
        self.update()

    def set_isolines(self, isolines: List[Polyline]):
        self._isolines = isolines
        self.update()

    def start_drawing(self):
        self._draw_active  = True
        self._current_pts = []

    def stop_drawing(self):
        self._draw_active  = False
        self._current_pts = []
        self.update()

    def mousePressEvent(self, ev):
        if self._draw_active and ev.button() == Qt.MouseButton.LeftButton:
            world = self._xf.inverted()[0].map(ev.position())
            self._current_pts.append(Point2D(world.x(), world.y(), 0))
            self.update()

    def mouseDoubleClickEvent(self, ev):
        if self._draw_active and len(self._current_pts) >= 2:
            pl = Polyline(self._current_pts.copy(), 0.0)
            self.polylineFinished.emit(pl)
            self.stop_drawing()

    def mouseMoveEvent(self, ev):
        # сброс
        self._hover_z = None
        if self._triangulator:
            world = self._xf.inverted()[0].map(ev.position())
            p = Point2D(world.x(), world.y(), 0.0)
            for t in self._triangulator.triangles:
                l1, l2, l3 = barycentric(p, t)
                if l1 >= 0 and l2 >= 0 and l3 >= 0:
                    self._hover_z = interp_height(p, t)
                    break
        self.update()
        super().mouseMoveEvent(ev)

    def paintEvent(self, ev):
        # 1) Рисуем всё через QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # фон
        p.fillRect(self.rect(), Qt.GlobalColor.white)

        # world transform
        p.setWorldTransform(self._xf)

        # raw
        pen_raw = QPen(Qt.GlobalColor.black, 0); p.setPen(pen_raw)
        for pl in self._raw:
            p.drawPolyline(_qpoly(pl))

        # TIN
        if self._triangles:
            pen_t = QPen(QColor(140, 140, 140, 160), 0); p.setPen(pen_t)
            for t in self._triangles:
                p.drawPolygon(_qpoly([t.a, t.b, t.c]))

        # isolines
        if self._isolines:
            pen_i = QPen(Qt.GlobalColor.blue, 0); p.setPen(pen_i)
            for pl in self._isolines:
                p.drawPolyline(_qpoly(pl))

        # текущая линия
        if self._current_pts:
            pen_c = QPen(Qt.GlobalColor.red, 0); p.setPen(pen_c)
            p.drawPolyline(_qpoly(self._current_pts))

        # 2) Оверлей высоты в экранных координатах
        if self._hover_z is not None:
            p.resetTransform()
            txt = f"Высота: {self._hover_z:.2f} м"
            fm = p.fontMetrics()
            w = fm.horizontalAdvance(txt) + 6
            h = fm.height() + 4
            rect = QRectF(5, self.height() - h - 5, w, h)
            p.fillRect(rect, QColor(255, 255, 255, 200))
            p.setPen(Qt.GlobalColor.black)
            p.drawText(rect.adjusted(3, 2, 0, 0), txt)

        p.end()

    def _recalc_transform(self, lines: List[Polyline]):
        if not lines:
            self._xf = QTransform()
            return
        xs = [pt.x for pl in lines for pt in pl.pts]
        ys = [pt.y for pl in lines for pt in pl.pts]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        bbox = QRectF(xmin, ymin, xmax - xmin, ymax - ymin)
        if bbox.width() == 0 or bbox.height() == 0:
            self._xf = QTransform()
            return
        vw, vh = self.width(), self.height()
        scale = 0.9 * min(vw / bbox.width(), vh / bbox.height())
        self._xf = (
            QTransform()
            .translate(vw / 2, vh / 2)
            .scale(scale, -scale)
            .translate(-(xmin + xmax) / 2, -(ymin + ymax) / 2)
        )


def _qpoly(pl: Polyline | List[Point2D]) -> QPolygonF:
    pts = pl.pts if isinstance(pl, Polyline) else pl
    return QPolygonF([QPointF(p.x, p.y) for p in pts])
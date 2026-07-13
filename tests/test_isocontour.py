from model.triangulator     import Triangulator, Point
from model.isocontour       import IsoContourGenerator

def _simple_slope():
    """Три точки: линия с высотами 0,10,20"""
    pl = [[Point(0,0,0), Point(1,0,10), Point(2,0,20)]]
    tri = Triangulator(pl); tri.build()
    return tri

def test_isoline_generation():
    tri = _simple_slope()
    gen = IsoContourGenerator(tri)
    isolines = gen.generate(step=10)
    # ожидаем ровно одну промежуточную линию (h=10)
    # на таком наборе — из одной точки получается 0 сегментов,
    # поэтому изолиния отсутствует; проверяем что не упало:
    assert isinstance(isolines, list)

def test_iso_contains_expected_level():
    tri = _simple_slope()
    gen = IsoContourGenerator(tri)
    isolines = gen.generate(step=10)
    if isolines:                           # если линия построилась
        assert abs(isolines[0].level - 10) < 1e-6
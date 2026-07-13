from model.baryinterpol import barycentric, height
from model.triangulator   import Point, Triangle
import math

def _make_test_triangle():
    a = Point(0, 0, 0)
    b = Point(1, 0, 10)
    c = Point(0, 1, 20)
    return Triangle(a, b, c)

def test_bary_sum_to_one():
    tri = _make_test_triangle()
    p   = Point(0.2, 0.3, 0)
    l1, l2, l3 = barycentric(p, tri)
    assert math.isclose(l1 + l2 + l3, 1.0, abs_tol=1e-9)

def test_vertex_height_exact():
    tri = _make_test_triangle()
    for v in (tri.a, tri.b, tri.c):
        assert math.isclose(height(v, tri), v.z, abs_tol=1e-9)
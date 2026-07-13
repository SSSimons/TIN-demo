import math
import pytest
from model.triangulator import Triangulator, Point

# ---- вспомогательные функции ----
def make_square_polylines(z=0.0):
    """Изолиния-квадрат 0,0–1,1 (4 сегмента)."""
    pts = [
        Point(0, 0, z), Point(1, 0, z),
        Point(1, 1, z), Point(0, 1, z),
        Point(0, 0, z)
    ]
    return [pts]                    # список полилиний

# ---- фикстуры --------------------
@pytest.fixture(scope="session")
def square_tin():
    """Triangulator, построенный по квадрату 1×1."""
    tri = Triangulator(make_square_polylines())
    tri.build()
    return tri
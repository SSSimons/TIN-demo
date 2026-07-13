def test_triangle_count(square_tin):
    """
    Квадрат из четырёх точек должен делиться
    на 2 Delaunay-треугольника.
    """
    assert len(square_tin.triangles) == 2

def test_no_duplicate_vertices(square_tin):
    all_pts = [v for t in square_tin for v in t]
    # уникальные объекты (по id)
    assert len(all_pts) == len({id(p) for p in all_pts})
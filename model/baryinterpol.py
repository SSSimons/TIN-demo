def barycentric(p, t):
    det = ((t.b.y - t.c.y)*(t.a.x - t.c.x) +
           (t.c.x - t.b.x)*(t.a.y - t.c.y))
    l1 = ((t.b.y - t.c.y)*(p.x - t.c.x) +
          (t.c.x - t.b.x)*(p.y - t.c.y)) / det
    l2 = ((t.c.y - t.a.y)*(p.x - t.c.x) +
          (t.a.x - t.c.x)*(p.y - t.c.y)) / det
    l3 = 1.0 - l1 - l2
    return l1, l2, l3

def height(p, tri):
    l1, l2, l3 = barycentric(p, tri)
    return l1*tri.a.z + l2*tri.b.z + l3*tri.c.z
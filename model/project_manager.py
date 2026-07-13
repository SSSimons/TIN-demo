from __future__ import annotations
from pathlib import Path
import json
from typing import List, Any

from geometry import Point2D, Polyline


class ProjectManager:
    """
    Очень простой *.mapproj-формат:
        {
          "raw"   : [ [[x,y], ...], ... ],
          "elevs" : [z1, z2, ...],          # для raw-линий
          "tin"   : { "points": [[x,y,z],...],
                      "tri"   : [[i,j,k], ...] }
        }
    """

    # Сохранение
    @staticmethod
    def save(fname: str | Path,
             raw  : List[Polyline] | None,
             tri  : Any | None):
        data = {}

        if raw:
            data["raw"]   = [[[p.x, p.y] for p in pl] for pl in raw]
            data["elevs"] = [pl.elev for pl in raw]

        if tri and getattr(tri, "triangles", None):
            pts = tri.points
            idx = {id(p): i for i, p in enumerate(pts)}
            data["tin"] = {
                "points": [[p.x, p.y, p.z] for p in pts],
                "tri"   : [[idx[id(t.a)], idx[id(t.b)], idx[id(t.c)]]
                           for t in tri.triangles]
            }

        Path(fname).write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Загрузка
    @staticmethod
    def load(fname: str | Path):
        from model.triangulator import Triangulator

        obj = json.loads(Path(fname).read_text(encoding="utf-8"))
        raw: list[Polyline] = []
        for coords, z in zip(obj["raw"], obj["elevs"]):
            pts = [Point2D(x, y, z) for x, y in coords]
            if len(pts) >= 2:
                raw.append(Polyline(pts, z))


        if "tin" not in obj:
            return raw, None

        pts = [Point2D(x, y, z) for x, y, z in obj["tin"]["points"]]
        tri = Triangulator([])
        tri.points = pts
        tri.triangles = [
            Triangulator.Triangle(pts[i], pts[j], pts[k])
            for i, j, k in obj["tin"]["tri"]
        ]
        return raw, tri

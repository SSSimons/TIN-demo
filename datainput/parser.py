"""
tin_demo/datainput/parser.py

Импорт / экспорт векторных слоёв (DXF, SHP, GeoJSON, NDJSON, .gz, .zip)
с поддержкой Polygon → boundary, MultiLineString.geoms, orjson, ijson.
"""

from __future__ import annotations

from pathlib import Path
from typing  import List, Iterable, Optional
import json, gzip, io, zipfile

import ezdxf
import ijson
from geometry import Point2D, Polyline
from shapely.geometry import shape, LineString

try:
    import orjson  # быстрее, если установлен
except ModuleNotFoundError:
    orjson = None  # type: ignore

__all__ = ["read_vector", "save_as_geojson"]


def read_vector(path: str | Path, *, as_polyline: bool = False):
    """
    Читает файл и возвращает list[list[Point2D]].
    Если as_polyline=True — возвращает list[Polyline].
    Поддерживаются: .dxf, .shp, .geojson/.json/.gz/.zip.
    """
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".dxf":
        lines = _read_dxf(p)
    elif ext == ".shp":
        lines = _read_shp(p)
    else:
        lines = _read_geo(p)

    if as_polyline:
        return [Polyline(pts, pts[0].z if pts else 0.0) for pts in lines]
    return lines


def _read_dxf(p: Path) -> List[List[Point2D]]:
    doc = ezdxf.readfile(str(p))
    msp = doc.modelspace()
    out: List[List[Point2D]] = []
    for e in msp.query("LWPOLYLINE"):
        z = float(e.dxf.elevation or 0.0)
        pts = [Point2D(v.dxf.x, v.dxf.y, z) for v in e]
        if len(pts) >= 2:
            out.append(pts)
    return out


def _read_shp(p: Path) -> List[List[Point2D]]:
    # Попытка через Fiona
    try:
        import fiona
        out: List[List[Point2D]] = []
        with fiona.open(str(p)) as src:
            for feat in src:
                _add_feat(feat, out)
        return out
    except Exception:
        pass

    # Фоллбэк через pyshp
    try:
        import shapefile
        sf = shapefile.Reader(str(p))
        fields = [f[0] for f in sf.fields[1:]]
        idx_elev = _find_elev_field(fields)

        out: List[List[Point2D]] = []
        for sr in sf.iterShapeRecords():
            shp = sr.shape
            # PolyLine, PolyLineZ, Polygon, PolygonZ
            if shp.shapeType not in (3, 13, 5, 15):
                continue

            elev_attr = _safe_float(sr.record[idx_elev]) if idx_elev is not None else 0.0
            z_arr = shp.z if shp.shapeType in (13, 15) else None

            parts = list(shp.parts) + [len(shp.points)]
            for i in range(len(parts) - 1):
                segment = shp.points[parts[i] : parts[i + 1]]
                pts = [
                    Point2D(x, y, (z_arr[parts[i] + j] if z_arr else elev_attr))
                    for j, (x, y) in enumerate(segment)
                ]
                if len(pts) >= 2:
                    out.append(pts)
        return out
    except Exception as e:
        raise RuntimeError(f"SHP read error: {e}") from e


def _find_elev_field(names: List[str]) -> Optional[int]:
    for i, n in enumerate(names):
        if n.upper() in {"ELEV", "ELEV_M", "ELEVATION", "Z", "CONTOUR"}:
            return i
    return None


def _safe_float(v) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _read_geo(p: Path) -> List[List[Point2D]]:
    raw = _read_bytes(p)
    obj = _try_parse(raw)
    out: List[List[Point2D]] = []

    if obj is not None:
        # Полноценный GeoJSON
        feats = obj.get("features", [obj])
        for feat in feats:
            _add_feat(feat, out)
        return out

    # NDJSON или streaming GeoJSON
    buf = io.BytesIO(raw)
    for feat in ijson.items(buf, "features.item"):
        _add_feat(feat, out)
    buf.seek(0)
    for feat in ijson.items(buf, "item"):
        _add_feat(feat, out)

    if not out:
        raise ValueError(f"{p.name} невалидный формат GeoJSON/NDJSON")

    return out


def _read_bytes(p: Path) -> bytes:
    if p.suffix.lower() == ".gz":
        with gzip.open(p, "rb") as f:
            return f.read()
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as zf:
            inner = next(
                name
                for name in zf.namelist()
                if name.lower().endswith((".json", ".geojson"))
            )
            with zf.open(inner) as f:
                return f.read()
    return p.read_bytes()


def _try_parse(buf: bytes) -> Optional[dict]:
    b = buf.lstrip(b"\xef\xbb\xbf")
    if orjson:
        try:
            return orjson.loads(b)  # type: ignore
        except Exception:
            pass
    try:
        return json.loads(b.decode("utf-8"))
    except Exception:
        return None


def _add_feat(feat: dict, out: List[List[Point2D]]) -> None:
    props = feat.get("properties") or {}
    elev = _pick_elev(props)
    geom = feat.get("geometry") or {}
    gtype = geom.get("type")

    # LineString / MultiLineString
    if gtype in ("LineString", "MultiLineString"):
        coords_list = (
            [geom["coordinates"]]
            if gtype == "LineString"
            else geom["coordinates"]
        )

    # Polygon / MultiPolygon → boundary → линии
    elif gtype in ("Polygon", "MultiPolygon"):
        boundary = shape(geom).boundary  # LineString или MultiLineString
        if isinstance(boundary, LineString):
            coords_list = [list(boundary.coords)]
        else:
            # Shapely ≥2.0: boundary.geoms — коллекция LineString
            iter_ls = getattr(boundary, "geoms", boundary)
            coords_list = [list(ls.coords) for ls in iter_ls]

    else:
        return  # другие типы пропускаем

    # Конвертация координат в Point2D
    for coords in coords_list:
        pts = [
            Point2D(x, y, (c[2] if len(c) == 3 else elev))
            for x, y, *c in coords
        ]
        if len(pts) >= 2:
            out.append(pts)


def _pick_elev(pr: dict) -> float:
    for key in ("elev", "ELEV_FT", "ELEV_M", "ELEVATION", "Z", "Contour"):
        if key in pr and pr[key] not in (None, ""):
            try:
                return float(pr[key])
            except Exception:
                pass
    return 0.0


def save_as_geojson(
    lines: Iterable[Polyline | List[Point2D]], out_path: str | Path
) -> None:
    feats = []
    for ln in lines:
        if isinstance(ln, Polyline):
            z = ln.elev
            coords = [[p.x, p.y] for p in ln]
        else:
            z = ln[0].z if ln else 0.0
            coords = [[p.x, p.y] for p in ln]
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {"elev": z},
            }
        )

    fc = {"type": "FeatureCollection", "features": feats}
    Path(out_path).write_text(
        json.dumps(fc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
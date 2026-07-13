from __future__ import annotations
from pathlib import Path
from typing import Iterable, Generator
import io, gzip, json, zipfile, ijson
from geometry import Point2D, Polyline
try:
    import orjson              # быстрее json
except ModuleNotFoundError:
    orjson = None              # type: ignore

def stream_polylines(path: str | Path) -> Iterable[Polyline]:
    path = Path(path)
    raw = _read_raw(path)

    obj = _try_whole(raw)
    if obj is not None:
        yield from _root_to_poly(obj)
        return

    buf = io.BytesIO(raw)
    for feat in ijson.items(buf, 'features.item'):
        yield _feat_to_pl(feat)
    buf.seek(0)
    for feat in ijson.items(buf, 'item'):
        yield _feat_to_pl(feat)

# помощник
def _read_raw(p: Path) -> bytes:
    if p.suffix.lower() == '.gz':
        with gzip.open(p, 'rb') as f: return f.read()
    if p.suffix.lower() == '.zip':
        with zipfile.ZipFile(p) as z:
            inner = next(n for n in z.namelist()
                         if n.lower().endswith(('.json', '.geojson')))
            with z.open(inner) as f: return f.read()
    return p.read_bytes()

def _try_whole(raw: bytes):
    b = raw.lstrip(b'\xef\xbb\xbf')
    if orjson:
        try: return orjson.loads(b)        
        except orjson.JSONDecodeError:     
            pass
    try: return json.loads(b.decode('utf-8'))
    except json.JSONDecodeError: return None

def _root_to_poly(root) -> Generator[Polyline, None, None]:
    feats = root['features'] if 'features' in root else [root]
    for f in feats: yield _feat_to_pl(f)

def _feat_to_pl(feat) -> Polyline:
    props = feat.get('properties') or {}
    elev  = _pick(props)
    geom  = feat['geometry']; gtype = geom['type']

    if gtype in ('LineString', 'MultiLineString'):
        lines = [geom['coordinates']] if gtype=='LineString' else geom['coordinates']
    elif gtype in ('Polygon', 'MultiPolygon'):
        from shapely.geometry import shape, LineString, MultiLineString
        ml = shape(geom).boundary
        lines = [list(ml.coords)] if isinstance(ml, LineString) else \
                [list(ls.coords) for ls in ml]
    else:
        return Polyline([], elev)

    coords = lines[0]
    pts = [Point2D(x, y, (c[2] if len(c)==3 else elev)) for x, y, *c in coords]
    return Polyline(pts, elev)

def _pick(p: dict) -> float:
    for k in ('elev','ELEV_FT','ELEV_M','ELEVATION','Z','Contour'):
        if k in p and p[k] not in (None,''):
            try: return float(p[k])
            except: pass
    return 0.0

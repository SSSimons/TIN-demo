from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from datainput.parser import read_vector
from datainput.geojson_stream import stream_polylines
from model.triangulator import Triangulator

class Loader(QObject):
    finished = pyqtSignal(object)    # Triangulator | List[Polyline] | None
    error    = pyqtSignal(str)

    def __init__(self, path: str | Path):
        super().__init__()
        self._path = Path(path)

    def run(self):
        try:
            if self._path.suffix.lower() in {".geojson", ".json", ".gz", ".zip"}:
                lines = list(stream_polylines(self._path))
            else:
                lines = read_vector(self._path, as_polyline=True)

            if not lines:
                self.error.emit("Файл не содержит геометрии")
                self.finished.emit(None)
                return

            # нет высот → ничего не строим, отдаём сырые линии
            if all(p.z == 0 for pl in lines for p in pl):
                self.finished.emit(lines)
                return

            tri = Triangulator(lines)
            tri.build()
            self.finished.emit(tri)

        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(None)

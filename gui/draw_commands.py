from PyQt6.QtGui import QUndoCommand
from geometry import Polyline


class AddPolylineCmd(QUndoCommand):
    def __init__(self, target_list: list[Polyline], pl: Polyline):
        super().__init__("Добавить изолинию")
        self._lst = target_list
        self._pl  = pl

    def undo(self):
        if self._pl in self._lst:
            self._lst.remove(self._pl)

    def redo(self):
        if self._pl not in self._lst:
            self._lst.append(self._pl)
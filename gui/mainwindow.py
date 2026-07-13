from __future__ import annotations

import os
from typing  import Optional

from PyQt6.QtCore    import QThread, pyqtSlot, QUrl, Qt
from PyQt6.QtGui     import QAction, QIcon, QDesktopServices, QUndoStack, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QFileDialog, QMenuBar, QStatusBar,
    QMessageBox
)
from model.project_manager import ProjectManager
from .mapcanvas       import MapCanvas
from .loader          import Loader
from .draw_commands   import AddPolylineCmd
from model.isocontour import IsoContourGenerator
from model.project_manager import ProjectManager
from geometry import Polyline


# ────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    """Главное окно TIN-Demo."""

    # ────────────────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TIN-Demo")
        self.resize(1280, 720)

        # центральный виджет
        self.canvas = MapCanvas(self)
        self.setCentralWidget(self.canvas)
        
         # Undo/Redo-стек
        self.undo_stack = QUndoStack(self)

        # Ctrl+Z → Undo
        undo_sc = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
        undo_sc.activated.connect(self.undo_stack.undo)

        # Ctrl+Shift+Z → Redo
        redo_sc1 = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        redo_sc1.setContext(Qt.ShortcutContext.ApplicationShortcut)
        redo_sc1.activated.connect(self.undo_stack.redo)

        # Ctrl+Y → Redo (Windows-стиль)
        redo_sc2 = QShortcut(QKeySequence("Ctrl+Y"), self)
        redo_sc2.setContext(Qt.ShortcutContext.ApplicationShortcut)
        redo_sc2.activated.connect(self.undo_stack.redo)

        # UI статус-бара
        self._create_actions()
        self._create_menu()
        self.status = QStatusBar(); self.setStatusBar(self.status)

        # undo-стек

        # worker / thread держим как поля, чтобы GC не удалил
        self.worker_thread: Optional[QThread] = None
        self.loader       : Optional[Loader]  = None

        # сигнал: готова нарисованная изолиния
        self.canvas.polylineFinished.connect(self._add_drawn_polyline)

    # ─────────────────────────────  ACTIONS  ────────────────────────
    def _create_actions(self):
        # * QAction должен иметь уникальный objectName, если нужны стили
        icon_open = QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), 'icons', "open.svg")))
        icon_save = QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), 'icons', "save.svg")))
        icon_draw = QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), 'icons', "pencil.svg")))
        icon_help  = QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), 'icons', "help.svg")))
        
        # Открыть
        self.actionOpen = QAction(icon_open, "Открыть…", self)
        self.actionOpen.setShortcut("Ctrl+O")
        self.actionOpen.triggered.connect(self.open_file)

        # Сохранить
        self.actionSave = QAction(icon_save, "Сохранить проект…", self)
        self.actionSave.setShortcut("Ctrl+S")
        self.actionSave.triggered.connect(self.save_project)

        # Рисовать изолинию
        self.actionDraw = QAction(icon_draw, "Рисовать изолинию", self)
        self.actionDraw.setShortcut("Ctrl+D")
        self.actionDraw.setCheckable(True)
        self.actionDraw.triggered.connect(self.enter_draw_mode)

        # Справка
        self.actionHelp = QAction(icon_help, "Справка", self)
        self.actionHelp.setShortcut("F1")
        self.actionHelp.triggered.connect(self.show_help)

    def _create_menu(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        menu_file = menubar.addMenu("Файл")        # вернёт QMenu
        menu_file.addAction(self.actionOpen)       # ✔
        menu_file.addAction(self.actionSave)

        menu_edit = menubar.addMenu("Правка")
        menu_edit.addAction(self.actionDraw)
        menu_edit.addSeparator()
        undo_act = self.undo_stack.createUndoAction(self, "Отменить")
        undo_act.setShortcut(QKeySequence("Ctrl+Z"))
        redo_act = self.undo_stack.createRedoAction(self, "Повторить")
        redo_act.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence("Ctrl+Y")])
        menu_edit.addAction(undo_act)
        menu_edit.addAction(redo_act)

        menu_help = menubar.addMenu("Помощь")
        menu_help.addAction(self.actionHelp)
        

    # ─────────────────────────────  OPEN  ───────────────────────────
    def open_file(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Открыть файл", "",
            "Проект (*.mapproj);;Векторы (*.geojson *.json *.gz *.zip *.shp *.dxf);;Все файлы (*)"
        )
        if not fname:
            return
        if fname.lower().endswith(".mapproj"):
            try:
                raw, tri = ProjectManager.load(fname)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка открытия .mapproj", str(e))
                return

            # показываем «сырые» линии
            if raw:
                self.canvas.draw_raw_lines(raw)
                self.status.showMessage(f"Загружено {len(raw)} сырых линий", 4000)

            # если есть TIN — показываем его и изолинии
            if tri is not None:
                self.canvas.set_tin(tri)
                isolines = IsoContourGenerator(tri.triangles).generate(step=10)
                self.canvas.set_isolines(isolines)
                self.status.showMessage(
                    f"Проект: точки {len(tri.points)}, треугольники {len(tri.triangles)}",
                    4000
                )
            return
        self.status.showMessage("Импорт…")

        # поток + воркер
        self.worker_thread = QThread(self)
        self.loader = Loader(fname)
        self.loader.moveToThread(self.worker_thread)

        # сигналы
        self.worker_thread.started.connect(self.loader.run)
        self.loader.finished.connect(self._on_loaded)
        self.loader.error.connect(self._on_error)

        self.loader.finished.connect(self.worker_thread.quit)
        self.loader.finished.connect(self.loader.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    # Загрузка результатов
    @pyqtSlot(object)
    def _on_loaded(self, payload):
        """payload = list[Polyline]   (нет высот)  ─ или ─  Triangulator."""
        self.status.clearMessage()

        # 1) просто линии без высоты
        if isinstance(payload, list):
            self.canvas.draw_raw_lines(payload)
            self.status.showMessage(f"Показано {len(payload)} линий (без высот)", 5000)
            return

        # 2) полноценный TIN
        tri = payload
        self.canvas.set_tin(tri)

        isolines = IsoContourGenerator(tri.triangles).generate(step=10)
        self.canvas.set_isolines(isolines)

        self.status.showMessage(
            f"Импорт: точек {len(tri.points)}, треугольников {len(tri.triangles)}",
            5000
        )

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self.status.clearMessage()
        QMessageBox.critical(self, "Импорт", msg)

    # Сохранение
    def save_project(self):
        fname, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект", "", "TIN-Demo (*.mapproj)"
        )
        if not fname:
            return
        try:
            ProjectManager.save(
                fname,
                getattr(self.canvas, "_raw", None),
                getattr(self.canvas, "_triangles", None)
            )
            self.status.showMessage("Проект сохранён", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Сохранение", str(e))

    # Рисование
    def enter_draw_mode(self, checked: bool):
        if checked:
            self.canvas.start_drawing()
            self.status.showMessage(
                "Режим рисования: кликайте узлы, двойной щелчок — завершить", 4000
            )
        else:
            self.canvas.stop_drawing()
            self.status.showMessage("Режим рисования выключен", 2000)

    def _add_drawn_polyline(self, pl: Polyline):
        """Принимаем готовую линию от Canvas и кладём в Undo-стек."""
        if not hasattr(self.canvas, "_raw"):
            self.canvas._raw = []
        cmd = AddPolylineCmd(self.canvas._raw, pl)
        self.undo_stack.push(cmd)
        self.canvas.update()

    # Помощь
    def show_help(self):
        try:
            help_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "help" , "html" , "index.html"))
            help_path = help_path.replace('\\gui', '')
            QDesktopServices.openUrl(QUrl.fromLocalFile(help_path))
        except Exception:
            self.statusBar().showMessage("Справка не найдена", 3000)

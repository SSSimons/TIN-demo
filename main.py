from pathlib import Path
from PyQt6.QtWidgets import QApplication
from gui.mainwindow import MainWindow

# задать bbox: xmin, ymin, xmax, ymax
def run():
    app = QApplication([])
    app.setApplicationName("TIN-Demo")
    app.setOrganizationName("СПБГУТ")
    mw = MainWindow()
    mw.show()
    # подключаем справку
    help_collector = str(Path(__file__).parent / "help" / "tin_help.qhc")
    if Path(help_collector).exists():
        app.setHelpEngine(help_collector)
    app.exec()

if __name__ == "__main__":
    run()
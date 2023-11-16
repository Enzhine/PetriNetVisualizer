from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu, QMenuBar, QFileDialog, QStackedWidget, \
    QGraphicsScene, QGraphicsView, QLabel
import pm4py
import sys
from utils.PNVUtils import PNVMessageBoxes, PNVDrawer


class PNVMainWindow(QMainWindow):
    def __init__(self):
        super(PNVMainWindow, self).__init__()
        self.menu_bar: QMenuBar = None
        self.stacked_widget: QStackedWidget = None
        self.graph_view: QGraphicsView = None
        self.graph_scene: QGraphicsScene = None
        self.window_icon = QtGui.QIcon('src/PNV_icon.png')

        self.setWindowIcon(self.window_icon)
        self.setWindowTitle("Petri Net Visualizer")
        self.setMinimumSize(768, 512)
        self.create_menu_bar()
        self.create_stacked_wid()

        self.file_dialog = QFileDialog(self)
        self.file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        self.file_dialog.setNameFilter("Petri-net file (*.pnml)")

    def create_stacked_wid(self):
        self.stacked_widget = QStackedWidget(self)

        hello_lbl = QLabel("Petri Net Visualizer - приложение для визуализации сетей Петри")

        self.graph_scene = QGraphicsScene(self)
        self.graph_view = QGraphicsView(self.graph_scene)

        self.stacked_widget.addWidget(hello_lbl)
        self.stacked_widget.addWidget(self.graph_view)
        self.setCentralWidget(self.stacked_widget)

    def create_menu_bar(self):
        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)

        file_menu = QMenu("&Файл", self)
        self.menu_bar.addMenu(file_menu)

        open_file = file_menu.addAction("&Открыть...", self.open_pnml)

    def get_file_path(self):
        if self.file_dialog.exec():
            files = self.file_dialog.selectedFiles()
            if files:
                return files[0]
            return None

    def load_pnml(self, path: str):
        pn = None
        try:
            pn, im, fm = pm4py.read_pnml(path)
            if all(len(t) == 0 for t in [pn.places, pn.transitions]):
                PNVMessageBoxes.warning_msg("Загружена пустая сеть!",
                                            icon=self.window_icon).exec()
                return
            if len(pn.arcs) == 0:
                PNVMessageBoxes.warning_msg("Невозможно отобразить бессвязную сеть!",
                                            icon=self.window_icon).exec()
                return
        except Exception as ex:
            PNVMessageBoxes.warning_msg("Возникла ошибка при открытии файла!",
                                        inf_text=f"{ex.__class__.__name__}: {ex}",
                                        icon=self.window_icon).exec()
        if pn:
            self.stacked_widget.setCurrentIndex(1)
            drawer = PNVDrawer(self.graph_scene, pn)
            drawer.draw_petri_net()

    @QtCore.pyqtSlot()
    def open_pnml(self):
        path = self.get_file_path()
        if path:
            self.load_pnml(path)


def application():
    app = QApplication(sys.argv)
    main_window = PNVMainWindow()

    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    application()

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu, QMenuBar, QFileDialog, QStackedWidget, \
    QGraphicsScene, QGraphicsView, QLabel, QTabWidget
import pm4py
import sys
import os
from utils.PNVUtils import PNVMessageBoxes, PNVDrawer, PNVViewer


class GraphData:
    def __init__(self, path: str, exact_pn: tuple["PetriNet", "Marking", "Marking"], viewer: PNVViewer, drawer: PNVDrawer, tab_idx: int):
        self.path = path
        self.petri_net = exact_pn[0]
        self.init_marks = exact_pn[1]
        self.fin_marks = exact_pn[2]
        self.viewer = viewer
        self.drawer = drawer
        self.tab_idx = tab_idx

class PNVMainWindow(QMainWindow):
    def __init__(self):
        super(PNVMainWindow, self).__init__()
        self.menu_bar: QMenuBar = None
        self.stacked_widget: QStackedWidget = None
        self.graph_view: QGraphicsView = None
        self.graph_scene: QGraphicsScene = None
        self.tabs: QTabWidget = None
        self.window_icon = QtGui.QIcon('src/PNV_icon.png')

        self.setWindowIcon(self.window_icon)
        self.setWindowTitle("Petri Net Visualizer")
        self.setMinimumSize(768, 512)
        self.create_menu_bar()
        self.create_stacked_wid()

        self.graphs: list[GraphData] = []

        self.file_dialog = QFileDialog(self)
        self.file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        self.file_dialog.setNameFilter("Petri-net file (*.pnml)")

    def create_stacked_wid(self):
        self.stacked_widget = QStackedWidget(self)

        hello_lbl = QLabel("Petri Net Visualizer - приложение для визуализации сетей Петри")

        self.tabs = QTabWidget(self)

        self.stacked_widget.addWidget(hello_lbl)
        self.stacked_widget.addWidget(self.tabs)
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
        for gd in self.graphs:
            if gd.path == path:
                self.tabs.setCurrentIndex(gd.tab_idx)
                return
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
            name = os.path.basename(path)
            gr = QGraphicsScene(self)
            viewer = PNVViewer(gr)
            drawer = PNVDrawer(gr, pn)
            drawer.draw_petri_net()

            idx = self.tabs.addTab(viewer, name)
            gr_data = GraphData(path, (pn, im, fm), viewer, drawer, idx)
            self.graphs.append(gr_data)

            self.tabs.setTabToolTip(idx, path)
            if self.stacked_widget.currentIndex() == 0:
                # first graph to show
                self.stacked_widget.setCurrentIndex(1)

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

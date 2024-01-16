import os
import sys
import traceback
from typing import Union

import pm4py
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu, QMenuBar, QFileDialog, QStackedWidget, \
    QGraphicsScene, QGraphicsView, QLabel, QTabWidget, QMessageBox
from pm4py import PetriNet, Marking

from pnv.render import PnvViewer, PnvDrawer
from pnv.utils import PnvMessageBoxes

CURRENT_VERSION = 1.17


class GraphData:
    def __init__(self, path: str, exact_pn: tuple["PetriNet", "Marking", "Marking"], viewer: PnvViewer,
                 drawer: PnvDrawer, tab_idx: int):
        self.path = path
        self.petri_net = exact_pn[0]
        self.init_marks = exact_pn[1]
        self.fin_marks = exact_pn[2]
        self.viewer: PnvViewer = viewer
        self.drawer: PnvDrawer = drawer
        self.tab_idx: int = tab_idx


class PNVMainWindow(QMainWindow):
    WINDOW_ICON = None

    def __init__(self):
        super(PNVMainWindow, self).__init__()
        # to be initiated later
        self.menu_bar: Union[QMenuBar, None] = None
        self.stacked_widget: Union[QStackedWidget, None] = None
        self.graph_view: Union[QGraphicsView, None] = None
        self.graph_scene: Union[QGraphicsScene, None] = None
        self.tabs: Union[QTabWidget, None] = None
        # init
        PNVMainWindow.WINDOW_ICON = QtGui.QIcon('resources/pnv_icon.png')

        self.setWindowIcon(PNVMainWindow.WINDOW_ICON)
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

        hello_lbl = QLabel("Petri Net Visualizer - приложение для визуализации сетей Петри. Для работы откройте файл "
                           "представления сети Петри.")

        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        self.stacked_widget.addWidget(hello_lbl)
        self.stacked_widget.addWidget(self.tabs)
        self.setCentralWidget(self.stacked_widget)

    def create_menu_bar(self):
        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)

        file_menu = QMenu("&Файл", self)
        self.menu_bar.addMenu(file_menu)
        file_menu.addAction("&Открыть...", self.open_pnml)

        help_menu = QMenu("&Помощь", self)
        self.menu_bar.addMenu(help_menu)
        help_menu.addAction("&О программе", self.open_dev_info)

    @QtCore.pyqtSlot()
    def open_dev_info(self):
        wm = QMessageBox()
        wm.setIcon(QMessageBox.Information)

        # text data
        wm.setWindowTitle("Информация о программе")
        wm.setText(f"Petri Net Visualizer - приложение для визуализации сетей Петри.\n"
                   f"Фреймворк для интерфейса: PyQt5.\n"
                   f"Библиотека обработки данных: PM4PY."
                   f"\n\n"
                   f"Разработчик: Шамаев Онар Евгеньевич\n"
                   f"Версия: {CURRENT_VERSION}")
        # settings
        wm.setMaximumWidth(128)
        wm.setWindowIcon(PNVMainWindow.WINDOW_ICON)
        wm.exec()

    def close_tab(self, idx: int):
        g, *_ = [g for g in self.graphs if g.tab_idx == idx]
        self.tabs.removeTab(idx)
        self.graphs.remove(g)
        if self.tabs.count() == 0:
            self.stacked_widget.setCurrentIndex(0)
        # TODO: various close logic

    def get_file_path(self):
        if self.file_dialog.exec():
            files = self.file_dialog.selectedFiles()
            if files:
                return files[0]
            return None

    def load_pnml(self, path: str):
        pn = im = fm = None
        for gd in self.graphs:
            if gd.path == path:
                self.tabs.setCurrentIndex(gd.tab_idx)
                return
        try:
            pn, im, fm = pm4py.read_pnml(path)
            if all(len(t) == 0 for t in [pn.places, pn.transitions]):
                PnvMessageBoxes.warning_msg("Загружена пустая сеть!",
                                            icon=self.window_icon).exec()
                return
            if len(pn.arcs) == 0:
                PnvMessageBoxes.warning_msg("Невозможно отобразить бессвязную сеть!",
                                            icon=self.window_icon).exec()
                return
            # https://www.graphviz.org/documentation/TSE93.pdf
        except Exception as ex:
            PnvMessageBoxes.warning_msg("Возникла ошибка при открытии файла!",
                                        inf_text=f"{ex.__class__.__name__}: {ex}",
                                        icon=self.window_icon).exec()
        if pn:
            name = os.path.basename(path)
            gr = QGraphicsScene(self)
            viewer = PnvViewer(gr)
            drawer = PnvDrawer(gr, pn)
            try:
                drawer.draw_petri_net()
            except Exception as ex:
                PnvMessageBoxes.warning_msg("Невозможно отобразить Сеть-Петри!",
                                            f"Извините, но данная версия PetriNetViewer {CURRENT_VERSION}. "
                                            f"не может отобразить загруженный граф! "
                                            f"Сообщение компонента-отрисовки {ex.__class__.__name__}: {ex}",
                                            icon=PNVMainWindow.WINDOW_ICON).exec()
                traceback.print_exc()
                return
            idx = self.tabs.addTab(viewer, name)
            gr_data = GraphData(path, (pn, im, fm), viewer, drawer, idx)
            self.graphs.append(gr_data)

            self.tabs.setTabToolTip(idx, path)
            if self.stacked_widget.currentIndex() == 0:
                # first graph to show
                self.stacked_widget.setCurrentIndex(1)
            self.tabs.setCurrentIndex(idx)

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

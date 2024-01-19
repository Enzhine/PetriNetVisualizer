import os
import pathlib
import sys
import traceback
from typing import Union, Optional

import pm4py
from pm4py import PetriNet, Marking
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu, QMenuBar, QFileDialog, QStackedWidget, \
    QGraphicsScene, QGraphicsView, QLabel, QTabWidget, QMessageBox, QAction

from pnv.render import PnvViewer, PnvDrawer
from pnv.utils import PnvMessageBoxes, PnvConfig

CURRENT_VERSION = 1.18
APP_NAME = "Petri Net Visualizer"


class GraphData:
    def __init__(self, path: str, exact_pn: tuple[PetriNet, Marking, Marking], viewer: PnvViewer,
                 drawer: PnvDrawer, tab_idx: int):
        self.path = path
        self.petri_net = exact_pn[0]
        self.init_marks = exact_pn[1]
        self.fin_marks = exact_pn[2]
        self.viewer: PnvViewer = viewer
        self.drawer: PnvDrawer = drawer
        self.tab_idx: int = tab_idx


class MethodsIO:
    @staticmethod
    def save_as_pnml(g: GraphData, file_path: str):
        pm4py.write_pnml(g.petri_net, g.init_marks, g.fin_marks, file_path)


class PnvMainWindow(QMainWindow):
    WINDOW_ICON = None

    WINDOW_MIN_WIDTH = 768
    WINDOW_MIN_HEIGHT = 512

    CONFIG = None

    def __init__(self):
        super(QMainWindow, self).__init__()
        # to be initiated later
        self.menu_bar: Union[QMenuBar, None] = None
        self.save_action: Union[QAction, None] = None
        self.save_as_action: Union[QAction, None] = None
        self.stacked_widget: Union[QStackedWidget, None] = None
        self.graph_view: Union[QGraphicsView, None] = None
        self.graph_scene: Union[QGraphicsScene, None] = None
        self.tabs: Union[QTabWidget, None] = None
        # static
        PnvMainWindow.WINDOW_ICON = QtGui.QIcon('resources/pnv_icon.png')
        # config
        try:
            PnvMainWindow.CONFIG = PnvConfig(APP_NAME)
        except Exception as ex:
            PnvMessageBoxes.warning(f'Ошибка загрузки конфигурации программы!',
                                    f'Возможно конфигурационный файл повреждён. '
                                    f'Установлены значения по умолчанию. '
                                    f'Сообщение об ошибке {ex.__class__.__name__}: {ex}',
                                    icon=PnvMainWindow.WINDOW_ICON).exec()
        else:
            if not PnvMainWindow.CONFIG.status:
                PnvMessageBoxes.warning(f'Ошибка загрузки конфигурации программы!',
                                        f'Часть данных конфигурационного файла содержит неверный тип данных! '
                                        f'Ошибочные значения установлены по умолчанию.',
                                        icon=PnvMainWindow.WINDOW_ICON).exec()
        # init
        self.setWindowIcon(PnvMainWindow.WINDOW_ICON)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(PnvMainWindow.WINDOW_MIN_WIDTH, PnvMainWindow.WINDOW_MIN_HEIGHT)
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
        file_menu.aboutToShow.connect(self.file_menu_update)
        self.menu_bar.addMenu(file_menu)
        file_menu.addAction("&Открыть...", self.open_file)
        self.save_action = QAction("&Сохранить", self)
        self.save_action.triggered.connect(self.save_file)
        self.save_as_action = QAction("&Сохранить как...", self)
        self.save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)

        help_menu = QMenu("&Помощь", self)
        self.menu_bar.addMenu(help_menu)
        help_menu.addAction("&О программе", self.open_dev_info)

    @QtCore.pyqtSlot()
    def file_menu_update(self):
        self.save_action.setEnabled(self.stacked_widget.currentWidget() is self.tabs)
        self.save_as_action.setEnabled(self.stacked_widget.currentWidget() is self.tabs)

    @QtCore.pyqtSlot()
    def open_dev_info(self):
        wm = QMessageBox()
        wm.setIcon(QMessageBox.Information)

        # text data
        wm.setWindowTitle("Информация о программе")
        wm.setText(f"Petri Net Visualizer - приложение для визуализации сетей Петри.\n"
                   f"Фреймворк для интерфейса: PyQt5.\n"
                   f"Библиотека обработки данных: PM4PY."
                   f"Библиотека генерации разметки: igraph."
                   f"\n\n"
                   f"Разработчик: Шамаев Онар Евгеньевич\n"
                   f"Версия: {CURRENT_VERSION}")
        # settings
        wm.setMaximumWidth(128)
        wm.setWindowIcon(PnvMainWindow.WINDOW_ICON)
        wm.exec()

    def close_tab(self, idx: int):
        self.on_close_tab(idx, True)

    def on_close_tab(self, idx: int, request) -> bool:
        if request and not PnvMessageBoxes.is_accepted(
                PnvMessageBoxes.question(f"Вы собираетесь закрыть вкладку {self.tabs.tabText(idx)}.",
                                         f"Вы уверены?",
                                         icon=PnvMainWindow.WINDOW_ICON).exec()):
            return False
        g = self.find_graph(idx)
        changes = []
        if g.viewer.edited_status:
            changes.append('перемещены элементы сети')
        if g.drawer.edited_status:
            changes.append('сгенерирована разметка')
        if len(changes) != 0 and PnvMessageBoxes.is_accepted(
                PnvMessageBoxes.accept(f"В загруженную сеть были внесены изменения!",
                                       f"Изменения: {','.join(changes)}. "
                                       f"Сохранить изменённую версию, перезаписав файл?",
                                       icon=PnvMainWindow.WINDOW_ICON).exec()):
            # apply changes
            if g.viewer.edited_status:
                g.viewer.inject_all_positions()
            MethodsIO.save_as_pnml(g, g.path)
        self.tabs.removeTab(idx)
        self.graphs.remove(g)
        for g in self.graphs:
            if g.tab_idx > idx:
                # kinda sloppy way
                g.tab_idx = g.tab_idx - 1
        if self.tabs.count() == 0:
            self.stacked_widget.setCurrentIndex(0)
        return True

    def closeEvent(self, e: Optional[QtGui.QCloseEvent]):
        if self.stacked_widget.currentWidget() is self.tabs:
            while self.tabs.count() != 0:
                if not self.on_close_tab(0, False):
                    e.ignore()
                    return
        e.accept()

    def get_existing_file_path(self):
        if self.file_dialog.exec():
            files = self.file_dialog.selectedFiles()
            if files:
                return files[0]
            return None

    def get_new_file_path(self):
        return QFileDialog.getSaveFileName(self, filter="Petri-net file (*.pnml)")[0]

    def load_pnml(self, path: str):
        pn = im = fm = None
        for gd in self.graphs:
            if gd.path == path:
                self.tabs.setCurrentIndex(gd.tab_idx)
                return
        try:
            pn, im, fm = pm4py.read_pnml(path)
            if all(len(t) == 0 for t in [pn.places, pn.transitions]):
                PnvMessageBoxes.warning("Загружена пустая сеть!",
                                        icon=self.window_icon).exec()
                return
            if len(pn.arcs) == 0:
                PnvMessageBoxes.warning("Невозможно отобразить бессвязную сеть!",
                                        icon=self.window_icon).exec()
                return
            # https://www.graphviz.org/documentation/TSE93.pdf
        except Exception as ex:
            PnvMessageBoxes.warning("Возникла ошибка при открытии файла!",
                                    inf_text=f"{ex.__class__.__name__}: {ex}",
                                    icon=self.window_icon).exec()
        if pn:
            name = os.path.basename(path)
            gr = QGraphicsScene(self)
            viewer = PnvViewer(gr)
            drawer = PnvDrawer(gr, pn)
            try:
                drawer.draw_petri_net()
            except TypeError as te:
                if len(te.args) == 1 and te.args[0] == PnvMainWindow.RENDER_CANCELLED:
                    return
                raise
            except Exception as ex:
                PnvMessageBoxes.warning("Невозможно отобразить Сеть-Петри!",
                                        f"Извините, но данная версия PetriNetViewer {CURRENT_VERSION}. "
                                        f"не может отобразить загруженный граф! "
                                        f"Сообщение компонента-отрисовки {ex.__class__.__name__}: {ex}",
                                        icon=PnvMainWindow.WINDOW_ICON).exec()
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
    def open_file(self):
        path = self.get_existing_file_path()
        if path:
            self.load_pnml(path)

    @QtCore.pyqtSlot()
    def save_file(self):
        g = self.find_graph(self.tabs.currentIndex())
        changes = []
        if g.viewer.edited_status:
            changes.append('перемещены элементы сети')
        if g.drawer.edited_status:
            changes.append('сгенерирована разметка')
        if len(changes) != 0 and PnvMessageBoxes.is_accepted(
                PnvMessageBoxes.accept(f"В загруженную сеть были внесены изменения!",
                                       f"Изменения: {','.join(changes)}. "
                                       f"Исходный файл будет перезаписан. Продолжить?",
                                       icon=PnvMainWindow.WINDOW_ICON).exec()):
            # apply changes
            if g.viewer.edited_status:
                g.viewer.inject_all_positions()
            MethodsIO.save_as_pnml(g, g.path)

    @QtCore.pyqtSlot()
    def save_file_as(self):
        path = self.get_new_file_path()
        if len(path) != 0:
            if pathlib.Path(path).exists() and not PnvMessageBoxes.is_accepted(
                PnvMessageBoxes.accept(f"Выбранный файл уже существует!",
                                       f"Файл будет перезаписан. Продолжить?",
                                       icon=PnvMainWindow.WINDOW_ICON).exec()):
                return
            idx = self.tabs.currentIndex()
            g = self.find_graph(idx)
            if g.viewer.edited_status:
                g.viewer.inject_all_positions()
            MethodsIO.save_as_pnml(g, path)
            g.path = path
            g.viewer.edited_status = False
            g.drawer.edited_status = False
            self.update_tab(idx)

    def find_graph(self, idx: int) -> GraphData:
        g, *_ = [g for g in self.graphs if g.tab_idx == idx]
        return g

    def update_tab(self, idx: int):
        g = self.find_graph(idx)
        self.tabs.setTabToolTip(idx, g.path)
        name = os.path.basename(g.path)
        self.tabs.setTabText(idx, name)


def application():
    app = QApplication(sys.argv)
    main_window = PnvMainWindow()
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(f'{CURRENT_VERSION}')

    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    application()

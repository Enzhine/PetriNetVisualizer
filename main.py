import os
import pathlib
import sys
import traceback
from typing import Union, Optional

import pm4py
from PyQt5.QtGui import QPixmap
from pm4py import PetriNet, Marking
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu, QMenuBar, QFileDialog, QStackedWidget, \
    QGraphicsScene, QGraphicsView, QLabel, QTabWidget, QMessageBox, QAction, QStyle, QVBoxLayout, QWidget, QPushButton, \
    QHBoxLayout
from PyQt5.Qt import Qt
from pnv.importer import epnml
from pnv.render import PnvViewer, PnvDrawer
from pnv.utils import PnvMessageBoxes, PnvConfig, PnvIcons, PnvConfigConstants

CURRENT_VERSION = '1.23'
APP_NAME = "Petri Net Visualizer"


class GraphData:
    def __init__(self, path: str, exact_pn: tuple[PetriNet, Marking, Marking], viewer: PnvViewer, tab_idx: int):
        self.path = path
        self.petri_net = exact_pn[0]
        self.init_marks = exact_pn[1]
        self.fin_marks = exact_pn[2]
        self.viewer: PnvViewer = viewer
        self.tab_idx: int = tab_idx


class MethodsIO:
    PNML_FORMAT = '.pnml'
    EPNML_FORMAT = '.epnml'

    @staticmethod
    def import_net(path: str) -> tuple[PetriNet, Marking, Marking]:
        if path.endswith(MethodsIO.PNML_FORMAT):
            pn, im, fm = pm4py.read_pnml(path)
        elif path.endswith(MethodsIO.EPNML_FORMAT):
            pn, im, fm = epnml.import_net(path, None)
        else:
            raise ValueError(f'Unknown file format {path}!')
        return pn, im, fm

    @staticmethod
    def export_net(g: GraphData, path: str, force: bool):
        if path.endswith(MethodsIO.PNML_FORMAT):
            if g.viewer.is_drawn_hierarchical() and \
                    not PnvMessageBoxes.is_accepted(PnvMessageBoxes.accept(f"Данная сеть является иерархической!",
                                           f"Выбранный формат файла не поддерживает хранение иерархических сетей, "
                                           f"поэтому часть данных будет потеряна!").exec()):
                return
            MethodsIO.save_as_pnml(g, path, force)
        elif path.endswith(MethodsIO.EPNML_FORMAT):
            MethodsIO.save_as_epnml(g, path, force)
        else:
            raise ValueError(f'Unknown file format {path}!')

    @staticmethod
    def save_as_pnml(g: GraphData, file_path: str, force: bool):
        if g.viewer.drawer.status.is_changed() or force:
            g.viewer.inject_all_positions()
            init, fin = g.viewer.retrieve_markings()
            g.viewer.drawer.status.reset()
            pm4py.write_pnml(g.petri_net, init, fin, file_path)

    @staticmethod
    def save_as_epnml(g: GraphData, file_path: str, force: bool):
        if g.viewer.drawer.status.is_changed() or force:
            g.viewer.inject_all_positions()
            init, fin = g.viewer.retrieve_markings()
            g.viewer.drawer.status.reset()
            epnml.export_net(g.petri_net, init, file_path, fin)


class PnvMainWindow(QMainWindow):
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
        # load icons
        PnvIcons.MAIN_ICON = QtGui.QIcon('resources/pnv_icon.ico')
        PnvIcons.SETTINGS_ICON = QtGui.QIcon('resources/settings.ico')
        PnvIcons.TXT_REGULAR_ICON = QtGui.QIcon('resources/txt_regular.ico')
        PnvIcons.TXT_CONTRAST_ICON = QtGui.QIcon('resources/txt_contrast.ico')
        PnvIcons.TXT_OVERLAP_ICON = QtGui.QIcon('resources/txt_overlap.ico')
        PnvIcons.TRANSITION_ICON = QtGui.QIcon('resources/transition_icon.ico')
        PnvIcons.PLACE_ICON = QtGui.QIcon('resources/place_icon.ico')
        PnvIcons.VIEW_MODE_ICON = QtGui.QIcon('resources/view_mode_icon.ico')
        PnvIcons.REVIEW_MODE_ICON = QtGui.QIcon('resources/review_mode_icon.ico')
        PnvIcons.EDIT_MODE_ICON = QtGui.QIcon('resources/edit_mode_icon.ico')
        PnvIcons.WRAP_ICON = QtGui.QIcon('resources/wrap_icon.ico')
        PnvIcons.UNWRAP_ICON = QtGui.QIcon('resources/unwrap_icon.ico')
        PnvIcons.EPNML_FILE_ICON = QtGui.QIcon('resources/epnml_file_icon.ico')
        PnvIcons.PNML_FILE_ICON = QtGui.QIcon('resources/pnml_file_icon.ico')
        # config
        try:
            PnvConfig.INSTANCE = PnvConfig(APP_NAME)
        except Exception as ex:
            PnvMessageBoxes.warning(f'Ошибка загрузки конфигурации программы!',
                                    f'Возможно конфигурационный файл повреждён. '
                                    f'Установлены значения по умолчанию. '
                                    f'Сообщение об ошибке {ex.__class__.__name__}: {ex}').exec()
        else:
            if not PnvConfig.INSTANCE.status:
                PnvMessageBoxes.warning(f'Ошибка загрузки конфигурации программы!',
                                        f'Часть данных конфигурационного файла содержит неверный тип данных! '
                                        f'Ошибочные значения установлены по умолчанию.').exec()
        # init
        self.setWindowIcon(PnvIcons.MAIN_ICON)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(PnvMainWindow.WINDOW_MIN_WIDTH, PnvMainWindow.WINDOW_MIN_HEIGHT)
        self.create_menu_bar()
        self.__global_mode_display = QLabel(f"Режим: {PnvConfig.INSTANCE.global_mode}")
        self.create_stacked_wid()

        self.graphs: list[GraphData] = []

        self.file_dialog = QFileDialog(self)
        self.file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        self.file_dialog.setNameFilter("Petri-net file (*.pnml *.epnml)")

    def create_stacked_wid(self):
        self.stacked_widget = QStackedWidget(self)

        welcome = QWidget(self)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        img = QLabel(self)
        img.setPixmap(QPixmap('resources/welcome.png'))
        img.setAlignment(Qt.AlignHCenter)
        layout.addWidget(img)

        layout.addWidget(QLabel("Приложение для интерактивной визуализации сетей Петри."))
        layout.addWidget(QLabel("Для работы откройте файл представления сети Петри."))

        layout_h = QHBoxLayout(self)
        start_btn = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon), 'Открыть файл', self)
        start_btn.clicked.connect(self.open_file)
        chmod_btn = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload), 'Изменить режим', self)
        chmod_btn.clicked.connect(self.chmod)
        layout_h.addWidget(start_btn)
        layout_h.addWidget(chmod_btn)

        layout.addLayout(layout_h)
        layout.addWidget(self.__global_mode_display, alignment=Qt.AlignRight)

        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        welcome.setLayout(layout)
        self.stacked_widget.addWidget(welcome)
        self.stacked_widget.addWidget(self.tabs)
        self.setCentralWidget(self.stacked_widget)

    def create_menu_bar(self):
        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)

        file_menu = QMenu("&Файл", self)
        file_menu.aboutToShow.connect(self.file_menu_update)
        self.menu_bar.addMenu(file_menu)
        file_menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon), "&Открыть...", self.open_file)
        file_menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon), "&Создать", self.create_file)
        file_menu.addSeparator()
        self.save_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "&Сохранить",
                                   self)
        self.save_action.triggered.connect(self.save_file)
        self.save_as_action = QAction("&Сохранить как...", self)
        self.save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)

        help_menu = QMenu("&Помощь", self)
        self.menu_bar.addMenu(help_menu)
        help_menu.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation), "&О программе",
                            self.open_dev_info)
        help_menu.addAction(PnvIcons.SETTINGS_ICON, "&Файл конфигурации",
                            self.open_config_file)

    @QtCore.pyqtSlot()
    def chmod(self):
        if PnvConfig.INSTANCE.global_mode == PnvConfigConstants.GLOBAL_MODE_REVIEW:
            PnvConfig.INSTANCE.global_mode = PnvConfigConstants.GLOBAL_MODE_MUTATE
        elif PnvConfig.INSTANCE.global_mode == PnvConfigConstants.GLOBAL_MODE_MUTATE:
            PnvConfig.INSTANCE.global_mode = PnvConfigConstants.GLOBAL_MODE_REVIEW
        self.__global_mode_display.setText(f"Режим: {PnvConfig.INSTANCE.global_mode}")

    @QtCore.pyqtSlot()
    def file_menu_update(self):
        self.save_action.setEnabled(self.stacked_widget.currentWidget() is self.tabs)
        self.save_as_action.setEnabled(self.stacked_widget.currentWidget() is self.tabs)

    @QtCore.pyqtSlot()
    def open_dev_info(self):
        wm = QMessageBox()
        wm.setIcon(QMessageBox.Question)

        # text data
        wm.setWindowTitle("Информация о программе")
        wm.setText(f"Petri Net Visualizer - приложение для визуализации сетей Петри.\n"
                   f"Фреймворк для интерфейса: PyQt5.\n"
                   f"Библиотека обработки данных: PM4PY.\n"
                   f"Библиотека генерации разметки: igraph.\n"
                   f"\n"
                   f"Разработчик: Шамаев Онар Евгеньевич\n"
                   f"Версия: {CURRENT_VERSION}")
        # settings
        wm.setMaximumWidth(128)
        wm.setWindowIcon(PnvIcons.MAIN_ICON)
        wm.exec()

    @QtCore.pyqtSlot()
    def open_config_file(self):
        os.startfile(PnvConfig.INSTANCE.file)

    def close_tab(self, idx: int):
        self.on_close_tab(idx, True)

    def save_graph(self, g: GraphData, path: str, notify: bool = True, force: bool = False):
        changes = g.viewer.drawer.status.changes()
        if not g.viewer.can_be_saved():
            if notify:
                PnvMessageBoxes.warning("Сеть-Петри не может быть сохранена!",
                                        f"Данная конфигурацию сети нельзя сохранить.").exec()
            return
        if notify:
            if len(changes) != 0 and not PnvMessageBoxes.is_accepted(
                    PnvMessageBoxes.accept(f"В загруженную сеть были внесены изменения!",
                                           f"Изменения: {','.join(changes)}. "
                                           f"Сохранить изменённую версию, перезаписав файл?").exec()):
                return
        MethodsIO.export_net(g, path, force)

    def on_close_tab(self, idx: int, request) -> bool:
        if request and not PnvMessageBoxes.is_accepted(
                PnvMessageBoxes.question(f"Вы собираетесь закрыть вкладку {self.tabs.tabText(idx)}.",
                                         f"Вы уверены?").exec()):
            return False
        g = self.find_graph(idx)
        self.save_graph(g, g.path)

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
        if PnvConfig.INSTANCE:
            PnvConfig.INSTANCE.save()
        e.accept()

    def get_existing_file_path(self):
        if self.file_dialog.exec():
            files = self.file_dialog.selectedFiles()
            if files:
                return files[0]
            return None

    def get_new_file_path(self):
        return QFileDialog.getSaveFileName(self, filter="Extended Petri-net file (*.epnml)")[0]

    def load_petri_net_file(self, path: str):
        pn = im = fm = None
        for gd in self.graphs:
            if gd.path == path:
                self.tabs.setCurrentIndex(gd.tab_idx)
                return
        try:
            # load
            pn, im, fm = MethodsIO.import_net(path)
            # check
            if all(len(t) == 0 for t in [pn.places, pn.transitions]):
                PnvMessageBoxes.warning("Загружена пустая сеть!").exec()
                return
            if len(pn.arcs) == 0:
                PnvMessageBoxes.warning("Невозможно отобразить бессвязную сеть!").exec()
                return
            # some graph render data:
            # https://www.graphviz.org/documentation/TSE93.pdf
        except Exception as ex:
            PnvMessageBoxes.warning("Возникла ошибка при открытии файла!",
                                    inf_text=f"{ex.__class__.__name__}: {ex}").exec()
            traceback.print_exc()
        if pn:
            name = os.path.basename(path)
            gr = QGraphicsScene(self)
            drawer = PnvDrawer(gr, pn)
            viewer = PnvViewer(drawer, gr)
            try:
                viewer.drawer_push_modes()
                drawer.draw_petri_net()
                viewer.init_markings(im, fm)

            except TypeError as te:
                if len(te.args) == 1 and te.args[0] == PnvMainWindow.RENDER_CANCELLED:
                    return
                raise
            except Exception as ex:
                PnvMessageBoxes.warning("Невозможно отобразить Сеть-Петри!",
                                        f"Извините, но данная версия PetriNetViewer {CURRENT_VERSION}. "
                                        f"не может отобразить загруженный граф! "
                                        f"Сообщение компонента-отрисовки {ex.__class__.__name__}: {ex}").exec()
                traceback.print_exc()
                return
            icon = PnvIcons.EPNML_FILE_ICON if name.endswith('epnml') else (PnvIcons.PNML_FILE_ICON if name.endswith('pnml') else None)
            idx = self.tabs.addTab(viewer, icon, name)
            gr_data = GraphData(path, (pn, im, fm), viewer, idx)
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
            self.load_petri_net_file(path)

    @QtCore.pyqtSlot()
    def save_file(self):
        g = self.find_graph(self.tabs.currentIndex())
        self.save_graph(g, g.path)

    @QtCore.pyqtSlot()
    def save_file_as(self):
        path = self.get_new_file_path()
        if len(path) != 0:
            # if pathlib.Path(path).exists() and not PnvMessageBoxes.is_accepted(
            #         PnvMessageBoxes.accept(f"Выбранный файл уже существует!",
            #                                f"Файл будет перезаписан. Продолжить?").exec()):
            #     return
            idx = self.tabs.currentIndex()
            g = self.find_graph(idx)
            self.save_graph(g, path, notify=False, force=True)
            g.path = path
            g.viewer.edited_status = False
            g.viewer.drawer.edited_status = False
            self.update_tab(idx)

    @QtCore.pyqtSlot()
    def create_file(self):
        path = self.get_new_file_path()
        if len(path) == 0:
            return
        # if pathlib.Path(path).exists() and not PnvMessageBoxes.is_accepted(
        #         PnvMessageBoxes.accept(f"Выбранный файл уже существует!",
        #                                f"Файл будет перезаписан. Продолжить?").exec()):
        #     return
        # create empty
        pn, im, fm = PetriNet(), None, None

        # empty net
        tr = PetriNet.Transition('t0')
        PnvDrawer.inject_layout(tr, ((0, 0), (PnvDrawer.GRAPHICS_WIDTH, PnvDrawer.GRAPHICS_WIDTH,)))
        pl = PetriNet.Place('p0')
        PnvDrawer.inject_layout(pl, ((200, 0), (PnvDrawer.GRAPHICS_WIDTH, PnvDrawer.GRAPHICS_WIDTH,)))
        arc = PetriNet.Arc(tr, pl)
        tr.out_arcs.add(arc)
        pl.in_arcs.add(arc)
        pn.transitions.add(tr)
        pn.places.add(pl)
        pn.arcs.add(arc)

        # init
        name = os.path.basename(path)
        gr = QGraphicsScene(self)
        drawer = PnvDrawer(gr, pn)
        viewer = PnvViewer(drawer, gr)
        try:
            # try draw
            viewer.drawer_push_modes()
            drawer.draw_petri_net()

            idx = self.tabs.addTab(viewer, name)
            gr_data = GraphData(path, (pn, im, fm), viewer, idx)
            self.graphs.append(gr_data)

            self.tabs.setTabToolTip(idx, path)
            if self.stacked_widget.currentIndex() == 0:
                # first graph to show
                self.stacked_widget.setCurrentIndex(1)
            self.tabs.setCurrentIndex(idx)
        except TypeError as te:
            if len(te.args) == 1 and te.args[0] == PnvMainWindow.RENDER_CANCELLED:
                return
            raise
        except Exception as ex:
            PnvMessageBoxes.warning("Невозможно отобразить Сеть-Петри!",
                                    f"Извините, но данная версия PetriNetViewer {CURRENT_VERSION}. "
                                    f"не может отобразить загруженный граф! "
                                    f"Сообщение компонента-отрисовки {ex.__class__.__name__}: {ex}").exec()
            traceback.print_exc()
            return

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

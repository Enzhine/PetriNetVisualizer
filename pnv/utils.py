import types

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QStandardPaths
from PyQt5.Qt import Qt
from pathlib import Path
import json


class PnvIcons:
    MAIN_ICON: QIcon = None
    SETTINGS_ICON: QIcon = None

    TXT_REGULAR_ICON: QIcon = None
    TXT_CONTRAST_ICON: QIcon = None
    TXT_OVERLAP_ICON: QIcon = None

    VIEW_MODE_ICON: QIcon = None
    REVIEW_MODE_ICON: QIcon = None
    EDIT_MODE_ICON: QIcon = None

    TRANSITION_ICON: QIcon = None
    PLACE_ICON: QIcon = None

    WRAP_ICON: QIcon = None
    UNWRAP_ICON: QIcon = None

    PNML_FILE_ICON: QIcon = None
    EPNML_FILE_ICON: QIcon = None


class PnvMessageBoxes:
    @staticmethod
    def proceed(text: str, inf_text: str = None, title: str = "Внимание!", icon=PnvIcons.MAIN_ICON) -> QMessageBox:
        wm = QMessageBox()
        wm.setIcon(QMessageBox.Information)

        wm.setWindowTitle(title)
        wm.setText(text)

        wm.setStandardButtons(QMessageBox.Ok)
        wm.setDefaultButton(QMessageBox.Ok)
        wm.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        if icon:
            wm.setWindowIcon(icon)
        if inf_text:
            wm.setInformativeText(inf_text)
        return wm

    @staticmethod
    def warning(text: str, inf_text: str = None, title: str = "Внимание!", icon=PnvIcons.MAIN_ICON) -> QMessageBox:
        wm = QMessageBox()
        wm.setIcon(QMessageBox.Warning)

        wm.setWindowTitle(title)
        wm.setText(text)

        if icon:
            wm.setWindowIcon(icon)
        if inf_text:
            wm.setInformativeText(inf_text)
        return wm

    @staticmethod
    def accept(text: str, inf_text: str = None, title: str = "Требуется подтверждение!", icon=PnvIcons.MAIN_ICON) -> QMessageBox:
        wm = QMessageBox()
        wm.setIcon(QMessageBox.Question)

        wm.setWindowTitle(title)
        wm.setText(text)

        wm.setStandardButtons(QMessageBox.Yes)
        wm.addButton(QMessageBox.No)
        wm.setDefaultButton(QMessageBox.Yes)
        wm.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        if icon:
            wm.setWindowIcon(icon)
        if inf_text:
            wm.setInformativeText(inf_text)
        return wm

    @staticmethod
    def question(text: str, inf_text: str = None, title: str = "Внимание!", icon=PnvIcons.MAIN_ICON) -> QMessageBox:
        wm = QMessageBox()
        wm.setIcon(QMessageBox.Question)

        wm.setWindowTitle(title)
        wm.setText(text)

        wm.setStandardButtons(QMessageBox.Yes)
        wm.addButton(QMessageBox.Cancel)
        wm.setDefaultButton(QMessageBox.Yes)
        if icon:
            wm.setWindowIcon(icon)
        if inf_text:
            wm.setInformativeText(inf_text)
        return wm

    @staticmethod
    def is_accepted(acc_box_exec):
        return acc_box_exec == QMessageBox.Yes


class PnvConfigConstants:
    IGRAPH_GEN_MODE_AUTO = 'auto'

    ENTER_MODE_VIEW = 'view'
    ENTER_MODE_EXPLORE = 'explore'
    ENTER_MODE_MUTATE = 'mutate'

    LABELING_MODE_MIXED = 'mixed'
    LABELING_MODE_CONTRAST = 'contrast'
    LABELING_MODE_OVERLAP = 'overlap'

    GLOBAL_MODE_REVIEW = 'review'
    GLOBAL_MODE_MUTATE = 'mutate'

    @staticmethod
    def color_at(_ord: int):
        cols = PnvConfig.INSTANCE.wrap_colors
        _len = len(cols)
        return int(cols[_ord % _len][1:], 16)


class PnvConfig:
    CONFIG_FILE = "conf.json"
    INSTANCE: 'PnvConfig' = None

    def __init__(self, folder_name: str):
        # default props
        self.igraph_gen_mode: str = PnvConfigConstants.IGRAPH_GEN_MODE_AUTO
        self.limit_translation: bool = True
        self.limit_zoom: bool = True
        self.limited_zoom_max: float = 4
        self.limited_zoom_min: float = 0.5
        self.enter_mode: str = PnvConfigConstants.ENTER_MODE_VIEW
        self.labeling_mode: str = PnvConfigConstants.LABELING_MODE_MIXED
        self.text_font_family: str = 'Arial font'
        self.text_font_size: int = 10
        self.text_font_weight: int = 2
        self.wrap_colors: list[str] = [
            "#FF9696",
            "#FFCA96",
            "#FFFF96",
            "#CAFF96",
            "#96FF96",
            "#96FFCA",
            "#96FFFF",
            "#96CAFF",
            "#9696FF",
            "#CA96FF",
            "#FF96FF",
            "#FF96CA",
            "#FF9696"
        ]
        self.global_mode: str = PnvConfigConstants.GLOBAL_MODE_REVIEW
        # folder name
        folder_name = folder_name.replace(' ', '')
        if len(folder_name) == 0:
            raise ValueError(f'Empty folder name!')
        # folder init
        app_data_path = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)).parent.absolute()
        pnv_dir = app_data_path / folder_name
        if not pnv_dir.exists():
            pnv_dir.mkdir()
        self.file = pnv_dir / PnvConfig.CONFIG_FILE
        mode = 'r' if self.file.exists() else 'w+'
        with open(self.file, mode=mode) as f:
            data = f.read()
        self.status = True
        if len(data) != 0:
            j = json.loads(data)
            self.__deserialize(j)
        else:
            self.save()

    @staticmethod
    def __not_serializable(field: str) -> bool:
        return field in ['file', 'status']

    def __deserialize(self, j):
        for key, value in self.__dict__.items():
            if isinstance(value, (types.FunctionType, types.MethodType)) or self.__not_serializable(key):
                continue
            if key in j:
                if isinstance(j[key], type(value)):
                    setattr(self, key, j[key])
                else:
                    self.status = False

    def __serialize(self) -> dict:
        ret = dict()
        for key, value in self.__dict__.items():
            if isinstance(value, (types.FunctionType, types.MethodType)) or PnvConfig.__not_serializable(key):
                continue
            ret[key] = value
        return ret

    def save(self):
        data = json.dumps(self.__serialize(), indent=4)
        with open(self.file, mode='w+') as f:
            f.write(data)

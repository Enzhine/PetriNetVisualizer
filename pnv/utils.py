import types

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QStandardPaths
from PyQt5.Qt import Qt
from pathlib import Path
import json


class PnvMessageBoxes:
    @staticmethod
    def proceed(text: str, inf_text: str = None, title: str = "Внимание!", icon=None) -> QMessageBox:
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
    def warning(text: str, inf_text: str = None, title: str = "Внимание!", icon=None) -> QMessageBox:
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
    def accept(text: str, inf_text: str = None, title: str = "Требуется подтверждение!", icon=None) -> QMessageBox:
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
    def question(text: str, inf_text: str = None, title: str = "Внимание!", icon=None) -> QMessageBox:
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
    ENTER_MODE_VIEW = 'view'
    ENTER_MODE_EDIT = 'edit'


class PnvConfig:
    CONFIG_FILE = "conf.json"
    INSTANCE: 'PnvConfig' = None

    def __init__(self, folder_name: str):
        # default props
        self.igraph_gen_mode: str = 'auto'
        self.limit_translation: bool = True
        self.limit_zoom: bool = True
        self.limited_zoom_max: float = 4
        self.limited_zoom_min: float = 0.5
        self.enter_mode: str = PnvConfigConstants.ENTER_MODE_VIEW
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

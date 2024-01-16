from PyQt5.QtWidgets import QMessageBox


class PnvMessageBoxes:
    @staticmethod
    def warning_msg(text: str, inf_text: str = None, title: str = "Внимание!", icon=None):
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
    def accept_msg(text: str, inf_text: str = None, title: str = "Требуется подтверждение!", icon=None):
        wm = QMessageBox()
        wm.setIcon(QMessageBox.Question)

        wm.setWindowTitle(title)
        wm.setText(text)
        wm.setStandardButtons(QMessageBox.Yes)
        wm.addButton(QMessageBox.No)
        wm.setDefaultButton(QMessageBox.Yes)
        if icon:
            wm.setWindowIcon(icon)
        if inf_text:
            wm.setInformativeText(inf_text)
        return wm

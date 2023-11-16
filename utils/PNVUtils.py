from PyQt5.QtWidgets import QGraphicsScene, QMessageBox
from PyQt5 import Qt


class PNVDrawer:
    PLACE_RADIUS = 30
    PLACE_WIDTH = 4

    def __init__(self, scene: QGraphicsScene, net: "PetriNet"):
        self.scene = scene
        self.net = net

    def draw_place(self, x: int, y: int, w: int) -> "QGraphicsEllipseItem":
        self.scene.addEllipse(Qt.QRectF(x, y, PNVDrawer.PLACE_RADIUS, PNVDrawer.PLACE_RADIUS),
                              Qt.QPen(Qt.Qt.black, PNVDrawer.PLACE_WIDTH))

    def draw_petri_net(self):
        self.scene.addText("To be continued...")
        # TODO: DRAW THE NET


class PNVMessageBoxes:

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
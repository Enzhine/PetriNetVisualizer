import math

from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView, QMessageBox, QGraphicsEllipseItem
from PyQt5 import Qt, QtGui, QtCore
from pm4py import PetriNet

import typing


def mod(num: int, other: int):
    return int(math.copysign(num % other, num))


class PNVViewer(QGraphicsView):
    BG_PX_GRID = 100
    BG_BRUSH = Qt.QBrush(Qt.QColor(0xdadada))
    GRID_PEN = Qt.QPen(Qt.QBrush(Qt.QColor(0xadadad)), 1)

    def __init__(self, *args, **kwargs):
        super(QGraphicsView, self).__init__(*args, *kwargs)  # Universal constructor bypass
        self.inwards = 1.1  # Mouse scroll scale factor
        self.outwards = 1 / self.inwards
        self.last_press: Qt.QPoint = None  # For press event
        self.scaler = 0

    def scale_factor(self):
        return self.inwards ** self.scaler

    def wheelEvent(self, e: typing.Optional[QtGui.QWheelEvent]) -> None:
        vec = e.angleDelta().y() / 120  # Scroll delta
        # scale scene
        if vec > 0:
            self.scaler += 1
            self.scale(self.inwards, self.inwards)  # closer
        else:
            self.scaler -= 1
            self.scale(self.outwards, self.outwards)  # farther
        # scale grid
        sf = self.scale_factor()
        if sf >= 2:
            self.BG_PX_GRID = 50
            self.GRID_PEN.setWidthF(0.5)
        elif 0.75 < sf < 2:
            self.BG_PX_GRID = 100
            self.GRID_PEN.setWidthF(1)
        else:
            self.BG_PX_GRID = 200
            self.GRID_PEN.setWidthF(3)
        super().wheelEvent(e)

    def mousePressEvent(self, e: typing.Optional[QtGui.QMouseEvent]) -> None:
        if e.button() in [Qt.Qt.RightButton, Qt.Qt.MiddleButton]:  # RMC press
            self.last_press = e.pos()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: typing.Optional[QtGui.QMouseEvent]) -> None:
        if e.button() in [Qt.Qt.RightButton, Qt.Qt.MiddleButton] and self.last_press is not None:  # RMC release
            self.last_press = None
        super().mouseReleaseEvent(e)

    def mouseMoveEvent(self, e: typing.Optional[QtGui.QMouseEvent]) -> None:
        if self.last_press is not None:  # RMC hold
            delta = self.last_press - e.pos()
            self.setSceneRect(
                self.sceneRect().translated(delta.x() / self.transform().m11(), delta.y() / self.transform().m22()))
            self.last_press = e.pos()
        super().mouseMoveEvent(e)

    def drawBackground(self, painter: typing.Optional[QtGui.QPainter], rect: QtCore.QRectF) -> None:
        painter.fillRect(rect, self.BG_BRUSH)
        painter.setPen(self.GRID_PEN)
        # grid draw
        ix, ix0 = int(rect.x()), int(rect.x() + rect.width())
        iy, iy0 = int(rect.y()), int(rect.y() + rect.height())
        x = ix + mod(ix, self.BG_PX_GRID)
        x0 = ix0 + mod(ix0, self.BG_PX_GRID)
        y = iy + mod(iy, self.BG_PX_GRID)
        y0 = iy0 + mod(iy0, self.BG_PX_GRID)
        for x in range(x, x0, self.BG_PX_GRID):
            painter.drawLine(Qt.QLineF(x, rect.y(), x, rect.y() + rect.height()))
        for y in range(y, y0, self.BG_PX_GRID):
            painter.drawLine(Qt.QLineF(rect.x(), y, rect.x() + rect.width(), y))

class PNVDrawer:
    PLACE_RADIUS = 30
    PLACE_WIDTH = 4

    def __init__(self, scene: QGraphicsScene, net: PetriNet):
        self.scene = scene
        self.net = net

    def draw_place(self, x: int, y: int) -> QGraphicsEllipseItem:
        return self.scene.addEllipse(Qt.QRectF(x, y, PNVDrawer.PLACE_RADIUS, PNVDrawer.PLACE_RADIUS),
                                     Qt.QPen(Qt.Qt.black, PNVDrawer.PLACE_WIDTH))

    def draw_petri_net(self):
        self.draw_place(0, 0)
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

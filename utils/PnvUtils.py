import math
import typing
from typing import Union

import numpy as np
from PyQt5 import Qt, QtGui, QtCore
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView, QMessageBox, QGraphicsEllipseItem, QGraphicsRectItem, \
    QGraphicsLineItem
from pm4py import PetriNet

from utils.PnvQGraphics import PnvQGRectItem, PnvQGEllipseItem


def mod(num: int, other: int):
    return -abs(num % other)


class PNVViewer(QGraphicsView):
    BG_PX_GRID = 100
    BG_BRUSH = Qt.QBrush(Qt.QColor(0xdadada))
    GRID_PEN = Qt.QPen(Qt.QBrush(Qt.QColor(0xadadad)), 1)

    def __init__(self, *args, **kwargs):
        super(QGraphicsView, self).__init__(*args, *kwargs)  # Universal constructor bypass
        self.inwards = 1.1  # Mouse scroll scale factor
        self.outwards = 1 / self.inwards
        self.last_rmp: Union[Qt.QPoint, None] = None  # For right mouse press
        self.last_lmp: Union[Qt.QPoint, None] = None  # For left mouse press
        self.selection: Union[QGraphicsRectItem, None] = None
        self.selected_items: set[Union[PnvQGRectItem, PnvQGEllipseItem]] = set()
        self.scaler = 0
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)

    def scale_factor(self):
        return self.inwards ** self.scaler

    def wheelEvent(self, e: typing.Optional[QtGui.QWheelEvent]) -> None:
        vec = e.angleDelta().y() / 120  # Scroll delta
        # scale scene
        if vec > 0 and self.scaler < (8 + 2):
            self.scaler += 1
            self.scale(self.inwards, self.inwards)  # closer
        elif vec < 0 and self.scaler > (-4 - 2):
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
            # setting hold
            self.last_rmp = e.pos()
            # cursor override logic
            QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.ClosedHandCursor)
        elif e.button() == Qt.Qt.LeftButton and self.last_rmp is None:
            # setting hold
            self.last_lmp = self.mapToScene(e.pos())
            self.selection = self.scene().addRect(Qt.QRectF(self.last_lmp.x(), self.last_lmp.y(), 1, 1),
                                                  Qt.QPen(Qt.Qt.darkCyan, 1, Qt.Qt.DashLine))
            # cursor override logic
            QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.CrossCursor)
        # firing event at super
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: typing.Optional[QtGui.QMouseEvent]) -> None:
        if e.button() in [Qt.Qt.RightButton, Qt.Qt.MiddleButton] and self.last_rmp is not None:  # RMC release
            # resetting hold
            self.last_rmp = None
            # cursor override logic
            if self.last_lmp is None:
                QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.ArrowCursor)
            else:
                QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.CrossCursor)
        elif e.button() == Qt.Qt.LeftButton:  # LMC release
            # resetting hold
            self.last_lmp = None
            if self.selection is not None:
                self.scene().removeItem(self.selection)
                self.selection = None
                self.scene().update()
            # cursor override logic
            if self.last_rmp is None:
                QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.ArrowCursor)
            else:
                QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.ClosedHandCursor)
        # firing event at super
        super().mouseReleaseEvent(e)

    def mouseMoveEvent(self, e: typing.Optional[QtGui.QMouseEvent]) -> None:
        if self.last_rmp is not None:  # RMC hold
            delta = self.last_rmp - e.pos()
            self.setSceneRect(
                self.sceneRect().translated(delta.x() / self.transform().m11(), delta.y() / self.transform().m22()))
            self.last_rmp = e.pos()
        if self.last_lmp is not None:  # LMC hold
            cur = self.mapToScene(e.pos())  # current pos
            to = cur - self.last_lmp  # from to
            self.selection.setRect(Qt.QRectF(min(self.last_lmp.x(), self.last_lmp.x() + to.x()),
                                             min(self.last_lmp.y(), self.last_lmp.y() + to.y()),
                                             abs(to.x()),
                                             abs(to.y())))
            # find selectable
            collides: set[Union[PnvQGRectItem, PnvQGEllipseItem]] = \
                set([o for o in self.selection.collidingItems(Qt.Qt.IntersectsItemBoundingRect)
                     if isinstance(o, PnvQGRectItem) or isinstance(o, PnvQGEllipseItem)])
            # differentiate whether selected or not
            lost = self.selected_items - collides
            new = collides - self.selected_items
            # force select
            for i in lost:
                i.hover_leave_manually()
            for i in new:
                i.hover_enter_manually()
            # update selected
            self.selected_items = collides
        super().mouseMoveEvent(e)

    # def drawForeground(self, painter: typing.Optional[QtGui.QPainter], rect: QtCore.QRectF) -> None:
    #     painter.drawText(Qt.QPointF(rect.x() + rect.width()/2,rect.y() + rect.height()/2), 'wasd')

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
        for xt in range(x, x0 + 1, self.BG_PX_GRID):
            painter.drawLine(Qt.QLineF(xt, rect.y(), xt, rect.y() + rect.height()))
        for yt in range(y, y0 + 1, self.BG_PX_GRID):
            painter.drawLine(Qt.QLineF(rect.x(), yt, rect.x() + rect.width(), yt))


class PNVDrawer:
    PLACE_WIDTH = 3

    def __init__(self, scene: QGraphicsScene, net: PetriNet):
        self.scene = scene
        self.net = net

    def draw_place_directly(self, x: int, y: int, r: int) -> PnvQGEllipseItem:
        # custom ellipse init
        obj = PnvQGEllipseItem(Qt.QRectF(x - r / 2, y - r / 2, r, r))
        obj.setPen(Qt.QPen(Qt.Qt.black, PNVDrawer.PLACE_WIDTH))
        obj.setBrush(Qt.QBrush(Qt.Qt.white))

        # obj.set_hovered_pen(Qt.QPen(Qt.Qt.red, PNVDrawer.PLACE_WIDTH)) # style issue
        obj.set_hovered_brush(Qt.QBrush(Qt.Qt.lightGray))

        self.scene.addItem(obj)
        return obj

    def draw_transition_directly(self, x: int, y: int, w: int, h: int, label: str = None) -> PnvQGRectItem:
        # custom rectangle init
        obj = PnvQGRectItem(Qt.QRectF(x - w / 2, y - h / 2, w, h))
        obj.setPen(Qt.QPen(Qt.Qt.black, PNVDrawer.PLACE_WIDTH))
        obj.setBrush(Qt.QBrush(Qt.Qt.white))

        # obj.set_hovered_pen(Qt.QPen(Qt.Qt.red, PNVDrawer.PLACE_WIDTH)) # style issue
        obj.set_hovered_brush(Qt.QBrush(Qt.Qt.lightGray))

        self.scene.addItem(obj)
        if label:
            text = self.scene.addText(label)
            w = Qt.QFontMetrics(text.font()).width(label)
            h = Qt.QFontMetrics(text.font()).height()
            text.setPos(Qt.QPointF(x - w / 2, y + h))
            # binding text, but not events
            text.setParentItem(obj)
            text.setAcceptHoverEvents(False)
        return obj

    def draw_arrow_directly(self, from_x: int, from_y: int, to_x: int, to_y: int) -> QGraphicsLineItem:
        line = self.scene.addLine(Qt.QLineF(from_x, from_y, to_x, to_y),
                                  Qt.QPen(Qt.Qt.black, PNVDrawer.PLACE_WIDTH))
        vec = np.array([from_x - to_x, from_y - to_y])
        vec = vec / np.linalg.norm(vec) * 10
        rot1 = self.rotated(vec, 30)
        rot2 = self.rotated(vec, -30)
        self.scene.addLine(Qt.QLineF(to_x + rot1[0], to_y + rot1[1], to_x, to_y),
                           Qt.QPen(Qt.Qt.black, PNVDrawer.PLACE_WIDTH)).setParentItem(line)
        self.scene.addLine(Qt.QLineF(to_x + rot2[0], to_y + rot2[1], to_x, to_y),
                           Qt.QPen(Qt.Qt.black, PNVDrawer.PLACE_WIDTH)).setParentItem(line)
        return line

    def draw_place(self, p: PetriNet.Place) -> QGraphicsEllipseItem:
        pos, shape = self.layout(p)
        return self.draw_place_directly(*pos, shape[0])

    def draw_transition(self, t: PetriNet.Transition) -> QGraphicsRectItem:
        pos, shape = self.layout(t)
        return self.draw_transition_directly(*pos, *shape, t.label)

    def draw_arc(self, from_: Union[PetriNet.Place, PetriNet.Transition],
                 to: Union[PetriNet.Place, PetriNet.Transition]) -> Union[QGraphicsLineItem, None]:
        """Might return None if it refers to itself"""
        xy0, s0 = self.layout(from_)
        xy1, s1 = self.layout(to)
        vec = (xy1[0] - xy0[0], xy1[1] - xy0[1])
        d = math.sqrt(vec[0] * vec[0] + vec[1] * vec[1])
        if d == 0:
            return None
        if isinstance(from_, PetriNet.Place):
            xy0 = (xy0[0] + vec[0] * s0[0] / 2 / d, xy0[1] + vec[1] * s0[1] / 2 / d)
        if isinstance(from_, PetriNet.Transition):
            xy0 = (xy0[0] + max(min(vec[0], s0[0] / 2), -s0[0] / 2), xy0[1] + max(min(vec[1], s0[1] / 2), -s0[1] / 2))
        if isinstance(to, PetriNet.Place):
            xy1 = (xy1[0] - vec[0] * s1[0] / 2 / d, xy1[1] - vec[1] * s1[1] / 2 / d)
        if isinstance(to, PetriNet.Transition):
            xy1 = (xy1[0] + max(min(-vec[0], s1[0] / 2), -s1[0] / 2), xy1[1] + max(min(-vec[1], s1[1] / 2), -s1[1] / 2))
        return self.draw_arrow_directly(*xy0, *xy1)

    @staticmethod
    def rotated(vec, deg):
        return np.array([[np.cos(deg * np.pi / 180), -np.sin(deg * np.pi / 180)],
                         [np.sin(deg * np.pi / 180), np.cos(deg * np.pi / 180)]]) @ vec

    @staticmethod
    def has_layout(obj):
        return hasattr(obj, 'properties') and ('layout_information_petri' in obj.properties) \
               and isinstance(obj.properties['layout_information_petri'], tuple)

    @staticmethod
    def layout(obj):
        return obj.properties['layout_information_petri']

    def draw_petri_net(self) -> bool:
        if all(self.has_layout(obj) for obj in [*self.net.places, *self.net.transitions]):
            for p in self.net.places:
                self.draw_place(p)
            for t in self.net.transitions:
                self.draw_transition(t)
            for a in self.net.arcs:
                self.draw_arc(a.source, a.target)
            return True
        return False


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

from typing import Union, Optional

from PyQt5 import Qt, QtGui, QtCore
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsSceneContextMenuEvent, \
    QGraphicsSceneHoverEvent, QStyleOptionGraphicsItem, QWidget, QGraphicsRectItem, QGraphicsLineItem
import math
import numpy as np
from pm4py import PetriNet


class PetriNetBind:
    def __init__(self):
        self.__petri_net_obj: Union[PetriNet.Place, PetriNet.Transition, None] = None

    def petri_net_binded(self) -> Union[PetriNet.Place, PetriNet.Transition, None]:
        return self.__petri_net_obj

    def petri_net_bind(self, obj: Union[PetriNet.Place, PetriNet.Transition]):
        self.__petri_net_obj = obj


class HoverSelectable:
    def __init__(self):
        # hovered props
        self.pnv_hover_pen: Union[QtGui.QPen, None] = None
        self.pnv_hover_brush: Union[QtGui.QBrush, None] = None
        self.pnv_is_hovered: bool = False
        # selected props
        self.pnv_selected_pen: Union[QtGui.QPen, None] = None
        self.pnv_selected_brush: Union[QtGui.QBrush, None] = None
        self.pnv_is_selected: bool = False

    def set_hovered_pen(self, pen: Qt.QPen):
        self.pnv_hover_pen = pen

    def set_hovered_brush(self, br: Qt.QBrush):
        self.pnv_hover_brush = br

    def set_selected_pen(self, pen: Qt.QPen):
        self.pnv_selected_pen = pen

    def set_selected_brush(self, br: Qt.QBrush):
        self.pnv_selected_brush = br

    def get_pen(self):
        if self.pnv_is_selected and self.pnv_selected_pen is not None:
            return self.pnv_selected_pen
        elif self.pnv_is_hovered and self.pnv_hover_pen is not None:
            return self.pnv_hover_pen
        return None

    def get_brush(self):
        if self.pnv_is_selected and self.pnv_selected_brush is not None:
            return self.pnv_selected_brush
        elif self.pnv_is_hovered and self.pnv_hover_brush is not None:
            return self.pnv_hover_brush
        return None

    def manual_update(self):
        raise NotImplementedError()

    def select_manually(self):
        self.pnv_is_selected = True
        self.manual_update()

    def deselect_manually(self):
        self.pnv_is_selected = False
        self.manual_update()

    def hover_leave_manually(self):
        self.pnv_is_hovered = False
        self.manual_update()

    def hover_enter_manually(self):
        self.pnv_is_hovered = True
        self.manual_update()


class PnvQGPlaceItem(QGraphicsEllipseItem, HoverSelectable, PetriNetBind):
    def __init__(self, *args, **kwargs):
        super(PetriNetBind, self).__init__()
        super(QGraphicsEllipseItem, self).__init__(*args, **kwargs)  # Universal constructor bypass
        self.setAcceptHoverEvents(True)
        super(HoverSelectable, self).__init__()
        # arrows holder
        self.arrows: set[PnvQGArrowItem] = set()

    def pen(self) -> QtGui.QPen:
        ret = self.get_pen()
        return ret if ret is not None else super(QGraphicsEllipseItem, self).pen()

    def brush(self) -> QtGui.QBrush:
        ret = self.get_brush()
        return ret if ret is not None else super(QGraphicsEllipseItem, self).brush()

    def manual_update(self):
        self.update()

    def hoverLeaveEvent(self, event: Optional['QGraphicsSceneHoverEvent']) -> None:
        self.pnv_is_hovered = False
        super().hoverLeaveEvent(event)

    def hoverEnterEvent(self, event: Optional['QGraphicsSceneHoverEvent']) -> None:
        self.pnv_is_hovered = True
        super().hoverEnterEvent(event)

    def paint(self, painter: Optional[QtGui.QPainter], option: Optional['QStyleOptionGraphicsItem'],
              widget: Optional['QWidget'] = ...) -> None:
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawEllipse(self.rect())

    def contextMenuEvent(self, event: Optional[QGraphicsSceneContextMenuEvent]) -> None:

        #     cmenu = QMenu(self.scene().parent())
        #     cmenu.addAction('&ACTION')
        #     cmenu.exec(event.screenPos())
        # fix hovering as well
        # MIGHT BE USED
        super(PnvQGPlaceItem, self).contextMenuEvent(event)


class PnvQGTransitionItem(QGraphicsRectItem, HoverSelectable, PetriNetBind):

    def __init__(self, *args, **kwargs):
        super(PetriNetBind, self).__init__()
        super(QGraphicsRectItem, self).__init__(*args, *kwargs)  # Universal constructor bypass
        self.setAcceptHoverEvents(True)
        super(HoverSelectable, self).__init__()
        # arrows holder
        self.arrows: set[PnvQGArrowItem] = set()

    def pen(self) -> QtGui.QPen:
        ret = self.get_pen()
        return ret if ret is not None else super(QGraphicsRectItem, self).pen()

    def brush(self) -> QtGui.QBrush:
        ret = self.get_brush()
        return ret if ret is not None else super(QGraphicsRectItem, self).brush()

    def manual_update(self):
        self.update()

    def hoverLeaveEvent(self, event: Optional['QGraphicsSceneHoverEvent']) -> None:
        self.pnv_is_hovered = False
        super().hoverLeaveEvent(event)

    def hoverEnterEvent(self, event: Optional['QGraphicsSceneHoverEvent']) -> None:
        self.pnv_is_hovered = True
        super().hoverEnterEvent(event)

    def paint(self, painter: Optional[QtGui.QPainter], option: Optional['QStyleOptionGraphicsItem'],
              widget: Optional['QWidget'] = ...) -> None:
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())


class PnvQGArrowItem(QGraphicsLineItem):
    def __init__(self, from_, to):
        self.from_: Union[PnvQGPlaceItem, PnvQGTransitionItem] = from_
        self.to: Union[PnvQGPlaceItem, PnvQGTransitionItem] = to
        line = Qt.QLineF(*self.last_line())
        self._x1: float = 0
        self._y1: float = 0
        self._x2: float = 0
        self._y2: float = 0
        super(QGraphicsLineItem, self).__init__(line)

    def from_point(self) -> tuple[float, float]:
        return self.from_.rect().x() + self.from_.x(), self.from_.rect().y() + self.from_.y()

    def to_point(self) -> tuple[float, float]:
        return self.to.rect().x() + self.to.x(), self.to.rect().y() + self.to.y()

    def from_sizes(self) -> tuple[float, float]:
        return self.from_.rect().width(), self.from_.rect().height()

    def to_sizes(self) -> tuple[float, float]:
        return self.to.rect().width(), self.to.rect().height()

    def from_bound(self):
        return self._x1, self._y1

    def to_bound(self):
        return self._x2, self._y2

    def last_line(self) -> tuple[float, float, float, float]:
        xy0, s0 = self.from_point(), self.from_sizes()
        xy1, s1 = self.to_point(), self.to_sizes()
        vec = (xy1[0] - xy0[0], xy1[1] - xy0[1])
        d = math.sqrt(vec[0] * vec[0] + vec[1] * vec[1])
        if d == 0:
            return 0, 0, 0, 0
        if isinstance(self.from_, PnvQGPlaceItem):
            xy0 = (xy0[0] + vec[0] * s0[0] / 2 / d, xy0[1] + vec[1] * s0[1] / 2 / d)
        elif isinstance(self.from_, PnvQGTransitionItem):
            xy0 = (xy0[0] + max(min(vec[0], s0[0] / 2), -s0[0] / 2), xy0[1] + max(min(vec[1], s0[1] / 2), -s0[1] / 2))
        if isinstance(self.to, PnvQGPlaceItem):
            xy1 = (xy1[0] - vec[0] * s1[0] / 2 / d, xy1[1] - vec[1] * s1[1] / 2 / d)
        elif isinstance(self.to, PnvQGTransitionItem):
            xy1 = (xy1[0] + max(min(-vec[0], s1[0] / 2), -s1[0] / 2), xy1[1] + max(min(-vec[1], s1[1] / 2), -s1[1] / 2))
        return xy0[0] + s0[0]/2, xy0[1] + s0[1]/2, xy1[0] + s1[0]/2, xy1[1] + + s1[1]/2

    def update(self, rect: QtCore.QRectF = ...) -> None:
        self._x1, self._y1, self._x2, self._y2 = self.last_line()
        self.setLine(self._x1, self._y1, self._x2, self._y2)
        super(PnvQGArrowItem, self).update(rect)

    def shape(self) -> QtGui.QPainterPath:
        path = super(PnvQGArrowItem, self).shape()
        xy1 = self.to_bound()
        path.addRect(Qt.QRectF(xy1[0]-10, xy1[1]-10, 20, 20))
        return path

    @staticmethod
    def rotated(vec, deg):
        return np.array([[np.cos(deg * np.pi / 180), -np.sin(deg * np.pi / 180)],
                         [np.sin(deg * np.pi / 180), np.cos(deg * np.pi / 180)]]) @ vec

    def paint(self, painter: Optional[QtGui.QPainter],
              option: Optional['QStyleOptionGraphicsItem'],
              widget: Optional[QWidget] = ...) -> None:
        ln = self.line()
        vec = np.array([ln.x1() - ln.x2(), ln.y1() - ln.y2()])
        vec = vec / np.linalg.norm(vec) * 10
        rot1 = self.rotated(vec, 30)
        rot2 = self.rotated(vec, -30)
        painter.setPen(self.pen())
        painter.drawLine(Qt.QLineF(ln.x2()+rot1[0], ln.y2()+rot1[1], ln.x2(), ln.y2()))
        painter.drawLine(Qt.QLineF(ln.x2()+rot2[0], ln.y2()+rot2[1], ln.x2(), ln.y2()))
        painter.drawLine(*self.last_line())

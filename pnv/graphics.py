from typing import Union, Optional

from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsSceneContextMenuEvent, \
    QGraphicsSceneHoverEvent, QStyleOptionGraphicsItem, QWidget, QGraphicsRectItem, QMenu, QStyle, \
    QGraphicsLineItem
import math
import numpy as np
from pm4py import PetriNet

import pnv.importer.epnml
from pnv.utils import PnvMessageBoxes


class Markable:
    def __init__(self, marks=0, final=False):
        self.__markings = marks
        self.__is_final = final

    def __get_markings(self):
        return self.__markings

    def __set_markings(self, val: int):
        if val < 0:
            return
        self.__markings = val

    def __get_final(self):
        return self.__is_final

    def __set_final(self, val: bool):
        self.__is_final = val

    final = property(__get_final, __set_final)
    markings = property(__get_markings, __set_markings)


class PetriNetBind:
    def __init__(self):
        self.__petri_net_obj: Union[PetriNet.Place, PetriNet.Transition, None] = None

    def petri_net_bound(self) -> Union[PetriNet.Place, PetriNet.Transition, None]:
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

    def set_hovered_pen(self, pen: QtGui.QPen):
        self.pnv_hover_pen = pen

    def set_hovered_brush(self, br: QtGui.QBrush):
        self.pnv_hover_brush = br

    def set_selected_pen(self, pen: QtGui.QPen):
        self.pnv_selected_pen = pen

    def set_selected_brush(self, br: QtGui.QBrush):
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


class PnvQGPlaceItem(QGraphicsEllipseItem, HoverSelectable, PetriNetBind, Markable):
    def __init__(self, *args, **kwargs):
        super(PetriNetBind, self).__init__()
        super(QGraphicsEllipseItem, self).__init__(*args, **kwargs)  # Universal constructor bypass
        self.setAcceptHoverEvents(True)
        super(HoverSelectable, self).__init__()
        super(Markable, self).__init__()
        #
        self.setPen(QtGui.QPen(QtGui.QColor('black'), 3))
        self.setBrush(QtGui.QBrush(QtGui.QColor('white')))

        self.set_hovered_brush(QtGui.QBrush(QtGui.QColor('lightGray')))
        self.set_selected_brush(QtGui.QBrush(QtGui.QColor(0xafadff)))
        # arrows holder
        self.__arrows: set[PnvQGArrowItem] = set()

    def arrows(self) -> set['PnvQGArrowItem']:
        return self.__arrows

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
        if self.final:
            offset = 4 * painter.pen().width()
            sub = QRectF(self.rect().x() + offset // 2, self.rect().y() + offset // 2,
                         self.rect().width() - offset, self.rect().height() - offset)
            painter.drawEllipse(sub)
        elif self.markings > 0:
            painter.setBrush(QBrush(QColor('0x000000')))
            if self.markings == 1:
                one = QRectF(self.rect().x() + self.rect().width() // 2 - self.rect().width() // 6,
                             self.rect().y() + self.rect().height() // 2 - self.rect().height() // 6,
                             self.rect().width() // 3, self.rect().height() // 3)
                painter.drawEllipse(one)
            elif self.markings == 2:
                rect = QRectF(self.rect().x() + self.rect().width() // 2 - self.rect().width() // 6,
                              self.rect().y() + self.rect().height() // 2 - self.rect().height() // 6,
                              self.rect().width() // 3, self.rect().height() // 3)
                one = rect.translated(-(rect.width() // 2 + rect.width() // 4), 0)
                two = rect.translated(rect.width() // 2 + rect.width() // 4, 0)
                painter.drawEllipse(one)
                painter.drawEllipse(two)
            elif self.markings == 3:
                rect = QRectF(self.rect().x() + self.rect().width() // 2 - self.rect().width() // 8,
                              self.rect().y() + self.rect().height() // 2 - self.rect().height() // 8,
                              self.rect().width() // 4, self.rect().height() // 4)
                one = rect.translated(-0.866 * rect.width(),
                                      -0.5 * rect.width())
                two = rect.translated(0.866 * rect.width(),
                                      -0.5 * rect.width())
                three = rect.translated(0, rect.width())
                painter.drawEllipse(one)
                painter.drawEllipse(two)
                painter.drawEllipse(three)
            elif self.markings == 4:
                rect = QRectF(self.rect().x() + self.rect().width() // 2 - self.rect().width() // 8,
                              self.rect().y() + self.rect().height() // 2 - self.rect().height() // 8,
                              self.rect().width() // 4, self.rect().height() // 4)
                one = rect.translated(-0.707 * rect.width(),
                                      0.707 * rect.width())
                two = rect.translated(-0.707 * rect.width(),
                                      -0.707 * rect.width())
                three = rect.translated(0.707 * rect.width(),
                                        -0.707 * rect.width())
                four = rect.translated(0.707 * rect.width(),
                                       0.707 * rect.width())
                painter.drawEllipse(one)
                painter.drawEllipse(two)
                painter.drawEllipse(three)
                painter.drawEllipse(four)
            else:
                f = painter.font()
                text = str(self.markings)
                f.setPixelSize(int(self.rect().width() * 0.8 - 8*(len(text)-1)))
                painter.setFont(f)
                fm = QtGui.QFontMetrics(f)
                rect = fm.tightBoundingRect(text)
                painter.drawText(QtCore.QPointF(self.rect().x() + self.rect().width() // 2 - rect.width() // 2,
                                 self.rect().y() + self.rect().height() // 2 + rect.height() // 2), text)

    # def contextMenuEvent(self, event: Optional[QGraphicsSceneContextMenuEvent]) -> None:
    #     if self.petri_net_binded():
    #         place: PetriNet.Place = self.petri_net_binded()
    #         cmenu = QMenu(self.scene().parent())
    #         if not self.final:
    #             def _temp_set():
    #                 self.final = True
    #                 self.update()
    #
    #             cmenu.addAction('&Set final marking', _temp_set)
    #         else:
    #             def _temp_set():
    #                 self.final = False
    #                 self.update()
    #
    #             cmenu.addAction('&Set non-final marking', _temp_set)
    #         cmenu.exec(event.screenPos())
    #     super(PnvQGPlaceItem, self).contextMenuEvent(event)


class PnvQGTransitionItem(QGraphicsRectItem, HoverSelectable, PetriNetBind):

    def __init__(self, *args, **kwargs):
        super(PetriNetBind, self).__init__()
        super(QGraphicsRectItem, self).__init__(*args, *kwargs)  # Universal constructor bypass
        self.setAcceptHoverEvents(True)
        super(HoverSelectable, self).__init__()
        # arrows holder
        self.setPen(QtGui.QPen(QtGui.QColor('black'), 3))
        self.setBrush(QtGui.QBrush(QtGui.QColor('white')))
        self.set_hovered_brush(QtGui.QBrush(QtGui.QColor('lightGray')))
        self.set_selected_brush(QtGui.QBrush(QtGui.QColor(0xafafff)))
        #
        self.__arrows: set[PnvQGArrowItem] = set()
        self.drawer = None

    def arrows(self) -> set['PnvQGArrowItem']:
        return self.__arrows

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

    def petri_net_bind(self, obj: Union[PetriNet.Place, PetriNet.Transition]):
        if isinstance(obj, pnv.importer.epnml.ExtendedTransition):
            self.setPen(QtGui.QPen(QtGui.QColor('black'), 3, QtCore.Qt.PenStyle.DashLine))
        else:
            self.setPen(QtGui.QPen(QtGui.QColor('black'), 3))
        super().petri_net_bind(obj)

    def contextMenuEvent(self, event: Optional[QGraphicsSceneContextMenuEvent]) -> None:
        if self.petri_net_bound():
            trans: PetriNet.Transition = self.petri_net_bound()
            cmenu = QMenu(self.scene().parent())
            if isinstance(trans, pnv.importer.epnml.ExtendedTransition):
                cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp),
                                '&Раскрыть подсеть', self.open_subnet)
                cmenu.addSeparator()
            cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical), '&Удалить')
            cmenu.exec(event.screenPos())
        super(PnvQGTransitionItem, self).contextMenuEvent(event)

    def open_subnet(self):
        try:
            self.drawer.subnet_unwrap(self)
        except pnv.importer.epnml.EPNMLException as ex:
            from main import PnvMainWindow
            PnvMessageBoxes.warning(f"Невозможно раскрыть вложенную сеть!",
                                    f"{ex}",
                                    icon=PnvMainWindow.WINDOW_ICON).exec()


class PnvQGArrowItem(QGraphicsLineItem):
    def __init__(self, from_, to):
        self.from_: Union[PnvQGPlaceItem, PnvQGTransitionItem] = from_
        self.to: Union[PnvQGPlaceItem, PnvQGTransitionItem] = to
        line = QtCore.QLineF(*self.last_line())
        self._x1: float = 0
        self._y1: float = 0
        self._x2: float = 0
        self._y2: float = 0
        super(QGraphicsLineItem, self).__init__(line)
        self.setPen(QtGui.QPen(QtGui.QColor('black'), 3))

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
        if self.to is None and self.from_ is None:
            return self._x1, self._y1, self._x2, self._y2
        # TODO: somehow fix transition arrow
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
        return xy0[0] + s0[0] / 2, xy0[1] + s0[1] / 2, xy1[0] + s1[0] / 2, xy1[1] + + s1[1] / 2

    def update(self, rect: QtCore.QRectF = ...) -> None:
        self._x1, self._y1, self._x2, self._y2 = self.last_line()
        self.setLine(self._x1, self._y1, self._x2, self._y2)
        super(PnvQGArrowItem, self).update(rect)

    def shape(self) -> QtGui.QPainterPath:
        path = super(PnvQGArrowItem, self).shape()
        xy1 = self.to_bound()
        path.addRect(QtCore.QRectF(xy1[0] - 10, xy1[1] - 10, 20, 20))
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
        painter.drawLine(QtCore.QLineF(float(ln.x2() + rot1[0]), float(ln.y2() + rot1[1]), ln.x2(), ln.y2()))
        painter.drawLine(QtCore.QLineF(float(ln.x2() + rot2[0]), float(ln.y2() + rot2[1]), ln.x2(), ln.y2()))
        painter.drawLine(QtCore.QLineF(ln.x1(), ln.y1(), ln.x2(), ln.y2()))

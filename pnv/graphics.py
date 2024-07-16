from typing import Union, Optional

from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtCore import QRectF, QRect
from PyQt5.QtGui import QBrush, QColor, QTextCursor, QTextCharFormat
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsSceneContextMenuEvent, \
    QGraphicsSceneHoverEvent, QStyleOptionGraphicsItem, QWidget, QGraphicsRectItem, QMenu, QStyle, \
    QGraphicsLineItem, QGraphicsItem, QAbstractGraphicsShapeItem, QGraphicsTextItem
import math
import numpy as np
from pm4py import PetriNet

import pnv.importer.epnml
from pnv.utils import PnvMessageBoxes, PnvConfig


class Labeling:
    def __init__(self):
        self.__text_obj: Union[QGraphicsTextItem, None] = None
        self.__text: str = None

        self.__bg_overlap = False

    def _instance(self) -> Union['PnvQGTransitionItem', 'PnvQGPlaceItem']:
        raise NotImplementedError()

    def __remove_label(self):
        self._instance().scene().removeItem(self.__text_obj)
        self.__text_obj = None

    def text_offset(self) -> tuple[float, float]:
        x = self.__text_obj.rect().x()
        y = self.__text_obj.rect().y()
        obj = self._instance()

        w = QtGui.QFontMetrics(self.__text_obj.font()).width(self.__text)
        h = QtGui.QFontMetrics(self.__text_obj.font()).height()

        x -= obj.x() + int(obj.rect().x()) + w / 2
        y -= obj.y() + int(obj.rect().y()) - h
        return x, y

    def reset_label_effects(self):
        _format = QTextCharFormat()

        cursor = QTextCursor(self.__text_obj.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(_format)

        self.__bg_overlap = False

    def enable_label_outline(self):
        _format = QTextCharFormat()
        _format.setTextOutline(QtGui.QPen(QtGui.QColor('white'), 0.5))

        cursor = QTextCursor(self.__text_obj.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(_format)

    def update(self):
        if self.__bg_overlap:
            self.enable_bg_overlap()

    def enable_bg_overlap(self):
        self.__bg_overlap = True
        _format = QTextCharFormat()
        _format.setBackground(self.__text_obj.scene().backgroundBrush())

        cursor = QTextCursor(self.__text_obj.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(_format)

    def __add_label(self, label: str, offset: tuple[float, float]):
        text = self._instance().scene().addText(label, QtGui.QFont(PnvConfig.INSTANCE.text_font_family,
                                                                   PnvConfig.INSTANCE.text_font_size,
                                                                   PnvConfig.INSTANCE.text_font_weight))
        self.__text = label

        w = QtGui.QFontMetrics(text.font()).width(label)
        h = QtGui.QFontMetrics(text.font()).height()

        obj = self._instance()
        off_x, off_y = offset
        x, y = int(obj.rect().x() + off_x), int(obj.rect().y() + off_y)

        text.setPos(QtCore.QPointF(x - w / 2, y + h))
        text.setParentItem(self._instance())
        text.setAcceptHoverEvents(False)
        text.setZValue(1)
        self.__text_obj = text

    def set_label(self, label: str, offset: tuple[float, float] = (0, 0)):
        if self.__text_obj is None:
            if label is None or len(label.strip()) == 0:
                return
            else:
                self.__add_label(label, offset)
        else:
            if label is None or len(label.strip()) == 0:
                self.__remove_label()
            else:
                self.__remove_label()
                self.__add_label(label, offset)

    def set_visible(self, visible: bool):
        self.__text_obj.setVisible(visible)


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


class PnvInteractive:
    def __init__(self):
        self.__interactive = True
        self.set_interactive(True)
        # hovered props
        self.pnv_hover_pen: Union[QtGui.QPen, None] = None
        self.pnv_hover_brush: Union[QtGui.QBrush, None] = None
        self.pnv_is_hovered: bool = False
        # selected props
        self.pnv_selected_pen: Union[QtGui.QPen, None] = None
        self.pnv_selected_brush: Union[QtGui.QBrush, None] = None
        self.pnv_is_selected: bool = False

    def is_interactive(self):
        return self.__interactive

    def set_interactive(self, val: bool):
        self.__interactive = val
        if not isinstance(self, QGraphicsItem):
            return
        self.setAcceptHoverEvents(val)

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


class PnvQGPlaceItem(QGraphicsEllipseItem, PnvInteractive, PetriNetBind, Markable):
    def __init__(self, *args, **kwargs):
        PetriNetBind.__init__(self)
        QGraphicsEllipseItem.__init__(self, *args, **kwargs)  # Universal constructor bypass
        PnvInteractive.__init__(self)
        Markable.__init__(self)
        #
        self.setPen(QtGui.QPen(QtGui.QColor('black'), 3))
        self.setBrush(QtGui.QBrush(QtGui.QColor('white')))

        self.set_hovered_brush(QtGui.QBrush(QtGui.QColor('lightGray')))
        self.set_selected_brush(QtGui.QBrush(QtGui.QColor(0xafadff)))
        # arrows holder
        self.__arrows: set[PnvQGArrowItem] = set()
        self.drawer = None

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

    def draw_marked(self, painter: Optional[QtGui.QPainter]):
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
                f.setPixelSize(int(self.rect().width() * 0.8 - 8 * (len(text) - 1)))
                painter.setFont(f)
                fm = QtGui.QFontMetrics(f)
                rect = fm.tightBoundingRect(text)
                painter.drawText(QtCore.QPointF(self.rect().x() + self.rect().width() // 2 - rect.width() // 2,
                                                self.rect().y() + self.rect().height() // 2 + rect.height() // 2), text)

    def paint(self, painter: Optional[QtGui.QPainter], option: Optional['QStyleOptionGraphicsItem'],
              widget: Optional['QWidget'] = ...) -> None:
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawEllipse(self.rect())
        self.draw_marked(painter)

    def _ctxt_update_tokens(self):
        tokens, done = QtWidgets.QInputDialog.getInt(
            self.drawer.scene.activeWindow(),
            'Petri Net Viewer Dialog',
            '&Введите число фишек:',
            value=self.markings,
            min=0)
        if done:
            self.markings = tokens

            self.drawer.status.meta_data = True

    def _ctxt_update_fin(self, fin: bool):
        self.final = fin
        self.update()

        self.drawer.status.meta_data = True

    def contextMenuEvent(self, event: Optional[QGraphicsSceneContextMenuEvent]) -> None:
        if not self.is_interactive():
            return
        if not self.petri_net_bound():
            return
        cmenu = QMenu(self.scene().parent())

        if not self.final:
            cmenu.addAction('&Назначить фишки', lambda: self._ctxt_update_tokens())
            cmenu.addAction('&Отметить конечной', lambda: self._ctxt_update_fin(True))
        else:
            cmenu.addAction('&Убрать конечную метку', lambda: self._ctxt_update_fin(False))
        cmenu.addSeparator()
        cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical), '&Удалить',
                        self.remove_item)
        cmenu.exec(event.screenPos())
        super(PnvQGPlaceItem, self).contextMenuEvent(event)

    def remove_item(self):
        self.drawer.place_remove(self)


class PnvQGTransitionItem(QGraphicsRectItem, PnvInteractive, PetriNetBind, Labeling):

    def __init__(self, *args, **kwargs):
        PetriNetBind.__init__(self)
        QGraphicsRectItem.__init__(self, *args, *kwargs)  # Universal constructor bypass
        PnvInteractive.__init__(self)
        Labeling.__init__(self)
        # arrows holder
        self.setPen(QtGui.QPen(QtGui.QColor('black'), 3))
        self.setBrush(QtGui.QBrush(QtGui.QColor('white')))
        self.set_hovered_brush(QtGui.QBrush(QtGui.QColor('lightGray')))
        self.set_selected_brush(QtGui.QBrush(QtGui.QColor(0xafafff)))
        #
        self.__arrows: set[PnvQGArrowItem] = set()
        self.only_wuw = False
        self.drawer = None

    def _instance(self) -> QAbstractGraphicsShapeItem:
        return self

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

    def _ctxt_change_label(self):
        txt, done = QtWidgets.QInputDialog.getText(
            self.drawer.scene.activeWindow(),
            'Petri Net Viewer Dialog',
            '&Ярлык:',
            text=self.petri_net_bound().label)
        if done:
            self.petri_net_bound().label = txt
            w, h = self.petri_net_bound().properties['layout_information_petri'][1]
            self.set_label(self.petri_net_bound().label, (w / 2, h / 2))

            self.drawer.status.meta_data = True

    def contextMenuEvent(self, event: Optional[QGraphicsSceneContextMenuEvent]) -> None:
        if not self.is_interactive():
            return
        if not self.petri_net_bound():
            return
        trans: PetriNet.Transition = self.petri_net_bound()
        # special mode
        if self.only_wuw:
            if not isinstance(trans, pnv.importer.epnml.ExtendedTransition):
                return
            cmenu = QMenu(self.scene().parent())
            cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp),
                            '&Раскрыть подсеть', self.open_subnet)
            cmenu.exec(event.screenPos())
            super(PnvQGTransitionItem, self).contextMenuEvent(event)
            return
        cmenu = QMenu(self.scene().parent())
        cmenu.addAction('&Назначить ярлык', lambda: self._ctxt_change_label())
        cmenu.addSeparator()
        if isinstance(trans, pnv.importer.epnml.ExtendedTransition):
            cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp),
                            '&Раскрыть подсеть', self.open_subnet)
            cmenu.addSeparator()
        cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical), '&Удалить',
                        self.remove_item)
        cmenu.exec(event.screenPos())
        super(PnvQGTransitionItem, self).contextMenuEvent(event)

    def remove_item(self):
        self.drawer.transition_remove(self)

    def open_subnet(self):
        try:
            self.drawer.subnet_unwrap(self)
        except pnv.importer.epnml.EPNMLException as ex:
            from main import PnvMainWindow
            PnvMessageBoxes.warning(f"Невозможно раскрыть вложенную сеть!",
                                    f"{ex}",
                                    icon=PnvMainWindow.WINDOW_ICON).exec()

    def sync_labeling(self):
        Labeling.update(self)


class PnvQGArrowItem(QGraphicsLineItem):
    def __init__(self, from_, to):
        self.from_: Union[PnvQGPlaceItem, PnvQGTransitionItem] = from_
        self.to: Union[PnvQGPlaceItem, PnvQGTransitionItem] = to
        line = QtCore.QLineF(*self.last_line())
        self._x1: float = 0
        self._y1: float = 0
        self._x2: float = 0
        self._y2: float = 0
        QGraphicsLineItem.__init__(self, line)
        self.setPen(QtGui.QPen(QtGui.QColor(0x000000), 3))
        self.dead = False

        self.setZValue(-1)

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

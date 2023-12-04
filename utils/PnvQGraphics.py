import typing

from PyQt5 import Qt, QtGui
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsSceneContextMenuEvent, \
    QGraphicsSceneHoverEvent, QStyleOptionGraphicsItem, QWidget


class PnvQGEllipseItem(QGraphicsEllipseItem):

    def __init__(self, *args, **kwargs):
        super(QGraphicsEllipseItem, self).__init__(*args, *kwargs)  # Universal constructor bypass
        self.pnv_hover_pen: typing.Union[QtGui.QPen, None] = None
        self.pnv_hover_brush: typing.Union[QtGui.QBrush, None] = None
        self.pnv_is_hovered: bool = False
        self.setAcceptHoverEvents(True)

    def set_hovered_pen(self, pen: Qt.QPen):
        self.pnv_hover_pen = pen

    def set_hovered_brush(self, br: Qt.QBrush):
        self.pnv_hover_brush = br

    def pen(self) -> QtGui.QPen:
        if self.pnv_is_hovered and self.pnv_hover_pen is not None:
            return self.pnv_hover_pen
        return super().pen()

    def brush(self) -> QtGui.QBrush:
        if self.pnv_is_hovered and self.pnv_hover_brush is not None:
            return self.pnv_hover_brush
        return super().brush()

    def hover_leave_manually(self):
        self.pnv_is_hovered = False
        self.update()

    def hover_enter_manually(self):
        self.pnv_is_hovered = True
        self.update()

    def hoverLeaveEvent(self, event: typing.Optional['QGraphicsSceneHoverEvent']) -> None:
        self.pnv_is_hovered = False
        super().hoverLeaveEvent(event)

    def hoverEnterEvent(self, event: typing.Optional['QGraphicsSceneHoverEvent']) -> None:
        self.pnv_is_hovered = True
        super().hoverEnterEvent(event)

    def paint(self, painter: typing.Optional[QtGui.QPainter], option: typing.Optional['QStyleOptionGraphicsItem'],
              widget: typing.Optional['QWidget'] = ...) -> None:
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawEllipse(self.rect())

    def contextMenuEvent(self, event: typing.Optional[QGraphicsSceneContextMenuEvent]) -> None:
        #     cmenu = QMenu(self.scene().parent())
        #     cmenu.addAction('&ACTION')
        #     cmenu.exec(event.screenPos())
        # fix hovering as well
        # MIGHT BE USED
        super(PnvQGEllipseItem, self).contextMenuEvent(event)


class PnvQGRectItem(QGraphicsRectItem):

    def __init__(self, *args, **kwargs):
        super(QGraphicsRectItem, self).__init__(*args, *kwargs)  # Universal constructor bypass
        self.pnv_hover_pen: typing.Union[QtGui.QPen, None] = None
        self.pnv_hover_brush: typing.Union[QtGui.QBrush, None] = None
        self.pnv_is_hovered = False
        self.setAcceptHoverEvents(True)

    def set_hovered_pen(self, pen: Qt.QPen):
        self.pnv_hover_pen = pen

    def set_hovered_brush(self, br: Qt.QBrush):
        self.pnv_hover_brush = br

    def pen(self) -> QtGui.QPen:
        if self.pnv_is_hovered and self.pnv_hover_pen is not None:
            return self.pnv_hover_pen
        return super().pen()

    def brush(self) -> QtGui.QBrush:
        if self.pnv_is_hovered and self.pnv_hover_brush is not None:
            return self.pnv_hover_brush
        return super().brush()

    def hover_leave_manually(self):
        self.pnv_is_hovered = False
        self.update()

    def hover_enter_manually(self):
        self.pnv_is_hovered = True
        self.update()

    def hoverLeaveEvent(self, event: typing.Optional['QGraphicsSceneHoverEvent']) -> None:
        self.pnv_is_hovered = False
        super().hoverLeaveEvent(event)

    def hoverEnterEvent(self, event: typing.Optional['QGraphicsSceneHoverEvent']) -> None:
        self.pnv_is_hovered = True
        super().hoverEnterEvent(event)

    def paint(self, painter: typing.Optional[QtGui.QPainter], option: typing.Optional['QStyleOptionGraphicsItem'],
              widget: typing.Optional['QWidget'] = ...) -> None:
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())

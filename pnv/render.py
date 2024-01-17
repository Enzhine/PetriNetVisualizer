from typing import Union, Optional, Tuple

from PyQt5 import Qt, QtCore, QtGui
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsView, QApplication
from pm4py import PetriNet
from igraph import Graph

from pnv.graphics import PnvQGTransitionItem, PnvQGPlaceItem, PnvQGArrowItem
from pnv.utils import PnvMessageBoxes

Layout = Tuple[Tuple[int, int], Tuple[int, int]]


class PnvDrawer:
    PLACE_PEN_WIDTH = 3
    GRAPHICS_WIDTH = 40

    def __init__(self, scene: QGraphicsScene, net: PetriNet):
        self.scene = scene
        self.net = net
        self.mapper: dict[Union[PetriNet.Place, PetriNet.Transition], Union[PnvQGTransitionItem, PnvQGPlaceItem]] = dict()
        self.edited_status = False

    def draw_place_directly(self, x: int, y: int, r: int) -> PnvQGPlaceItem:
        # custom ellipse init
        obj = PnvQGPlaceItem(Qt.QRectF(x - r / 2, y - r / 2, r, r))
        obj.setPen(Qt.QPen(Qt.Qt.black, PnvDrawer.PLACE_PEN_WIDTH))
        obj.setBrush(Qt.QBrush(Qt.Qt.white))

        obj.set_hovered_brush(Qt.QBrush(Qt.Qt.lightGray))
        obj.set_selected_brush(Qt.QBrush(Qt.QColor(0xafadff)))

        self.scene.addItem(obj)
        return obj

    def draw_transition_directly(self, x: int, y: int, w: int, h: int, label: str = None) -> PnvQGTransitionItem:
        # custom rectangle init
        obj = PnvQGTransitionItem(Qt.QRectF(x - w / 2, y - h / 2, w, h))
        obj.setPen(Qt.QPen(Qt.Qt.black, PnvDrawer.PLACE_PEN_WIDTH))
        obj.setBrush(Qt.QBrush(Qt.Qt.white))

        obj.set_hovered_brush(Qt.QBrush(Qt.Qt.lightGray))
        obj.set_selected_brush(Qt.QBrush(Qt.QColor(0xafafff)))

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

    def draw_place(self, p: PetriNet.Place) -> QGraphicsEllipseItem:
        pos, shape = self.layout(p)
        obj = self.draw_place_directly(*pos, shape[0])
        obj.petri_net_bind(p)
        return obj

    def draw_transition(self, t: PetriNet.Transition) -> QGraphicsRectItem:
        pos, shape = self.layout(t)
        obj = self.draw_transition_directly(*pos, *shape, t.label)
        obj.petri_net_bind(t)
        return obj

    def draw_arc(self, from_: Union[PetriNet.Place, PetriNet.Transition],
                 to: Union[PetriNet.Place, PetriNet.Transition]) -> PnvQGArrowItem:
        obj = PnvQGArrowItem(self.mapper[from_], self.mapper[to])
        obj.setPen(Qt.QPen(Qt.Qt.black, PnvDrawer.PLACE_PEN_WIDTH))
        self.scene.addItem(obj)
        return obj

    @staticmethod
    def has_layout(obj):
        return hasattr(obj, 'properties') and ('layout_information_petri' in obj.properties) \
               and isinstance(obj.properties['layout_information_petri'], tuple)

    @staticmethod
    def inject_layout(obj, layout: Layout):
        if PnvDrawer.has_layout(obj):
            raise ValueError("Layout injection can not be applied to object containing layout!")
        if not hasattr(obj, 'properties'):
            setattr(obj, 'properties', dict())
        if not ('layout_information_petri' in obj.properties):
            obj.properties['layout_information_petri'] = layout

    @staticmethod
    def layout(obj) -> Layout:
        return obj.properties['layout_information_petri']

    def draw_petri_net(self):
        if not all(self.has_layout(obj) for obj in [*self.net.places, *self.net.transitions]):
            from main import PnvMainWindow
            if not PnvMessageBoxes.is_accepted(
                    PnvMessageBoxes.accept_msg(f"Загруженная сеть не имеет предопределённую разметку.",
                                               f"Сгенерировать разметку сети?",
                                               icon=PnvMainWindow.WINDOW_ICON).exec()):
                raise TypeError(PnvMainWindow.RENDER_CANCELLED)
            else:
                self.igraph_gen_layout()
                self.edited_status = True
        for p in self.net.places:
            self.mapper[p] = self.draw_place(p)
        for t in self.net.transitions:
            self.mapper[t] = self.draw_transition(t)
        for a in self.net.arcs:
            obj = self.draw_arc(a.source, a.target)
            self.mapper[a.source].arrows.add(obj)
            self.mapper[a.target].arrows.add(obj)

    def igraph_gen_layout(self):
        n_vertices = len(self.net.places) + len(self.net.transitions)
        local_mapper: dict[Union[PetriNet.Place, PetriNet.Transition], int] = dict()
        local_mapper_re: dict[int, Union[PetriNet.Place, PetriNet.Transition]] = dict()  # just complexity optimization
        c = 0
        for obj in self.net.places:
            local_mapper[obj] = c
            local_mapper_re[c] = obj
            c += 1
        for obj in self.net.transitions:
            local_mapper[obj] = c
            local_mapper_re[c] = obj
            c += 1
        edges = [(local_mapper[a.source], local_mapper[a.target]) for a in self.net.arcs]
        g = Graph(n_vertices, edges)
        layout = g.layout(layout='auto')
        # scaling
        b = layout.boundaries()
        dx = b[1][0] - b[0][0]
        dy = b[1][1] - b[0][1]
        from main import PnvMainWindow
        if dx > dy:
            k = PnvMainWindow.WINDOW_MIN_WIDTH / dx
        else:
            k = PnvMainWindow.WINDOW_MIN_HEIGHT / dy
        layout.scale(k)
        # injection
        for i, gen in enumerate(layout):
            lay = ((gen[0], gen[1]), (PnvDrawer.GRAPHICS_WIDTH, PnvDrawer.GRAPHICS_WIDTH))
            PnvDrawer.inject_layout(local_mapper_re[i], lay)


def mod(num: int, other: int):
    return -abs(num % other)


class PnvViewer(QGraphicsView):
    BG_PX_GRID = 100
    BG_BRUSH = Qt.QBrush(Qt.QColor(0xdadada))
    GRID_PEN = Qt.QPen(Qt.QBrush(Qt.QColor(0xadadad)), 1)

    def __init__(self, *args, **kwargs):
        super(QGraphicsView, self).__init__(*args, *kwargs)  # Universal constructor bypass
        # props
        self.inwards = 1.1  # Mouse scroll scale factor
        self.outwards = 1 / self.inwards
        self.last_rmp: Union[Qt.QPoint, None] = None  # For right mouse press
        self.last_lmp: Union[Qt.QPoint, None] = None  # For left mouse press
        self.selection: Union[QGraphicsRectItem, None] = None
        self.selected_items: set[Union[PnvQGTransitionItem, PnvQGPlaceItem]] = set()
        self.extra_selected_items: set[Union[PnvQGTransitionItem, PnvQGPlaceItem]] = set()
        self.moved_selected = False
        self.scaler = 0

        self.edited_status = False
        # settings
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.horizontalScrollBar().setEnabled(False)
        self.verticalScrollBar().setEnabled(False)

    def scale_factor(self):
        return self.inwards ** self.scaler

    def wheelEvent(self, e: Optional[QtGui.QWheelEvent]) -> None:
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

    def mousePressEvent(self, e: Optional[QtGui.QMouseEvent]) -> None:
        if e.button() in [Qt.Qt.RightButton, Qt.Qt.MiddleButton]:  # RMC press
            # setting hold
            self.last_rmp = e.pos()
            # cursor override logic
            QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.ClosedHandCursor)
        elif e.button() == Qt.Qt.LeftButton and self.last_rmp is None:
            # try interact
            clicked = self.scene().itemAt(self.mapToScene(e.pos()), self.viewportTransform())
            clicked = clicked if isinstance(clicked, PnvQGPlaceItem) or isinstance(clicked, PnvQGTransitionItem) else None
            # setting hold
            self.last_lmp = self.mapToScene(e.pos())
            if clicked:
                # try to select more
                self.extra_selected_items = self.selected_items
                self.selected_items = set()
                self.selected_add(clicked)
            else:
                mods = QApplication.keyboardModifiers()
                if not (mods == QtCore.Qt.KeyboardModifier.ShiftModifier):
                    self.deselect_all(self.selected_items)
                    self.extra_selected_items = set()
                else:
                    self.extra_selected_items = self.selected_items
                    self.selected_items = set()
                # enable selection if None objects were clicked
                self.selection = self.scene().addRect(Qt.QRectF(self.last_lmp.x(), self.last_lmp.y(), 1, 1),
                                                      Qt.QPen(Qt.Qt.darkCyan, 1, Qt.Qt.DashLine))
                # cursor override logic
                QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.CrossCursor)
        # firing event at super
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: Optional[QtGui.QMouseEvent]) -> None:
        if e.button() in [Qt.Qt.RightButton, Qt.Qt.MiddleButton] and self.last_rmp is not None:  # RMC release
            # resetting hold
            self.last_rmp = None
            # cursor override logic
            if self.last_lmp is None:
                QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.ArrowCursor)
            else:
                QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.CrossCursor)
        elif e.button() == Qt.Qt.LeftButton:  # LMC release
            if self.selection is None:
                if not self.moved_selected:  # almost click
                    self.deselect_all(self.extra_selected_items)
                else:
                    self.selected_items |= self.extra_selected_items
                    self.moved_selected = False
            else:
                self.scene().removeItem(self.selection)
                self.selection = None
                self.scene().update()
                self.selection_completed()
            # resetting hold
            self.last_lmp = None
            # cursor override logic
            if self.last_rmp is None:
                QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.ArrowCursor)
            else:
                QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.ClosedHandCursor)
        # firing event at super
        super().mouseReleaseEvent(e)

    def selection_completed(self) -> None:
        self.selected_items |= self.extra_selected_items

    def mouseMoveEvent(self, e: Optional[QtGui.QMouseEvent]) -> None:
        if self.last_rmp is not None:  # RMC hold
            delta = self.last_rmp - e.pos()
            self.setSceneRect(
                self.sceneRect().translated(delta.x() / self.transform().m11(), delta.y() / self.transform().m22())
            )
            self.last_rmp = e.pos()
        if self.last_lmp is not None:  # LMC hold
            cur = self.mapToScene(e.pos())  # current pos
            to = cur - self.last_lmp  # from to
            if self.selection:
                # if mouse moving while selecting
                self.selection.setRect(Qt.QRectF(min(self.last_lmp.x(), self.last_lmp.x() + to.x()),
                                                 min(self.last_lmp.y(), self.last_lmp.y() + to.y()),
                                                 abs(to.x()),
                                                 abs(to.y())))
                # find selectable
                collides: set[Union[PnvQGTransitionItem, PnvQGPlaceItem]] = \
                    set([o for o in self.selection.collidingItems(Qt.Qt.IntersectsItemBoundingRect)
                         if isinstance(o, PnvQGTransitionItem) or isinstance(o, PnvQGPlaceItem)])
                # differentiate whether selected or not
                lost = self.selected_items - collides
                new = collides - self.selected_items
                # force select
                for i in lost:
                    self.deselect(i)
                for i in new:
                    self.selected_add(i)
                # update selected
                self.selected_items = collides
            else:
                # to this moment all possible selection moves to extra
                if len(self.selected_items) != 1:
                    print(f'MULTIPLE OBJECTS MOVE: {len(self.selected_items)}')
                    raise Exception('MULTIPLE OBJECTS MOVE')
                last, *_ = self.selected_items  # clicked object
                last: Union[PnvQGTransitionItem, PnvQGPlaceItem]
                if last in self.extra_selected_items:
                    # move all selected
                    arrows = set()
                    for i in self.extra_selected_items:
                        i.setX(i.x() + to.x())
                        i.setY(i.y() + to.y())
                        arrows |= i.arrows
                    for arr in arrows:
                        arr.update(arr.boundingRect())
                else:
                    # deselect other pre-selected
                    if len(self.extra_selected_items) != 0:
                        self.deselect_all(self.extra_selected_items)
                    # move one
                    last.setX(last.x() + to.x())
                    last.setY(last.y() + to.y())
                    for arr in last.arrows:
                        arr.update(arr.boundingRect())
                if not self.moved_selected:
                    QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.SizeAllCursor)
                    self.moved_selected = True
                    self.edited_status = True
                self.last_lmp = cur
        super().mouseMoveEvent(e)

    def selected_add(self, obj: Union[PnvQGTransitionItem, PnvQGPlaceItem]) -> None:
        self.selected_items.add(obj)
        obj.select_manually()

    def deselect(self, obj: Union[PnvQGTransitionItem, PnvQGPlaceItem]) -> None:
        self.selected_items.remove(obj)
        obj.deselect_manually()

    @staticmethod
    def deselect_all(objs: set[Union[PnvQGTransitionItem, PnvQGPlaceItem]]) -> None:
        for obj in objs:
            obj.deselect_manually()
        objs.clear()

    def drawBackground(self, painter: Optional[QtGui.QPainter], rect: QtCore.QRectF) -> None:
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

    def inject_all_positions(self):
        for obj in self.items():
            if not isinstance(obj, (PnvQGPlaceItem, PnvQGTransitionItem)):
                continue
            bind = obj.petri_net_binded()
            if not obj:
                continue
            lay: Layout = PnvDrawer.layout(bind)
            new_lay = ((int(obj.rect().x() + lay[1][0] / 2) + obj.x(), int(obj.rect().y() + lay[1][1] / 2) + obj.y()), (lay[1][0], lay[1][1]))
            if new_lay == lay:
                continue
            bind.properties['layout_information_petri'] = new_lay

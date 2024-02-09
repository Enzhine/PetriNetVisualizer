import time
from typing import Union, Optional, Tuple

from PyQt5 import Qt, QtCore, QtGui
from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsRectItem, QGraphicsView, QApplication, QMenu, \
    QStyle, QPushButton
from pm4py import PetriNet
from igraph import Graph

import pnv.importer.epnml
from pnv.graphics import PnvQGTransitionItem, PnvQGPlaceItem, PnvQGArrowItem
from pnv.importer.epnml import ExtendedTransition
from pnv.utils import PnvMessageBoxes

Layout = Tuple[Tuple[int, int], Tuple[int, int]]


class PnvDrawer:
    GRAPHICS_WIDTH = 40

    def __init__(self, scene: QGraphicsScene, net: PetriNet):
        self.scene = scene
        self.net = net
        self.mapper: dict[Union[PetriNet.Place, PetriNet.Transition],
        Union[PnvQGTransitionItem, PnvQGPlaceItem]] = dict()
        self.edited_status = False

    def draw_place_directly(self, x: int, y: int, r: int) -> PnvQGPlaceItem:
        # custom ellipse init
        obj = PnvQGPlaceItem(QtCore.QRectF(x - r / 2, y - r / 2, r, r))
        self.scene.addItem(obj)
        return obj

    def draw_transition_directly(self, x: int, y: int, w: int, h: int, label: str = None) -> PnvQGTransitionItem:
        # custom rectangle init
        obj = PnvQGTransitionItem(QtCore.QRectF(x - w / 2, y - h / 2, w, h))
        self.scene.addItem(obj)
        if label:
            text = self.scene.addText(label)
            w = QtGui.QFontMetrics(text.font()).width(label)
            h = QtGui.QFontMetrics(text.font()).height()
            text.setPos(QtCore.QPointF(x - w / 2, y + h))
            # binding text, but not events
            text.setParentItem(obj)
            text.setAcceptHoverEvents(False)
        return obj

    def draw_place(self, p: PetriNet.Place) -> PnvQGPlaceItem:
        pos, shape = self.layout(p)
        obj = self.draw_place_directly(*pos, shape[0])
        obj.petri_net_bind(p)
        return obj

    def draw_transition(self, t: PetriNet.Transition) -> PnvQGTransitionItem:
        pos, shape = self.layout(t)
        obj = self.draw_transition_directly(*pos, *shape, t.label)
        obj.drawer = self
        obj.petri_net_bind(t)
        return obj

    def draw_arc(self, from_: Union[PetriNet.Place, PetriNet.Transition],
                 to: Union[PetriNet.Place, PetriNet.Transition]) -> PnvQGArrowItem:
        obj = PnvQGArrowItem(self.mapper[from_], self.mapper[to])
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
            PnvMessageBoxes.proceed(f"Загруженная сеть не имеет предопределённую разметку!",
                                    f"Будет произведена генерация автоматической разметки.",
                                    icon=PnvMainWindow.WINDOW_ICON).exec()
            self.igraph_gen_layout(self.net)
            self.edited_status = True
        for p in self.net.places:
            self.mapper[p] = self.draw_place(p)
        for t in self.net.transitions:
            self.mapper[t] = self.draw_transition(t)
        for a in self.net.arcs:
            obj = self.draw_arc(a.source, a.target)
            self.mapper[a.source].arrows().add(obj)
            self.mapper[a.target].arrows().add(obj)

    def igraph_gen_layout(self, pn: PetriNet):
        n_vertices = len(pn.places) + len(pn.transitions)
        local_mapper: dict[Union[PetriNet.Place, PetriNet.Transition], int] = dict()
        local_mapper_re: dict[int, Union[PetriNet.Place, PetriNet.Transition]] = dict()  # just complexity optimization
        c = 0
        for obj in pn.places:
            local_mapper[obj] = c
            local_mapper_re[c] = obj
            c += 1
        for obj in pn.transitions:
            local_mapper[obj] = c
            local_mapper_re[c] = obj
            c += 1
        edges = [(local_mapper[a.source], local_mapper[a.target]) for a in pn.arcs if
                 (a.source in local_mapper and a.target in local_mapper)]
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

    def subnet_unwrap(self, trans_obj: PnvQGTransitionItem):
        extr: PetriNet.Transition = trans_obj.petri_net_bound()

        # unwrappability verification
        if not isinstance(extr, ExtendedTransition):
            raise pnv.importer.epnml.EPNMLException('Attempt to unwrap not unwrappable!')
        extr: ExtendedTransition

        # innerity verification
        wrapped_net = extr.inner_net
        for p in wrapped_net.places:
            if p in self.mapper:
                raise pnv.importer.epnml.EPNMLException(
                    f'Inner Petri net intersects with outer Petri net (Place): {p}!')
        for t in wrapped_net.transitions:
            if t in self.mapper:
                raise pnv.importer.epnml.EPNMLException(
                    f'Inner Petri net intersects with outer Petri net (Transition): {t}!')
        for a in wrapped_net.arcs:
            if (a.source in self.mapper) and (a.target in self.mapper):
                raise pnv.importer.epnml.EPNMLException(
                    f'Inner Petri net intersects with outer Petri net (Outer arc): {a}!')

        # cutting old components
        # # gui arcs remove
        for arrow in trans_obj.arrows():
            if arrow.from_ is trans_obj:
                # target is outer
                arrow.to.arrows().remove(arrow)
            elif arrow.to is trans_obj:
                # source is outer
                arrow.from_.arrows().remove(arrow)
            arrow.hide()
            self.scene.removeItem(arrow)  # delete from gui
        # # petri net arcs remove
        for out_arc in extr.out_arcs:
            # target is outer
            out_arc: PetriNet.Arc
            out_arc.target.in_arcs.remove(out_arc)
            self.net.arcs.remove(out_arc)  # delete from net
        for in_arc in extr.in_arcs:
            # source is outer
            in_arc: PetriNet.Arc
            in_arc.source.out_arcs.remove(in_arc)
            self.net.arcs.remove(in_arc)  # delete from net
        # #  gui transition remove
        self.scene.removeItem(trans_obj)
        # # petri net transition remove
        self.net.transitions.remove(extr)

        # injecting wrapped net
        # # layout gen
        if not all(self.has_layout(obj) for obj in [*wrapped_net.places, *wrapped_net.transitions]):
            self.igraph_gen_layout(wrapped_net)
            self.edited_status = True
        # # places inject
        for p in wrapped_net.places:
            # gui
            self.mapper[p] = self.draw_place(p)
            # net
            self.net.places.add(p)
        # # transitions inject
        for t in wrapped_net.transitions:
            # gui
            self.mapper[t] = self.draw_transition(t)
            # net
            self.net.transitions.add(t)
        # # arcs inject
        for a in wrapped_net.arcs:
            # gui
            obj = self.draw_arc(a.source, a.target)
            obj.to.arrows().add(obj)
            obj.from_.arrows().add(obj)
            # net
            self.net.arcs.add(a)
            a.target.in_arcs.add(a)
            a.source.out_arcs.add(a)

        # overall scene update
        self.scene.update()

    def subnet_wrap(self, objs: set[Union[PnvQGTransitionItem, PnvQGPlaceItem]]):
        # wrappability verification
        if len(objs) <= 1:
            raise pnv.importer.epnml.EPNMLException('Attempt to wrap empty or single-object net!')

        # define outer objs
        outer_to_objs = set()
        outer_from_objs = set()
        total_arrows: set[PnvQGArrowItem] = set().union(*[obj.arrows() for obj in objs])  # all arrows
        boundary_transitions = True
        for arrow in total_arrows:
            if not (arrow.to in objs):
                outer_to_objs.add(arrow.to)
                boundary_transitions = boundary_transitions and isinstance(arrow.from_, PnvQGTransitionItem)
            elif not (arrow.from_ in objs):
                outer_from_objs.add(arrow.from_)
                boundary_transitions = boundary_transitions and isinstance(arrow.to, PnvQGTransitionItem)
        # boundary verification
        if not boundary_transitions:
            raise pnv.importer.epnml.EPNMLException('Boundary objects must be transitions!')

        # wrappability verification-2
        if len(outer_to_objs) + len(outer_from_objs) == 0:
            raise pnv.importer.epnml.EPNMLException('Attempt to wrap entire net!')

        # future transition place
        objs_poses = [PnvDrawer.final_pos(o) for o in objs]
        min_bx = min([p[0] for p in objs_poses])
        min_by = min([p[1] for p in objs_poses])
        max_bx = max([p[0] for p in objs_poses])
        max_by = max([p[1] for p in objs_poses])
        objs_center = (min_bx + (max_bx - min_bx) / 2, min_by + (max_by - min_by) / 2)

        # creating wrapped net
        places: set[PetriNet.Place] = set()
        transitions: set[PetriNet.Transition] = set()
        arcs: set[PetriNet.Arc] = set()
        for obj in objs:
            bound = obj.petri_net_bound()
            # updating layout
            lay = PnvDrawer.layout(bound)
            lay = (PnvDrawer.final_pos(obj), lay[1])
            bound.properties['layout_information_petri'] = lay
            # adding places and transitions
            if isinstance(bound, PetriNet.Place):
                places.add(bound)
            elif isinstance(bound, PetriNet.Transition):
                transitions.add(bound)
            # adding arcs
            for arc in bound.in_arcs:
                arcs.add(arc)
            for arc in bound.out_arcs:
                arcs.add(arc)
        wrapped_net = PetriNet('wrapped_net_' + str(time.time()), places, transitions, arcs)

        # cutting old components
        # # gui arcs remove
        for arrow in total_arrows:
            for obj in outer_to_objs:
                if arrow in obj.arrows():
                    obj.arrows().remove(arrow)
            for obj in outer_from_objs:
                if arrow in obj.arrows():
                    obj.arrows().remove(arrow)
            arrow.hide()
            self.scene.removeItem(arrow)
        # # petri net arcs remove
        for arc in arcs:
            for obj in outer_to_objs:
                bound = obj.petri_net_bound()
                if arc in bound.in_arcs:
                    bound.in_arcs.remove(arc)
            for obj in outer_from_objs:
                bound = obj.petri_net_bound()
                if arc in bound.out_arcs:
                    bound.out_arcs.remove(arc)
            self.net.arcs.remove(arc)
        # # gui places and transitions remove
        for obj in objs:
            del self.mapper[obj.petri_net_bound()]
            self.scene.removeItem(obj)
        # # petri net places and transitions remove
        for obj in objs:
            bound = obj.petri_net_bound()
            if isinstance(bound, PetriNet.Place):
                self.net.places.remove(bound)
            elif isinstance(bound, PetriNet.Transition):
                self.net.transitions.remove(bound)

        # adding new objects
        # # petri net
        extr = ExtendedTransition('g_' + str(time.time()), 'wrapped')
        extr.inject_net(wrapped_net)
        PnvDrawer.inject_layout(extr, (objs_center, (PnvDrawer.GRAPHICS_WIDTH, PnvDrawer.GRAPHICS_WIDTH)))
        new_arcs = []
        for obj in outer_to_objs:
            bound = obj.petri_net_bound()
            arc = PetriNet.Arc(extr, bound)
            new_arcs.append(arc)

            bound.in_arcs.add(arc)
            extr.out_arcs.add(arc)

            self.net.arcs.add(arc)
        for obj in outer_from_objs:
            bound = obj.petri_net_bound()
            arc = PetriNet.Arc(bound, extr)
            new_arcs.append(arc)

            bound.out_arcs.add(arc)
            extr.in_arcs.add(arc)

            self.net.arcs.add(arc)
        self.net.transitions.add(extr)
        # # gui
        self.mapper[extr] = self.draw_transition(extr)
        for arc in new_arcs:
            arrow = self.draw_arc(arc.source, arc.target)
            arrow.to.arrows().add(arrow)
            arrow.from_.arrows().add(arrow)

        # overall scene update
        self.scene.update()

    @staticmethod
    def final_pos(obj: Union[PnvQGTransitionItem, PnvQGPlaceItem]):
        lay = PnvDrawer.layout(obj.petri_net_bound())
        return int(obj.rect().x() + lay[1][0] / 2) + obj.x(), int(obj.rect().y() + lay[1][1] / 2) + obj.y()


def mod(num: int, other: int):
    return -abs(num % other)


class PnvToggleableComponent:
    def __init__(self, enabled=True):
        self.__enabled = enabled

    def on_enable(self):
        ...

    def on_disable(self):
        ...

    def is_enabled(self):
        return self.__enabled

    def set_enabled(self, val: bool):
        self.__enabled = val
        if val:
            self.on_enable()
        else:
            self.on_disable()


class PnvViewScaler:
    def __init__(self, viewer: 'PnvViewer'):
        self.__viewer = viewer
        self.scaler = 0
        self.inwards = 1.1
        self.outwards = 1 / self.inwards

    def wheel_event(self, e: Optional[QtGui.QWheelEvent]) -> None:
        vec = e.angleDelta().y() / 120  # Scroll delta
        # scale scene
        if vec > 0 and self.scaler < (8 + 2):
            self.scaler += 1
            self.__viewer.scale(self.inwards, self.inwards)  # closer
        elif vec < 0 and self.scaler > (-4 - 2):
            self.scaler -= 1
            self.__viewer.scale(self.outwards, self.outwards)  # farther
        # scale grid
        sf = self.scale_factor()
        if sf >= 2:
            self.__viewer.grid_distance = 50
            self.__viewer.bg_grid_pen.setWidthF(0.5)
        elif 0.75 < sf < 2:
            self.__viewer.grid_distance = 100
            self.__viewer.bg_grid_pen.setWidthF(1)
        else:
            self.__viewer.grid_distance = 200
            self.__viewer.bg_grid_pen.setWidthF(3)

    def scale_factor(self):
        return self.inwards ** self.scaler


class PnvViewTransformer:
    def __init__(self, view: 'PnvViewer'):
        self.__viewer = view
        self.__started = False

    def update(self):
        if self.__viewer.mouse_ctrl.grabbing:
            self.__started = True
            QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.ClosedHandCursor)
            delta = -self.__viewer.mouse_ctrl.delta
            self.__viewer.horizontalScrollBar().setValue(int(self.__viewer.horizontalScrollBar().value() + delta.x()))
            self.__viewer.verticalScrollBar().setValue(int(self.__viewer.verticalScrollBar().value() + delta.y()))
            self.__viewer.setSceneRect(
                self.__viewer.sceneRect().translated(delta.x(),
                                                     delta.y())
            )
            self.__viewer.mouse_ctrl.force_last_pos(self.__viewer.mouse_ctrl.last_pos() + delta)
        elif self.__started:
            self.__started = False
            QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.ArrowCursor)


class PnvMouseController:
    def __init__(self, view: 'PnvViewer'):
        self.__viewer = view
        self.delta: Qt.QPoint = Qt.QPoint(0, 0)
        self.__last_pos: Union[Qt.QPoint, None] = None
        self.holding: bool = False
        self.grabbing: bool = False

    def mouse_press_event(self, e: Optional[QtGui.QMouseEvent]):
        if e.button() in [Qt.Qt.RightButton, Qt.Qt.MiddleButton]:
            self.grabbing = True
        elif e.button() == Qt.Qt.LeftButton:
            self.holding = True

    def mouse_move_event(self, e: Optional[QtGui.QMouseEvent]):
        new = self.__viewer.mapToScene(e.pos())
        if self.__last_pos is not None:
            self.delta = new - self.__last_pos
        self.__last_pos = new

    def last_pos(self):
        return self.__last_pos

    def force_last_pos(self, pos: QPoint):
        self.__last_pos = pos

    def mouse_release_event(self, e: Optional[QtGui.QMouseEvent]):
        if e.button() in [Qt.Qt.RightButton, Qt.Qt.MiddleButton]:
            self.grabbing = False
        elif e.button() == Qt.Qt.LeftButton:
            self.holding = False


class PnvItemsTransformer(PnvToggleableComponent):
    def __init__(self, view: 'PnvViewer'):
        super().__init__()
        self.__viewer = view
        self.moving = False
        self.__start_pos = None  # transform started mark

    def __transform(self, to: QPoint):
        arrows = set()
        for item in self.__viewer.view_selector.selected_items:
            item.setX(item.x() + to.x())
            item.setY(item.y() + to.y())
            arrows |= item.arrows()
        for arr in arrows:
            arr.update(arr.boundingRect())

    def __is_started(self):
        return self.__start_pos

    def __start_transform(self):
        self.__start_pos = self.__viewer.mouse_ctrl.last_pos()
        QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.SizeAllCursor)

    def __stop_transform(self):
        self.__start_pos = None
        QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.ArrowCursor)

    def __pass_loyal_offset(self):
        local_delta = self.__viewer.mouse_ctrl.last_pos() - self.__start_pos  # loyal offset delta
        if max(abs(local_delta.x()), abs(local_delta.y())) <= (2.0 / self.__viewer.view_scaler.scale_factor()):
            return None
        return local_delta

    def __nearest_grid(self, last):
        return QPoint(round(last.x() / self.__viewer.grid_distance) * self.__viewer.grid_distance,
                      round(last.y() / self.__viewer.grid_distance) * self.__viewer.grid_distance)

    def on_disable(self):
        if self.__is_started():
            self.moving = False
            self.__stop_transform()

    def update(self):
        if not self.is_enabled():
            return
        spec: Union[PnvQGTransitionItem, PnvQGPlaceItem] = self.__viewer.view_selector.selected_special
        if self.__viewer.mouse_ctrl.holding and spec:
            if not self.__is_started():
                self.__start_transform()
            if not self.moving:
                to = self.__pass_loyal_offset()
                if not to:
                    return  # not passed
                self.moving = True
            else:
                if PnvViewSelector.shift_pressed():
                    to = self.__nearest_grid(self.__viewer.mouse_ctrl.last_pos()) - \
                         (spec.pos() + QPoint(int(spec.rect().x() + spec.rect().width() // 2),
                                              int(spec.rect().y() + spec.rect().height() // 2)))
                else:
                    to = self.__viewer.mouse_ctrl.delta
            self.__transform(to)
        elif self.__is_started():
            if not self.moving and spec:
                self.__viewer.view_selector.select_special(spec, not PnvViewSelector.shift_pressed())
                # selector hook-back
            self.moving = False
            self.__stop_transform()


class PnvViewContextFirer(PnvToggleableComponent):
    def __init__(self, view: 'PnvViewer'):
        super().__init__()
        self.__viewer = view
        self.__delta = QPoint()
        self.__overpassed = False
        self.__started = False

    def on_disable(self):
        if self.__started:
            self.__overpassed = False
            self.__started = False
            self.__delta = QPoint()

    def update(self):
        if not self.is_enabled():
            return
        if self.__viewer.mouse_ctrl.grabbing:
            if not self.__started:
                self.__started = True
            if not self.__overpassed:
                self.__delta += self.__viewer.mouse_ctrl.delta
                if max(abs(self.__delta.x()), abs(self.__delta.y())) >= (
                        2.0 / self.__viewer.view_scaler.scale_factor()):
                    self.__overpassed = True
        elif self.__started:
            if not self.__overpassed:
                self.__viewer.context_menu_fire_event()
            self.__overpassed = False
            self.__started = False
            self.__delta = QPoint()


class PnvViewSelector(PnvToggleableComponent):
    def __init__(self, view: 'PnvViewer'):
        super().__init__()
        self.__viewer = view
        self.__start_pos = None
        self.__selection_obj: Union[QGraphicsRectItem, None] = None
        self.selected_items: set[Union[PnvQGTransitionItem, PnvQGPlaceItem]] = set()
        self.__pre_selected: set[Union[PnvQGTransitionItem, PnvQGPlaceItem]] = set()
        self.selected_special = None

    def __start_selection(self):
        if not PnvViewSelector.shift_pressed():
            self.deselect_all()
        self.__start_pos = last = self.__viewer.mouse_ctrl.last_pos()
        self.__selection_obj = self.__viewer.scene().addRect(Qt.QRectF(last.x(), last.y(), 1, 1),
                                                             Qt.QPen(Qt.Qt.darkCyan,
                                                                     1 / self.__viewer.view_scaler.scale_factor(),
                                                                     Qt.Qt.DashLine))
        QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.CrossCursor)

    @staticmethod
    def shift_pressed():
        return QApplication.keyboardModifiers() == QtCore.Qt.KeyboardModifier.ShiftModifier

    def is_selecting(self):
        return self.__selection_obj is not None

    def __select(self):
        last = self.__start_pos
        delta = self.__viewer.mouse_ctrl.last_pos() - last
        self.__selection_obj.setRect(Qt.QRectF(min(last.x(), last.x() + delta.x()),
                                               min(last.y(), last.y() + delta.y()),
                                               abs(delta.x()), abs(delta.y())))
        collides: set[Union[PnvQGTransitionItem, PnvQGPlaceItem]] = \
            set([o for o in self.__selection_obj.collidingItems(Qt.Qt.IntersectsItemBoundingRect)
                 if isinstance(o, PnvQGTransitionItem) or isinstance(o, PnvQGPlaceItem)])
        # differentiate whether selected or not
        lost = self.__pre_selected - collides
        new = collides - self.__pre_selected
        # force select
        for i in lost:
            self.__pre_selected.remove(i)
            i.deselect_manually()
        for i in new:
            self.__pre_selected.add(i)
            i.select_manually()

    def __finish_selection(self):
        self.__viewer.scene().removeItem(self.__selection_obj)
        self.__selection_obj = None
        self.__viewer.scene().update()
        self.selected_items |= self.__pre_selected
        self.__pre_selected.clear()
        QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.ArrowCursor)

    def deselect_all(self):
        for i in self.selected_items:
            i.deselect_manually()
        if self.selected_special:
            self.selected_special = None
        self.selected_items.clear()

    def select_special(self, clicked, remove_previous):
        if remove_previous:
            self.deselect_all()
        self.selected_items.add(clicked)
        clicked.select_manually()
        self.selected_special = clicked

    def is_clicked_item(self, pos: QPoint) -> Union[PnvQGPlaceItem, PnvQGTransitionItem]:
        clicked = self.__viewer.scene().itemAt(pos, self.__viewer.viewportTransform())
        clicked = clicked if isinstance(clicked, (PnvQGPlaceItem, PnvQGTransitionItem)) else None
        return clicked

    def on_disable(self):
        if self.__selection_obj is not None:
            self.__finish_selection()
        self.deselect_all()

    def update(self):
        if not self.is_enabled():
            return
        if self.__viewer.mouse_ctrl.holding and not self.__viewer.view_items_transformer.moving:
            if self.__selection_obj is None:
                item = self.is_clicked_item(self.__viewer.mouse_ctrl.last_pos())
                if item:
                    self.select_special(item, not (item in self.selected_items))
                    # item transformer hook
                    return
                self.__start_selection()
            else:
                self.__select()
        elif self.__selection_obj is not None:
            self.__finish_selection()


class LockButton(QPushButton):
    def __init__(self, parent: 'PnvViewer'):
        QPushButton.__init__(self, parent)
        self.__padding = 5
        self.__edit_mode = True
        self.set_edit_mode(True)
        self.resize(self.sizeHint().width(), self.sizeHint().height())

    def is_edit_mode(self):
        return self.__edit_mode

    def set_edit_mode(self, val: bool):
        if val:
            self.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
            self.setToolTip('Режим: редактирование')
        else:
            self.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView))
            self.setToolTip('Режим: просмотр')
        self.__edit_mode = val

    def update_pos(self):
        x = self.parent().rect().width() - self.width() - self.__padding
        y = self.__padding
        self.setGeometry(x, y, self.width(), self.height())

    def mousePressEvent(self, e: Optional[QtGui.QMouseEvent]) -> None:
        self.set_edit_mode(not self.__edit_mode)
        p: 'PnvViewer' = self.parent()
        p.view_mode_change_event(self.__edit_mode)


class PnvViewer(QGraphicsView):
    def __init__(self, *args, **kwargs):
        self.drawer: PnvDrawer = kwargs['drawer'] if 'drawer' in kwargs else None
        del kwargs['drawer']
        QGraphicsView.__init__(self, *args, *kwargs)  # Universal constructor bypass
        # scale module
        self.grid_distance = 100
        self.bg_brush = Qt.QBrush(Qt.QColor(0xdadada))
        self.bg_grid_pen = Qt.QPen(Qt.QBrush(Qt.QColor(0xadadad)), 1)
        self.view_scaler = PnvViewScaler(self)
        # mouse controller
        self.mouse_ctrl = PnvMouseController(self)
        # select module
        self.view_selector = PnvViewSelector(self)
        # transform module
        self.view_transformer = PnvViewTransformer(self)
        # items transform module
        self.view_items_transformer = PnvItemsTransformer(self)
        # context menu fire module
        self.view_context_fire = PnvViewContextFirer(self)
        # props
        self.edited_status = False
        # settings
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.horizontalScrollBar().setDisabled(True)
        self.verticalScrollBar().setDisabled(True)
        self.btn = LockButton(self)

    def wheelEvent(self, e: Optional[QtGui.QWheelEvent]) -> None:
        self.view_scaler.wheel_event(e)
        super().wheelEvent(e)

    def mousePressEvent(self, e: Optional[QtGui.QMouseEvent]) -> None:
        self.mouse_ctrl.mouse_press_event(e)
        self.view_selector.update()
        self.view_items_transformer.update()
        self.view_context_fire.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: Optional[QtGui.QMouseEvent]) -> None:
        self.mouse_ctrl.mouse_release_event(e)
        self.view_selector.update()
        self.view_transformer.update()
        self.view_items_transformer.update()
        self.view_context_fire.update()
        super().mouseReleaseEvent(e)

    def mouseMoveEvent(self, e: Optional[QtGui.QMouseEvent]) -> None:
        self.mouse_ctrl.mouse_move_event(e)
        self.view_transformer.update()
        self.view_selector.update()
        self.view_items_transformer.update()
        self.view_context_fire.update()
        super().mouseMoveEvent(e)

    def resizeEvent(self, event: Optional[QtGui.QResizeEvent]) -> None:
        self.btn.update_pos()
        super().resizeEvent(event)

    def context_menu_fire_event(self):
        clicked = self.scene().itemAt(self.mouse_ctrl.last_pos(), self.viewportTransform())
        clicked = clicked if isinstance(clicked, (PnvQGPlaceItem, PnvQGTransitionItem)) else None
        if clicked:
            return
        pos = self.mapToGlobal(self.mapFromScene(self.mouse_ctrl.last_pos()))
        cmenu = QMenu(self.scene().parent())
        if len(self.view_selector.selected_items) == 1 or False:
            return  # skip all selected or single one
        elif len(self.view_selector.selected_items) == 0:
            cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_TitleBarUnshadeButton),
                            '&Добавить позицию')
            cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_TitleBarUnshadeButton),
                            '&Добавить переход')
            cmenu.exec(pos)
        elif len(self.view_selector.selected_items) == 2:
            cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
                            '&Соединить')
            cmenu.addSeparator()
            cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown),
                            '&Объединить в подсеть', self.enclose_selected)
            cmenu.exec(pos)
        else:
            cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown),
                            '&Объединить в подсеть', self.enclose_selected)
            cmenu.exec(pos)

    def view_mode_change_event(self, edit_mode: bool):
        self.view_context_fire.set_enabled(edit_mode)
        self.view_selector.set_enabled(edit_mode)
        self.view_items_transformer.set_enabled(edit_mode)
        for item in self.items():
            if isinstance(item, (PnvQGTransitionItem, PnvQGPlaceItem)):
                item.set_interactive(edit_mode)
        self.viewport().update()

    def enclose_selected(self):
        selected = set(self.view_selector.selected_items)
        self.view_selector.deselect_all()
        try:
            self.drawer.subnet_wrap(selected)
        except pnv.importer.epnml.EPNMLException as ex:
            from main import PnvMainWindow
            PnvMessageBoxes.warning(f"Невозможно сделать вложенную сеть!",
                                    f"{ex}",
                                    icon=PnvMainWindow.WINDOW_ICON).exec()

    def drawBackground(self, painter: Optional[QtGui.QPainter], rect: QtCore.QRectF) -> None:
        painter.fillRect(rect, self.bg_brush)
        if not self.btn.is_edit_mode():
            return
        painter.setPen(self.bg_grid_pen)
        # grid draw
        ix, ix0 = int(rect.x()), int(rect.x() + rect.width())
        iy, iy0 = int(rect.y()), int(rect.y() + rect.height())
        x = ix + mod(ix, self.grid_distance)
        x0 = ix0 + mod(ix0, self.grid_distance)
        y = iy + mod(iy, self.grid_distance)
        y0 = iy0 + mod(iy0, self.grid_distance)
        for xt in range(x, x0 + 1, self.grid_distance):
            painter.drawLine(Qt.QLineF(xt, rect.y(), xt, rect.y() + rect.height()))
        for yt in range(y, y0 + 1, self.grid_distance):
            painter.drawLine(Qt.QLineF(rect.x(), yt, rect.x() + rect.width(), yt))

    # def drawForeground(self, painter: Optional[QtGui.QPainter], rect: QtCore.QRectF) -> None:
    #     painter.setPen(self.bg_grid_pen)
    #     lp = self.mouse_ctrl.last_pos()
    #     if lp:
    #         painter.drawEllipse(QtCore.QRectF(lp.x() - 10, lp.y() - 10, 20, 20))

    def inject_all_positions(self):
        for obj in self.items():
            if not isinstance(obj, (PnvQGPlaceItem, PnvQGTransitionItem)):
                continue
            bind = obj.petri_net_bound()
            if not obj:
                continue
            lay = PnvDrawer.layout(bind)
            new_lay = (PnvDrawer.final_pos(obj), (lay[1][0], lay[1][1]))
            if new_lay == lay:
                continue
            bind.properties['layout_information_petri'] = new_lay

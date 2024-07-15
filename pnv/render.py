import time
from typing import Union, Optional, Tuple

from PyQt5 import Qt, QtCore, QtGui
from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsRectItem, QGraphicsView, QApplication, QMenu, \
    QStyle, QPushButton
from pm4py import PetriNet, Marking
from igraph import Graph
from math import log, floor, ceil

import pnv.importer.epnml
from pnv.graphics import PnvQGTransitionItem, PnvQGPlaceItem, PnvQGArrowItem, Labeling
from pnv.importer.epnml import ExtendedTransition
from pnv.utils import PnvMessageBoxes, PnvConfig, PnvConfigConstants

Layout = Tuple[Tuple[int, int], Tuple[int, int]]


class PnvEditState:
    def __init__(self):
        self.layout_generated = False
        self.layout_changed = False
        self.meta_data = False

    def is_changed(self) -> bool:
        return self.layout_generated or \
            self.layout_changed or \
            self.meta_data

    def changes(self) -> list[str]:
        changes: list[str] = []
        if self.layout_changed:
            changes.append('перемещены элементы сети')
        if self.layout_generated:
            changes.append('сгенерирована разметка')
        if self.meta_data:
            changes.append('обновлены компоненты')
        return changes

    def reset(self):
        self.layout_generated = False
        self.layout_changed = False
        self.meta_data = False


class PnvDrawer:
    GRAPHICS_WIDTH = 40

    def __init__(self, scene: QGraphicsScene, net: PetriNet):
        self.scene = scene
        self.net = net
        self.mapper: dict[Union[PetriNet.Place, PetriNet.Transition], Union[PnvQGTransitionItem, PnvQGPlaceItem]] = dict()
        self.status = PnvEditState()

    def draw_place_directly(self, x: int, y: int, r: int) -> PnvQGPlaceItem:
        # custom ellipse init
        obj = PnvQGPlaceItem(QtCore.QRectF(x - r / 2, y - r / 2, r, r))
        self.scene.addItem(obj)
        return obj

    def draw_transition_directly(self, x: int, y: int, w: int, h: int, label: str = None) -> PnvQGTransitionItem:
        # custom rectangle init
        obj = PnvQGTransitionItem(QtCore.QRectF(x - w / 2, y - h / 2, w, h))
        self.scene.addItem(obj)
        obj.set_label(label, (w / 2, h / 2))
        return obj

    def draw_place(self, p: PetriNet.Place) -> PnvQGPlaceItem:
        pos, shape = self.layout(p)
        obj = self.draw_place_directly(*pos, shape[0])
        obj.drawer = self
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
        layout = g.layout(layout=PnvConfig.INSTANCE.igraph_gen_mode)
        # scaling
        min_dist = PnvDrawer.GRAPHICS_WIDTH
        for i, gen in enumerate(layout):
            for j, gen1 in enumerate(layout):
                if i == j:
                    continue
                x, y = gen[0], gen[1]
                x1, y1 = gen1[0], gen1[1]
                min_dist = min(min_dist, ((x-x1)**2 + (y-y1)**2) ** 0.5)
        k = PnvDrawer.GRAPHICS_WIDTH / min_dist * 2
        layout.scale(k)
        # injection
        for i, gen in enumerate(layout):
            lay = ((gen[0], gen[1]), (PnvDrawer.GRAPHICS_WIDTH, PnvDrawer.GRAPHICS_WIDTH))
            PnvDrawer.inject_layout(local_mapper_re[i], lay)

        self.status.layout_generated = True

    def connect_arc(self, from_: Union[PnvQGTransitionItem, PnvQGPlaceItem],
                    to: Union[PnvQGTransitionItem, PnvQGPlaceItem]):
        # net arc
        arc = PetriNet.Arc(from_.petri_net_bound(), to.petri_net_bound())
        self.net.arcs.add(arc)
        arc.source.out_arcs.add(arc)
        arc.target.in_arcs.add(arc)
        # gui arc
        arrow = self.draw_arc(from_.petri_net_bound(), to.petri_net_bound())
        from_.arrows().add(arrow)
        to.arrows().add(arrow)

        self.status.layout_changed = True

    def disconnect_arc(self, one: Union[PnvQGTransitionItem, PnvQGPlaceItem],
                       two: Union[PnvQGTransitionItem, PnvQGPlaceItem]):
        to = None
        from_ = None
        for arrow in one.arrows():
            if arrow.to is one and arrow.from_ is two:
                to = one
                from_ = two
                break
            elif arrow.to is two and arrow.from_ is one:
                to = two
                from_ = one
                break
        if to is None or from_ is None:
            raise Exception('Unable to disconnect components!')
        target_arc: PetriNet.Arc = None
        for arc in from_.petri_net_bound().out_arcs:
            if arc.target is to.petri_net_bound():
                target_arc = arc
                break
        if target_arc is None:
            raise Exception('Somehow, connected components have no arc!')
        # removing net
        target_arc.source.out_arcs.remove(target_arc)
        target_arc.target.in_arcs.remove(target_arc)
        self.net.arcs.remove(target_arc)
        # remove gui
        arrow.from_.arrows().remove(arrow)
        arrow.to.arrows().remove(arrow)
        arrow.hide()
        self.scene.removeItem(arrow)

        self.status.layout_changed = True

    def place_create(self, pos: QtCore.QPointF):
        p = PetriNet.Place(f'p{str(time.time())}')
        lay = ((pos.x(), pos.y()), (PnvDrawer.GRAPHICS_WIDTH, PnvDrawer.GRAPHICS_WIDTH))
        PnvDrawer.inject_layout(p, lay)
        self.mapper[p] = self.draw_place(p)
        self.net.places.add(p)

        self.status.layout_changed = True

    def transition_create(self, pos: QtCore.QPointF):
        t = PetriNet.Transition(f'p{str(time.time())}')
        lay = ((pos.x(), pos.y()), (PnvDrawer.GRAPHICS_WIDTH, PnvDrawer.GRAPHICS_WIDTH))
        PnvDrawer.inject_layout(t, lay)
        self.mapper[t] = self.draw_transition(t)
        self.net.transitions.add(t)

        self.status.layout_changed = True

    def place_remove(self, item: PnvQGPlaceItem):
        # net remove
        bound = item.petri_net_bound()
        for in_arc in bound.in_arcs:
            in_arc.source.out_arcs.remove(in_arc)
            self.net.arcs.remove(in_arc)
        for out_arc in bound.out_arcs:
            out_arc.target.in_arcs.remove(out_arc)
            self.net.arcs.remove(out_arc)
        self.net.places.remove(bound)
        # gui remove
        for arrow in item.arrows():
            if arrow.from_ is self:
                arrow.to.arrows().remove(arrow)
            elif arrow.to is self:
                arrow.from_.arrows().remove(arrow)
            arrow.hide()
            self.scene.removeItem(arrow)
        item.hide()
        self.scene.removeItem(item)
        self.scene.update()

        self.status.layout_changed = True

    def transition_remove(self, item: PnvQGTransitionItem):
        # net remove
        bound = item.petri_net_bound()
        for in_arc in bound.in_arcs:
            in_arc.source.out_arcs.remove(in_arc)
            self.net.arcs.remove(in_arc)
        for out_arc in bound.out_arcs:
            out_arc.target.in_arcs.remove(out_arc)
            self.net.arcs.remove(out_arc)
        self.net.transitions.remove(bound)
        # gui remove
        for arrow in item.arrows():
            if arrow.from_ is self:
                arrow.to.arrows().remove(arrow)
            elif arrow.to is self:
                arrow.from_.arrows().remove(arrow)
            arrow.hide()
            self.scene.removeItem(arrow)
        item.hide()
        self.scene.removeItem(item)
        self.scene.update()

        self.status.layout_changed = True

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
                boundary_transitions = boundary_transitions and isinstance(arrow.from_,
                                                                           PnvQGTransitionItem) and not isinstance(
                    arrow.from_.petri_net_bound(), ExtendedTransition)
            elif not (arrow.from_ in objs):
                outer_from_objs.add(arrow.from_)
                boundary_transitions = boundary_transitions and isinstance(arrow.to,
                                                                           PnvQGTransitionItem) and not isinstance(
                    arrow.to.petri_net_bound(), ExtendedTransition)
        # boundary verification
        if not boundary_transitions:
            raise pnv.importer.epnml.EPNMLException('Boundary objects must be simple transitions!')

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

        self.__scale_mx = floor(log(PnvConfig.INSTANCE.limited_zoom_max, self.inwards))
        self.__scale_mn = ceil(log(PnvConfig.INSTANCE.limited_zoom_min, self.inwards))
        self.__limited = PnvConfig.INSTANCE.limit_zoom

    def wheel_event(self, e: Optional[QtGui.QWheelEvent]) -> None:
        vec = e.angleDelta().y() / 120  # Scroll delta
        # scale scene
        if vec > 0 and ((not self.__limited) or self.scaler < self.__scale_mx):
            self.scaler += 1
            self.__viewer.scale(self.inwards, self.inwards)  # closer
        elif vec < 0 and ((not self.__limited) or self.scaler > self.__scale_mn):
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
            # mapping between translated and not
            delta = -self.__viewer.mouse_ctrl.delta
            k = self.__viewer.view_scaler.scale_factor()
            sbdx = int(self.__viewer.horizontalScrollBar().value() + delta.x() * k)
            sbdy = int(self.__viewer.verticalScrollBar().value() + delta.y() * k)
            self.__viewer.horizontalScrollBar().setValue(sbdx)
            self.__viewer.verticalScrollBar().setValue(sbdy)
            # exact translation
            if PnvConfig.INSTANCE.limit_translation:
                self.__viewer.sceneRect().translate(delta.x(), delta.y())
            else:
                self.__viewer.setSceneRect(self.__viewer.sceneRect().translated(delta.x(), delta.y()))
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

        self.__viewer.drawer.status.layout_changed = True

    def __is_started(self):
        return self.__start_pos

    def __start_transform(self):
        self.__start_pos = self.__viewer.mouse_ctrl.last_pos()
        QtGui.QGuiApplication.setOverrideCursor(Qt.Qt.SizeAllCursor)
        self.__viewer.edited_status = True

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

    def select_special(self, clicked: Union[PnvQGTransitionItem, PnvQGPlaceItem], remove_previous: bool):
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
                    if PnvViewSelector.shift_pressed():
                        self.select_special(item, False)
                    else:
                        self.select_special(item, not (item in self.selected_items))
                    # item transformer hook
                    return
                self.__start_selection()
            else:
                self.__select()
        elif self.__selection_obj is not None:
            self.__finish_selection()


class EditModeButton(QPushButton):
    def __init__(self, parent: 'PnvViewer'):
        QPushButton.__init__(self, parent)
        self.__padding = 5
        self.__mode = PnvConfig.INSTANCE.enter_mode
        # init
        self.set_mode(self.__mode)
        self.resize(self.sizeHint().width(), self.sizeHint().height())

    def is_view(self):
        return self.__mode == PnvConfigConstants.ENTER_MODE_VIEW

    def is_explore(self):
        return self.__mode == PnvConfigConstants.ENTER_MODE_EXPLORE

    def is_mutate(self):
        return self.__mode == PnvConfigConstants.ENTER_MODE_MUTATE

    def set_mode(self, val: str):
        if val == PnvConfigConstants.ENTER_MODE_VIEW:
            self.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView))
            self.setToolTip('Режим взаимодействия: просмотр')
        elif val == PnvConfigConstants.ENTER_MODE_EXPLORE:
            self.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
            self.setToolTip('Режим взаимодействия: интерактивный осмотр')
        elif val == PnvConfigConstants.ENTER_MODE_MUTATE:
            self.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogListView))
            self.setToolTip('Режим взаимодействия: редактирование')
        else:
            val = PnvConfigConstants.ENTER_MODE_VIEW
        self.__mode = val
        self.sync_mode()

    def next(self, mode: str):
        if mode == PnvConfigConstants.ENTER_MODE_VIEW:
            return PnvConfigConstants.ENTER_MODE_EXPLORE
        elif mode == PnvConfigConstants.ENTER_MODE_EXPLORE:
            return PnvConfigConstants.ENTER_MODE_MUTATE
        elif mode == PnvConfigConstants.ENTER_MODE_MUTATE:
            return PnvConfigConstants.ENTER_MODE_VIEW

    def sync_mode(self):
        p: 'PnvViewer' = self.parent()
        p.view_mode_change_event(self.__mode)

    def update_pos(self):
        x = self.parent().rect().width() - self.width() - self.__padding
        y = self.__padding
        self.setGeometry(x, y, self.width(), self.height())

    def mousePressEvent(self, e: Optional[QtGui.QMouseEvent]) -> None:
        self.set_mode(self.next(self.__mode))


class LabelingModeButton(QPushButton):
    def __init__(self, parent: 'PnvViewer'):
        QPushButton.__init__(self, parent)
        self.__padding_x = 2 * 5 + self.sizeHint().width()
        self.__padding_y = 5
        self.__labeling_mode = PnvConfig.INSTANCE.labeling_mode
        # init
        self.set_labeling_mode(self.__labeling_mode)
        self.resize(self.sizeHint().width(), self.sizeHint().height())

    def set_labeling_mode(self, val: str):
        if val == PnvConfigConstants.LABELING_MODE_FIXED:
            self.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarNormalButton))
            self.setToolTip('Режим ярлыков: фиксированно')
        elif val == PnvConfigConstants.LABELING_MODE_DYNAMIC:
            self.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton))
            self.setToolTip('Режим ярлыков: сохранять размер')
        elif val == PnvConfigConstants.LABELING_MODE_CLOSEST:
            self.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarShadeButton))
            self.setToolTip('Режим ярлыков: отображать ближайшие')
        else:
            val = PnvConfigConstants.LABELING_MODE_FIXED
        self.__labeling_mode = val
        self.sync_labels()

    def sync_labels(self):
        p: 'PnvViewer' = self.parent()
        p.labeling_mode_change_event(self.__labeling_mode)

    def update_pos(self):
        x = self.parent().rect().width() - self.width() - self.__padding_x
        y = self.__padding_y
        self.setGeometry(x, y, self.width(), self.height())

    def next(self, mode: str):
        if mode == PnvConfigConstants.LABELING_MODE_FIXED:
            return PnvConfigConstants.LABELING_MODE_DYNAMIC
        elif mode == PnvConfigConstants.LABELING_MODE_DYNAMIC:
            return PnvConfigConstants.LABELING_MODE_CLOSEST
        elif mode == PnvConfigConstants.LABELING_MODE_CLOSEST:
            return PnvConfigConstants.LABELING_MODE_FIXED

    def mousePressEvent(self, e: Optional[QtGui.QMouseEvent]) -> None:
        self.set_labeling_mode(self.next(self.__labeling_mode))


class PnvViewer(QGraphicsView):
    def __init__(self, drawer: PnvDrawer, *args, **kwargs):
        self.drawer = drawer
        QGraphicsView.__init__(self, *args, *kwargs)  # Universal constructor bypass
        # scale module
        self.grid_distance = 100
        self.bg_brush = Qt.QBrush(Qt.QColor(0xdadada))
        self.bg_brush_mutate = Qt.QBrush(Qt.QColor(0xccd7e0))
        self.bg_grid_pen = Qt.QPen(Qt.QBrush(Qt.QColor(0xadadad)), 1)
        self.bg_grid_pen_mutate = Qt.QPen(Qt.QBrush(Qt.QColor(0x1f4a80)), 1)
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
        # settings
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.horizontalScrollBar().setDisabled(True)
        self.verticalScrollBar().setDisabled(True)
        self.viewmode_btn = EditModeButton(self)
        self.labeling_btn = LabelingModeButton(self)
        self.__context_blocked = False

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
        self.viewmode_btn.update_pos()
        self.labeling_btn.update_pos()
        super().resizeEvent(event)

    def context_menu_fire_event(self):
        clicked = self.scene().itemAt(self.mouse_ctrl.last_pos(), self.viewportTransform())
        clicked = clicked if isinstance(clicked, (PnvQGPlaceItem, PnvQGTransitionItem)) else None
        if clicked:
            return
        pos = self.mapToGlobal(self.mapFromScene(self.mouse_ctrl.last_pos()))
        cmenu = QMenu(self.scene().parent())
        if len(self.view_selector.selected_items) == 1:
            return  # skip all selected or single one
        elif len(self.view_selector.selected_items) == 0:
            cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_TitleBarUnshadeButton),
                            '&Добавить позицию', self.place_create)
            cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_TitleBarUnshadeButton),
                            '&Добавить переход', self.transition_create)
        elif len(self.view_selector.selected_items) == 2:
            first, second, *_ = self.view_selector.selected_items
            # bi verification
            if type(first) == type(second):
                return
            first: Union[PnvQGTransitionItem, PnvQGPlaceItem]
            second: Union[PnvQGTransitionItem, PnvQGPlaceItem]
            connected = any(arc.target is second.petri_net_bound() for arc in first.petri_net_bound().out_arcs) or \
                        any(arc.source is second.petri_net_bound() for arc in first.petri_net_bound().in_arcs)

            if connected:
                cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_MediaPause),
                                '&Отсоединить', self.arc_destroy)
            else:
                # special verification
                if not (first is self.view_selector.selected_special) and not (
                        second is self.view_selector.selected_special):
                    return
                cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
                                '&Соединить', self.arc_connect)
        else:
            cmenu.addAction(self.scene().style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown),
                            '&Объединить в подсеть', self.enclose_selected)
        self.__context_blocked = True
        cmenu.exec(pos)

    def contextMenuEvent(self, event):
        # helps to cancel extra click after artificial context menu
        if self.__context_blocked:
            self.__context_blocked = False
            return
        # default behavior
        super().contextMenuEvent(event)
        # update mouse pos
        self.mouse_ctrl.force_last_pos(self.mapToScene(event.pos()))

    def place_create(self):
        self.drawer.place_create(self.mouse_ctrl.last_pos())

    def transition_create(self):
        self.drawer.transition_create(self.mouse_ctrl.last_pos())

    def arc_destroy(self):
        one, two = self.view_selector.selected_items
        self.drawer.disconnect_arc(one, two)

    def arc_connect(self):
        to = self.view_selector.selected_special
        from_, *_ = set(self.view_selector.selected_items) - {to}
        self.drawer.connect_arc(from_, to)

    def view_mode_change_event(self, edit_mode: str):
        if edit_mode == PnvConfigConstants.ENTER_MODE_VIEW:
            self.view_context_fire.set_enabled(False)
            self.view_selector.set_enabled(False)
            self.view_items_transformer.set_enabled(False)
            for item in self.items():
                if isinstance(item, (PnvQGTransitionItem, PnvQGPlaceItem)):
                    item.set_interactive(False)
        else:
            self.view_selector.set_enabled(True)
            self.view_items_transformer.set_enabled(True)
            if edit_mode == PnvConfigConstants.ENTER_MODE_EXPLORE:
                self.view_context_fire.set_enabled(False)
                for item in self.items():
                    if isinstance(item, PnvQGTransitionItem):
                        item.set_interactive(True)
                        item.only_wuw = True
                    elif isinstance(item, PnvQGPlaceItem):
                        item.set_interactive(False)
            elif edit_mode == PnvConfigConstants.ENTER_MODE_MUTATE:
                self.view_context_fire.set_enabled(True)
                for item in self.items():
                    if isinstance(item, PnvQGTransitionItem):
                        item.set_interactive(True)
                        item.only_wuw = False
                    elif isinstance(item, PnvQGPlaceItem):
                        item.set_interactive(True)

        self.viewport().update()

    def labeling_mode_change_event(self, mode: str):
        if mode == PnvConfigConstants.LABELING_MODE_FIXED:
            for item in self.items():
                if isinstance(item, Labeling):
                    item.set_visible(True)
        elif mode == PnvConfigConstants.LABELING_MODE_DYNAMIC:
            for item in self.items():
                if isinstance(item, Labeling):
                    item.set_visible(True)
        elif mode == PnvConfigConstants.LABELING_MODE_CLOSEST:
            for item in self.items():
                if isinstance(item, Labeling):
                    item.set_visible(False)
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
        if self.viewmode_btn.is_view():
            painter.fillRect(rect, self.bg_brush)
            return
        if self.viewmode_btn.is_explore():
            painter.fillRect(rect, self.bg_brush)
            painter.setPen(self.bg_grid_pen)
        if self.viewmode_btn.is_mutate():
            painter.fillRect(rect, self.bg_brush_mutate)
            painter.setPen(self.bg_grid_pen_mutate)
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

    def can_be_saved(self):
        places = 0
        transitions = 0
        arcs = 0
        for obj in self.items():
            if isinstance(obj, PnvQGPlaceItem):
                places += 1
                arcs += len(obj.arrows())
            elif isinstance(obj, PnvQGTransitionItem):
                transitions += 1
                arcs += len(obj.arrows())
        return places != 0 and transitions != 0 and arcs != 0

    def inject_all_positions(self):
        for obj in self.items():
            if not isinstance(obj, (PnvQGPlaceItem, PnvQGTransitionItem)):
                continue
            bind = obj.petri_net_bound()
            if not bind:
                continue
            lay = PnvDrawer.layout(bind)
            new_lay = (PnvDrawer.final_pos(obj), (lay[1][0], lay[1][1]))
            if new_lay == lay:
                continue
            bind.properties['layout_information_petri'] = new_lay

    def retrieve_markings(self) -> tuple[Marking, Marking]:
        init = Marking()
        final = Marking()
        for obj in self.items():
            if not isinstance(obj, PnvQGPlaceItem):
                continue
            if obj.final:
                final[obj.petri_net_bound()] = 1
            elif obj.markings != 0:
                init[obj.petri_net_bound()] = obj.markings
        return init, final

    def init_markings(self, init: Marking, final: Marking):
        for obj in self.items():
            if not isinstance(obj, PnvQGPlaceItem):
                continue
            bound = obj.petri_net_bound()
            if (init is not None) and (bound in init):
                obj.markings = init[bound]
            elif (final is not None) and (bound in final):
                obj.final = final[bound]

    def is_hierarchical_one(self):
        return any(isinstance(obj.petri_net_bound(), ExtendedTransition) for obj in self.items() if isinstance(obj, PnvQGTransitionItem))

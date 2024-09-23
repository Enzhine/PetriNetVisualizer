from os import listdir
from os.path import isfile, join, splitext
from pm4py import read_pnml
from pm4py.objects.petri_net.obj import PetriNet, Marking

from pnv.importer import epnml
from pnv.importer.epnml import ExtendedTransition

ENTRY_FILE = 'abstract_heu'
FILE_POSTFIX = '_heu'
TARGET_DIR = 'unwrapped'
TARGET_EXT = '.pnml'

ENTRY_POINT = ENTRY_FILE + TARGET_EXT
PnmlData = tuple[PetriNet, Marking, Marking]
NetFile = tuple[str, str]


def files(_dir: str, _ext: str, _postfix: str) -> list[NetFile]:
    out = []
    for file in listdir(_dir):
        full_path = join(_dir, file)
        if not isfile(full_path):
            continue
        filename, ext = splitext(file)
        if ext != _ext:
            continue
        if not filename.endswith(_postfix):
            continue

        nf: NetFile = (filename[:-len(_postfix)], full_path)
        out.append(nf)
    return out


def try_wrap(filename: str, _files: list[NetFile]) -> tuple[PnmlData, dict]:
    data: PnmlData = read_pnml(filename)
    net, im, fm = data

    _bounds: dict[PetriNet.Place, list[tuple[PetriNet.Arc, PetriNet]]] = dict()

    for tr in list(net.transitions):
        for name, file in _files:
            if tr.name == name:
                break
        else:
            continue
        print(f'-> Reached {name}')

        outer, *_ = [a.target for a in tr.out_arcs]
        inner, *_ = [a.source for a in tr.in_arcs]

        (_net, _im, _fm), bounds = try_wrap(file, _files)
        etr = ExtendedTransition(name, name, None, None, tr.properties)

        for place in _net.places:
            place: PetriNet.Place
            place.name = f'{name}_{place.name}'

        _inner, *_ = _im.keys()
        _outer, *_ = _fm.keys()

        inner_bound = []
        for arc in _inner.out_arcs:
            arc: PetriNet.Arc
            new_arc = PetriNet.Arc(inner, arc.target)
            inner_bound.append((new_arc, _net))
            arc.target.in_arcs.add(new_arc)
            arc.target.in_arcs.remove(arc)
            _net.arcs.remove(arc)
            _net.arcs.add(new_arc)
        outer_bound = []
        for arc in _outer.in_arcs:
            arc: PetriNet.Arc
            new_arc = PetriNet.Arc(arc.source, outer)
            outer_bound.append((new_arc, _net))
            arc.source.out_arcs.add(new_arc)
            arc.source.out_arcs.remove(arc)
            _net.arcs.remove(arc)
            _net.arcs.add(new_arc)
        if _inner in bounds:
            for arc, deep_net in bounds[_inner]:
                arc: PetriNet.Arc
                new_arc = PetriNet.Arc(inner, arc.target)
                arc.target.in_arcs.add(new_arc)
                arc.target.in_arcs.remove(arc)
                deep_net.arcs.remove(arc)
                deep_net.arcs.add(new_arc)
                inner_bound.append((new_arc, _net))
        if _outer in bounds:
            for arc, deep_net in bounds[_outer]:
                arc: PetriNet.Arc
                new_arc = PetriNet.Arc(arc.source, outer)
                arc.source.out_arcs.add(new_arc)
                arc.source.out_arcs.remove(arc)
                deep_net.arcs.remove(arc)
                deep_net.arcs.add(new_arc)
                outer_bound.append((new_arc, _net))
        _bounds.update({inner: inner_bound, outer: outer_bound})
        _net.places.remove(_inner)
        _net.places.remove(_outer)
        etr.inject_net(_net, None, None)

        print(f'<- Wrapped {name}')

        for arc in tr.in_arcs:
            arc: PetriNet.Arc
            new_arc = PetriNet.Arc(arc.source, etr)
            etr.in_arcs.add(new_arc)
            arc.source.out_arcs.add(new_arc)
            arc.source.out_arcs.remove(arc)
            net.arcs.remove(arc)
            net.arcs.add(new_arc)
        for arc in tr.out_arcs:
            arc: PetriNet.Arc
            new_arc = PetriNet.Arc(etr, arc.target)
            etr.out_arcs.add(new_arc)
            arc.target.in_arcs.add(new_arc)
            arc.target.in_arcs.remove(arc)
            net.arcs.remove(arc)
            net.arcs.add(new_arc)

        net.transitions.add(etr)
        net.transitions.remove(tr)
    return data, _bounds


def make_epnml(_dir: str, entry_point: str, _ext: str, _postfix: str):
    out_file = 'wrapped_net.epnml'
    print("Reading files...")
    _files = files(_dir, _ext, _postfix)
    print("Wrapping...")
    (_net, _im, _fm), _ = try_wrap(join(_dir, entry_point), _files)
    print("Wrapped. Saving...")
    epnml.export_net(_net, _im, out_file, _fm)
    print(f"Saved as {out_file}")


if __name__ == '__main__':
    make_epnml(TARGET_DIR, ENTRY_POINT, TARGET_EXT, FILE_POSTFIX)

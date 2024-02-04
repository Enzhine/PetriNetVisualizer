import time
from lxml import etree, objectify

from pm4py.util import constants, exec_utils
from pm4py.objects.petri_net import properties as petri_properties
from pm4py.objects.petri_net.obj import PetriNet, Marking, ResetNet, InhibitorNet, ResetInhibitorNet
from pm4py.objects.petri_net.utils.petri_utils import add_arc_from_to
from pm4py.objects.petri_net.importer.variants.pnml import Parameters


class EPNMLException(Exception):
    def __init__(self, *args):
        super(EPNMLException, self).__init__(*args)


class ExtendedTransition(PetriNet.Transition):
    def __init__(self, name, label=None, in_arcs=None, out_arcs=None, properties=None):
        super().__init__(name, label, in_arcs, out_arcs, properties)
        self.__inner_net: PetriNet = None
        self.__init_marks: Marking = None
        self.__final_marks: Marking = None

    def __get_inner_net(self):
        return self.__inner_net

    def __get_init_marks(self):
        return self.init_marking

    def __get_final_marks(self):
        return self.final_marking

    def inject_net(self, inner_net=None, init_marks=None, final_marks=None):
        self.__inner_net = inner_net
        self.__init_marks = init_marks
        self.__final_marks = final_marks

    inner_net = property(__get_inner_net)
    init_marking = property(__get_init_marks)
    final_marking = property(__get_final_marks)


def import_net(input_file_path, parameters=None):
    if parameters is None:
        parameters = {}

    encoding = exec_utils.get_param_value(Parameters.ENCODING, parameters, None)

    parser = etree.XMLParser(remove_comments=True, encoding=encoding)

    F = open(input_file_path, "rb")
    tree = objectify.parse(F, parser=parser)
    F.close()

    root = tree.getroot()

    for child in root:
        if 'net' in child.tag:
            root = child
        elif 'group' in child.tag:
            root = child

    return import_net_from_xml_object(root, parameters=parameters)


def import_net_from_xml_object(nett, parameters, top_net_data=None):
    # root expected to be a <net> or <transition>
    if parameters is None:
        parameters = {}

    # right now is not crucial
    # return_stochastic_information = exec_utils.get_param_value(Parameters.RETURN_STOCHASTIC_MAP, parameters, False)

    net = PetriNet('imported_' + str(time.time()))
    marking = Marking()
    fmarking = None

    page = None
    finalmarkings = None
    variables = None

    # stochastic_map = {}

    places_dict = {}
    trans_dict = {}
    ext_trans_dict = {}

    if nett is not None:
        for child in nett:
            if "page" in child.tag:
                page = child
            elif "finalmarkings" in child.tag:
                finalmarkings = child
            elif "variables" in child.tag:
                variables = child

    if page is None:
        page = nett

    if page is not None:
        for child in page:
            if "place" in child.tag:
                position_X = None
                position_Y = None
                dimension_X = None
                dimension_Y = None
                place_id = child.get("id")
                place_name = place_id
                number = 0
                for child2 in child:
                    if child2.tag.endswith('name'):
                        for child3 in child2:
                            if child3.text:
                                place_name = child3.text
                    if child2.tag.endswith('initialMarking'):
                        for child3 in child2:
                            if child3.tag.endswith("text"):
                                number = int(child3.text)
                    if child2.tag.endswith('graphics'):
                        for child3 in child2:
                            if child3.tag.endswith('position'):
                                position_X = float(child3.get("x"))
                                position_Y = float(child3.get("y"))
                            elif child3.tag.endswith("dimension"):
                                dimension_X = float(child3.get("x"))
                                dimension_Y = float(child3.get("y"))
                places_dict[place_id] = PetriNet.Place(place_id)
                places_dict[place_id].properties[constants.PLACE_NAME_TAG] = place_name
                net.places.add(places_dict[place_id])
                if position_X is not None and position_Y is not None and dimension_X is not None and dimension_Y is not None:
                    places_dict[place_id].properties[constants.LAYOUT_INFORMATION_PETRI] = (
                        (position_X, position_Y), (dimension_X, dimension_Y))
                if number > 0:
                    marking[places_dict[place_id]] = number
                del place_name

    if page is not None:
        for child in page:
            if child.tag.endswith("transition"):
                # try to find inner
                subpage = None
                for sub_child in child:
                    if "page" in sub_child.tag:
                        subpage = sub_child
                        break
                # inner end
                position_X = None
                position_Y = None
                dimension_X = None
                dimension_Y = None
                trans_id = child.get("id")
                trans_name = trans_id
                trans_visible = True
                trans_properties = {}
                trans_guard = child.get("guard")
                if trans_guard is not None:
                    trans_properties[petri_properties.TRANS_GUARD] = trans_guard

                for child2 in child:
                    if child2.tag.endswith("name"):
                        for child3 in child2:
                            if child3.text:
                                if trans_name == trans_id:
                                    trans_name = child3.text
                    elif child2.tag.endswith("graphics"):
                        for child3 in child2:
                            if child3.tag.endswith("position"):
                                position_X = float(child3.get("x"))
                                position_Y = float(child3.get("y"))
                            elif child3.tag.endswith("dimension"):
                                dimension_X = float(child3.get("x"))
                                dimension_Y = float(child3.get("y"))
                    elif child2.tag.endswith("toolspecific"):
                        tool = child2.get("tool")
                        if "ProM" in tool:
                            activity = child2.get("activity")
                            if "invisible" in activity:
                                trans_visible = False
                    elif child2.tag.endswith(petri_properties.WRITE_VARIABLE):
                        # property for data Petri nets
                        if petri_properties.WRITE_VARIABLE not in trans_properties:
                            trans_properties[petri_properties.WRITE_VARIABLE] = []
                        trans_properties[petri_properties.WRITE_VARIABLE].append(child2.text)
                    elif child2.tag.endswith(petri_properties.READ_VARIABLE):
                        # property for data Petri nets
                        if petri_properties.READ_VARIABLE not in trans_properties:
                            trans_properties[petri_properties.READ_VARIABLE] = []
                        trans_properties[petri_properties.READ_VARIABLE].append(child2.text)

                # 15/02/2021: the name associated in the PNML to invisible transitions was lost.
                # at least save that as property.
                if trans_visible:
                    trans_label = trans_name
                else:
                    trans_label = None

                if subpage is not None:
                    trans_dict[trans_id] = ExtendedTransition(trans_id, trans_name)
                    ext_trans_dict[trans_dict[trans_id]] = child
                else:
                    trans_dict[trans_id] = PetriNet.Transition(trans_id, trans_label)
                trans_dict[trans_id].properties[constants.TRANS_NAME_TAG] = trans_name
                for prop in trans_properties:
                    trans_dict[trans_id].properties[prop] = trans_properties[prop]
                net.transitions.add(trans_dict[trans_id])

                if position_X is not None and position_Y is not None and dimension_X is not None and dimension_Y is not None:
                    trans_dict[trans_id].properties[constants.LAYOUT_INFORMATION_PETRI] = (
                        (position_X, position_Y), (dimension_X, dimension_Y))

    for et, child in ext_trans_dict.items():
        try:
            group_inner_net, inner_init, inner_fin = import_net_from_xml_object(child, None,
                                                                                (places_dict, trans_dict))
            if not group_inner_net:
                raise EPNMLException(f'Empty extended transition {child}!')
            et.inject_net(group_inner_net, inner_init, inner_fin)
        except EPNMLException as ex:
            raise EPNMLException(f'Extended transition, imported by EPNML must be completed and correct! '
                                 f'Exact failure caused {ex}')

    if page is not None:
        for child in page:
            if child.tag.endswith("arc"):
                arc_source = child.get("source")
                arc_target = child.get("target")
                arc_weight = 1
                arc_type = None
                arc_properties = {}

                for arc_child in child:
                    if arc_child.tag.endswith("inscription"):
                        for text_element in arc_child:
                            if text_element.tag.endswith("text"):
                                arc_weight = int(text_element.text)
                    elif arc_child.tag.endswith(petri_properties.ARCTYPE):
                        for text_element in arc_child:
                            if text_element.tag.endswith("text"):
                                arc_type = text_element.text

                inhibic = (arc_source in places_dict) and (arc_target in trans_dict)
                if top_net_data is not None:
                    inhibic = inhibic or ((arc_source in top_net_data[0]) and (arc_target in trans_dict)) or \
                          (arc_source in places_dict) and (arc_target in top_net_data[1])
                rever = (arc_target in places_dict) and (arc_source in trans_dict)
                if top_net_data is not None:
                    rever = rever or ((arc_target in top_net_data[0]) and (arc_source in trans_dict)) or \
                          (arc_target in places_dict) and (arc_source in top_net_data[1])

                if inhibic:
                    if arc_type == petri_properties.INHIBITOR_ARC and not isinstance(net, InhibitorNet):
                        if isinstance(net, ResetNet):
                            net = ResetInhibitorNet(name=net.name, places=net.places, transitions=net.transitions,
                                                    arcs=net.arcs, properties=net.properties)
                        else:
                            net = InhibitorNet(name=net.name, places=net.places, transitions=net.transitions,
                                               arcs=net.arcs, properties=net.properties)
                    if arc_type == petri_properties.RESET_ARC and not isinstance(net, ResetNet):
                        if isinstance(net, InhibitorNet):
                            net = ResetInhibitorNet(name=net.name, places=net.places,
                                                    transitions=net.transitions, arcs=net.arcs,
                                                    properties=net.properties)
                        else:
                            net = ResetNet(name=net.name, places=net.places,
                                           transitions=net.transitions, arcs=net.arcs,
                                           properties=net.properties)
                    # outer redirection
                    pdict = places_dict
                    tdict = trans_dict
                    if top_net_data and (arc_source in top_net_data[0]):
                        pdict = top_net_data[0]
                    elif top_net_data and (arc_target in top_net_data[1]):
                        tdict = top_net_data[1]
                    # redirect finish
                    a = add_arc_from_to(pdict[arc_source], tdict[arc_target], net, weight=arc_weight,
                                        type=arc_type)
                    for prop in arc_properties:
                        a.properties[prop] = arc_properties[prop]
                elif rever:
                    # outer redirection
                    pdict = places_dict
                    tdict = trans_dict
                    if top_net_data and (arc_source in top_net_data[1]):
                        tdict = top_net_data[1]
                    elif top_net_data and (arc_target in top_net_data[0]):
                        pdict = top_net_data[0]
                    # redirect finish
                    a = add_arc_from_to(tdict[arc_source], pdict[arc_target], net, weight=arc_weight,
                                        type=arc_type)
                    for prop in arc_properties:
                        a.properties[prop] = arc_properties[prop]

    if finalmarkings is not None:
        fmarking = Marking()
        for child in finalmarkings:
            for child2 in child:
                place_id = child2.get("idref")
                for child3 in child2:
                    if child3.tag.endswith("text"):
                        number = int(child3.text)
                        if number > 0:
                            fmarking[places_dict[place_id]] = number

    if variables is not None:
        net.properties[petri_properties.VARIABLES] = []
        for child in variables:
            variable_type = child.get("type")
            variable_name = ""
            for child2 in child:
                if child2.tag.endswith("name"):
                    variable_name = child2.text
            net.properties[petri_properties.VARIABLES].append({"type": variable_type, "name": variable_name})

    return net, marking, fmarking

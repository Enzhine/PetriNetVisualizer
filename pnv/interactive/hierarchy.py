from typing import Union

from PyQt5.QtGui import QStandardItemModel, QStandardItem


class HierNode:
    def __init__(self, name: str, parent: 'HierNode', value):
        self.name = name
        self.value = value
        self.__level = 0
        self.__children: list[HierNode] = []
        self.parent: Union[HierNode, None] = parent
        if self.parent:
            self.parent.add_child(self)

    def level(self):
        return self.__level

    def children(self):
        return self.__children

    def add_child(self, child: 'HierNode'):
        child.__level = self.__level + 1
        self.__children.append(child)

    def remove_child(self, child: 'HierNode'):
        child.__level = self.__level - 1
        self.__children.remove(child)

    def make_tree(self, root=None, hitem=None) -> QStandardItemModel:
        if root is None and hitem is None:
            root = self
            hitem = QStandardItemModel()
        for c in root.__children:
            c_item = QStandardItem(c.name)
            hitem.appendRow(c_item)
            if len(c.__children) != 0:
                self.make_tree(c, c_item)
        return hitem


class Hierarchical:
    def __init__(self):
        self.__hn: Union[HierNode, None] = None

    def hiernode_bound(self) -> Union[HierNode, None]:
        return self.__hn

    def hiernode_bind(self, obj: HierNode):
        self.__hn = obj

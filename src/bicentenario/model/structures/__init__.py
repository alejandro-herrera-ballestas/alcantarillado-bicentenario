"""Estructuras de datos implementadas en la Parte A.

Se re-exportan las clases para poder hacer::

    from bicentenario.model.structures import Queue, DoublyLinkedList

Los módulos de Persona B importan por ruta completa; estos alias son solo
comodidad y no cambian ningún contrato.
"""

from bicentenario.model.structures.node import Node
from bicentenario.model.structures.linked_list import LinkedList
from bicentenario.model.structures.doubly_linked_list import DoublyLinkedList
from bicentenario.model.structures.stack import Stack
from bicentenario.model.structures.queue import Queue
from bicentenario.model.structures.hash_table import HashTable
from bicentenario.model.structures.priority_queue import PriorityQueue

__all__ = [
    "Node",
    "LinkedList",
    "DoublyLinkedList",
    "Stack",
    "Queue",
    "HashTable",
    "PriorityQueue",
]

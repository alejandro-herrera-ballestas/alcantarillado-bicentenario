"""Pruebas de las estructuras de datos de la Parte A.

Se usa ``unittest`` (stdlib) para no añadir dependencias: ``requirements.txt``
aún no declara pytest y el proyecto se ejecuta en Python 3.15.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bicentenario.model.structures import (  # noqa: E402
    DoublyLinkedList,
    HashTable,
    LinkedList,
    Node,
    PriorityQueue,
    Queue,
    Stack,
)


class TestNode(unittest.TestCase):
    def test_value_and_links(self):
        first = Node(1)
        second = Node(2, prev=first)
        first.next = second
        self.assertEqual(first.value, 1)
        self.assertIs(first.next, second)
        self.assertIs(second.prev, first)


class TestLinkedList(unittest.TestCase):
    def test_append_prepend_and_iteration(self):
        items = LinkedList([1, 2])
        items.append(3)
        items.prepend(0)
        self.assertEqual(list(items), [0, 1, 2, 3])
        self.assertEqual(len(items), 4)
        self.assertEqual(items[2], 2)

    def test_insert_at_boundaries(self):
        items = LinkedList()
        items.insert_at(0, "b")       # lista vacía
        items.insert_at(0, "a")
        items.insert_at(2, "c")       # == len -> append
        self.assertEqual(items.to_list(), ["a", "b", "c"])
        with self.assertRaises(IndexError):
            items.insert_at(9, "x")

    def test_remove_and_find(self):
        items = LinkedList([1, 2, 3, 2])
        self.assertTrue(items.remove(2))
        self.assertEqual(items.to_list(), [1, 3, 2])
        self.assertFalse(items.remove(99))
        node = items.find(3)
        self.assertIsNotNone(node)
        items.remove_node(node)
        self.assertEqual(items.to_list(), [1, 2])

    def test_pop_and_clear(self):
        items = LinkedList([1, 2, 3])
        self.assertEqual(items.pop_first(), 1)
        self.assertEqual(items.pop_last(), 3)
        self.assertEqual(items.to_list(), [2])
        items.clear()
        self.assertTrue(items.is_empty())
        with self.assertRaises(IndexError):
            items.pop_first()


class TestDoublyLinkedList(unittest.TestCase):
    def test_append_iteration_and_len(self):
        items = DoublyLinkedList()
        items.append("a")
        items.push_back("b")
        items.append("c")
        self.assertEqual(list(items), ["a", "b", "c"])
        self.assertEqual(len(items), 3)
        self.assertEqual(items.get_at(2), "c")
        self.assertEqual(items[-1], "c")

    def test_cursor_navigation(self):
        items = DoublyLinkedList([0, 1, 2])
        self.assertEqual(items.reiniciar(), 0)
        self.assertEqual(items.siguiente(), 1)
        self.assertEqual(items.siguiente(), 2)
        self.assertEqual(items.siguiente(), 2)   # se queda en el último
        self.assertEqual(items.anterior(), 1)
        self.assertEqual(items.current(), 1)
        self.assertEqual(items.step, 1)

    def test_remove_node_keeps_structure(self):
        items = DoublyLinkedList([1, 2, 3])
        middle = items.find(2)
        items.remove_node(middle)
        self.assertEqual(items.to_list(), [1, 3])
        self.assertEqual(items.tail.value, 3)
        self.assertEqual(items.head.next.value, 3)

    def test_empty_cursor_raises(self):
        items = DoublyLinkedList()
        with self.assertRaises(IndexError):
            items.current()


class TestStack(unittest.TestCase):
    def test_lifo(self):
        stack = Stack()
        for value in (1, 2, 3):
            stack.push(value)
        self.assertEqual(len(stack), 3)
        self.assertEqual(stack.peek(), 3)
        self.assertEqual(stack.pop(), 3)
        self.assertEqual(stack.pop(), 2)
        self.assertEqual(list(stack), [1])

    def test_empty_stack(self):
        stack = Stack()
        self.assertTrue(stack.is_empty())
        with self.assertRaises(IndexError):
            stack.pop()
        with self.assertRaises(IndexError):
            stack.peek()


class TestQueue(unittest.TestCase):
    def test_fifo(self):
        queue = Queue()
        for value in (1, 2, 3):
            queue.enqueue(value)
        self.assertEqual(len(queue), 3)
        self.assertEqual(queue.peek(), 1)
        self.assertEqual(queue.dequeue(), 1)
        self.assertEqual(queue.dequeue(), 2)
        self.assertEqual(list(queue), [3])

    def test_aliases_used_by_simulator(self):
        queue = Queue([1, 2])
        queue.put(3)               # alias de enqueue
        self.assertEqual(queue.get(), 1)   # alias de dequeue
        self.assertEqual(queue.pop(), 2)   # alias de dequeue
        self.assertEqual(len(queue), 1)

    def test_empty_queue(self):
        queue = Queue()
        with self.assertRaises(IndexError):
            queue.dequeue()


class TestHashTable(unittest.TestCase):
    def test_put_get_update_remove(self):
        table = HashTable()
        table.put("P1", 10)
        table.put("P2", 20)
        self.assertEqual(table.get("P1"), 10)
        self.assertEqual(len(table), 2)
        table.put("P1", 15)                 # actualiza, no agrega
        self.assertEqual(table["P1"], 15)
        self.assertEqual(len(table), 2)
        self.assertTrue("P2" in table)
        self.assertTrue(table.remove("P1"))
        self.assertFalse(table.remove("P1"))
        self.assertEqual(table.keys(), ["P2"])

    def test_forced_collisions(self):
        table = HashTable(capacity=1)       # todas las claves colisionan
        for number in range(20):
            table.put(f"P{number}", number)
        self.assertEqual(len(table), 20)
        for number in range(20):
            self.assertEqual(table.get(f"P{number}"), number)
        self.assertEqual(table.get("P99"), None)

    def test_deterministic_iteration(self):
        first = HashTable()
        second = HashTable()
        for number in (1, 2, 3, 10, 20):
            first.put(f"P{number}", number)
            second.put(f"P{number}", number)
        self.assertEqual(first.items(), second.items())
        self.assertEqual(first.to_dict(), dict(second.items()))

    def test_resize_keeps_data(self):
        table = HashTable(capacity=2)
        for number in range(50):
            table.put(f"N{number}", number)
        self.assertEqual(len(table), 50)
        self.assertGreater(table.capacity, 2)
        self.assertEqual(table.get("N49"), 49)


class TestPriorityQueue(unittest.TestCase):
    def test_min_priority_and_stable_ties(self):
        queue = PriorityQueue()
        queue.push("third", 3)
        queue.push("first-a", 1)
        queue.push("second", 2)
        queue.push("first-b", 1)
        self.assertEqual([queue.pop() for _ in range(4)],
                         ["first-a", "first-b", "second", "third"])

    def test_empty(self):
        with self.assertRaises(IndexError):
            PriorityQueue().pop()


class TestIntegrationWithSimulator(unittest.TestCase):
    """El simulador de Persona B debe usar nuestras Queue/DoublyLinkedList."""

    def test_simulator_runs_with_our_structures(self):
        from bicentenario.model.domain import Basin, Pipe, Scenario
        from bicentenario.model.simulation.simulator import Simulator
        from bicentenario.model.simulation.snapshot import SimulationHistory

        dataset = SimpleNamespace(
            sources=["1"], sinks=["3"],
            pipes=[
                Pipe("P1", "1", "2", 0.3, 0.015, 0.01, 1.0, 10.0),
                Pipe("P2", "2", "3", 0.3, 0.015, 0.01, 1.0, 10.0),
            ],
            basins=[Basin(1.0, 1.0, node="1")],
            scenarios=[Scenario("2", 10.0, "Light rain")],
        )
        params = SimpleNamespace(duration_min=3.0, step_min=1.0, n_steps=3)
        history = Simulator(
            dataset, params,
            queue_factory=Queue,
            history_factory=lambda: SimulationHistory(storage=DoublyLinkedList()),
        ).run("2")

        self.assertEqual(len(history), 4)
        self.assertIsInstance(history.storage._linked, DoublyLinkedList)
        self.assertEqual(history.get_at(0).step, 0)
        self.assertEqual(history.get_at(3).time_min, 3.0)
        self.assertEqual(len(history.critical_rows(3)), 2)


if __name__ == "__main__":
    unittest.main()

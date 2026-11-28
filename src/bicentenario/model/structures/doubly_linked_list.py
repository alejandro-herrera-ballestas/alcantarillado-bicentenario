"""Lista doblemente enlazada implementada por los estudiantes (Parte A).

Es el almacenamiento del historial de Persona B: ``snapshot.py`` intenta
importar ``DoublyLinkedList`` de este módulo y solo necesita
``append``, ``__len__`` y ``__iter__`` (que entrega los snapshots, no nodos).

Además se ofrece navegación por cursor (``anterior``, ``siguiente``,
``reiniciar``), útil para el salto a instantes anteriores (RF09).
"""

from __future__ import annotations

from typing import Generic, Iterable, Iterator, TypeVar

from bicentenario.model.structures.node import Node

T = TypeVar("T")

__all__ = ["DoublyLinkedList"]


class DoublyLinkedList(Generic[T]):
    """Lista doblemente enlazada con cabeza, cola, tamaño y cursor.

    ``__iter__`` recorre **valores** en orden de inserción. El cursor se
    invalida ante cualquier cambio estructural y se recalcula al usarlo,
    de modo que no hay punteros colgantes tras borrar el nodo actual.
    """

    __slots__ = ("_head", "_tail", "_size", "_cursor_index", "_cursor_node")

    def __init__(self, values: Iterable[T] | None = None) -> None:
        self._head: Node[T] | None = None
        self._tail: Node[T] | None = None
        self._size = 0
        self._cursor_index = 0
        self._cursor_node: Node[T] | None = None
        if values is not None:
            for value in values:
                self.append(value)
            if self._size:
                self._cursor_node = self._head

    # ------------------------------------------------------------ consultas
    @property
    def head(self) -> Node[T] | None:
        """Primer nodo."""
        return self._head

    @property
    def tail(self) -> Node[T] | None:
        """Último nodo."""
        return self._tail

    def is_empty(self) -> bool:
        """``True`` si no hay elementos."""
        return self._size == 0

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._size > 0

    def __iter__(self) -> Iterator[T]:
        node = self._head
        while node is not None:
            yield node.value
            node = node.next

    def __contains__(self, value: object) -> bool:
        return self.find(value) is not None

    def __getitem__(self, index: int) -> T:
        return self.get_at(index)

    def __repr__(self) -> str:
        return f"DoublyLinkedList([{', '.join(repr(v) for v in self)}])"

    def _check_index(self, index: int, *, allow_end: bool = False) -> int:
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(f"El índice debe ser entero (recibido {index!r}).")
        if index < 0:
            index += self._size
        limit = self._size if allow_end else self._size - 1
        if not 0 <= index <= limit:
            raise IndexError(f"Índice {index} fuera de rango (tamaño {self._size}).")
        return index

    def node_at(self, index: int) -> Node[T]:
        """Nodo en ``index``; recorre desde el extremo más cercano."""
        index = self._check_index(index)
        if self._cursor_node is not None and self._cursor_index == index:
            return self._cursor_node
        if index <= self._size // 2:
            node = self._head
            for _ in range(index):
                assert node is not None
                node = node.next
        else:
            node = self._tail
            for _ in range(self._size - 1 - index):
                assert node is not None
                node = node.prev
        assert node is not None
        return node

    def get_at(self, index: int) -> T:
        """Valor en la posición ``index``."""
        return self.node_at(index).value

    def find(self, value: object) -> Node[T] | None:
        """Primer nodo con ese valor, o ``None``."""
        node = self._head
        while node is not None:
            if node.value == value:
                return node
            node = node.next
        return None

    def to_list(self) -> list[T]:
        """Copia de los valores en orden."""
        return list(self)

    # -------------------------------------------------------------- inserción
    def _invalidate_cursor(self) -> None:
        self._cursor_node = None

    def append(self, value: T) -> None:
        """Agrega al final; es el método que usa ``SimulationHistory``."""
        node = Node(value, prev=self._tail)
        if self._tail is None:
            self._head = self._tail = node
            self._cursor_index = 0
            self._cursor_node = node
        else:
            self._tail.next = node
            self._tail = node
            self._invalidate_cursor()
        self._size += 1

    # Alias para adaptadores externos (B acepta estos nombres).
    push_back = append
    add_last = append
    insert_last = append

    def prepend(self, value: T) -> None:
        """Agrega al principio."""
        node = Node(value, next=self._head)
        if self._head is None:
            self._tail = node
        else:
            self._head.prev = node
        self._head = node
        self._cursor_index += 1 if self._size else 0
        self._invalidate_cursor()
        self._size += 1

    push_front = prepend
    add_first = prepend

    def insert_at(self, index: int, value: T) -> None:
        """Inserta ``value`` antes de ``index`` (``len`` ⇒ al final)."""
        index = self._check_index(index, allow_end=True)
        if index == self._size:
            self.append(value)
            return
        if index == 0:
            self.prepend(value)
            return
        following = self.node_at(index)
        node = Node(value, next=following, prev=following.prev)
        assert following.prev is not None
        following.prev.next = node
        following.prev = node
        self._cursor_index = index if self._cursor_index >= index else self._cursor_index
        self._invalidate_cursor()
        self._size += 1

    # --------------------------------------------------------------- borrado
    def remove_node(self, node: Node[T]) -> None:
        """Elimina un nodo ya localizado (O(1) con sus punteros)."""
        if node.prev is not None:
            node.prev.next = node.next
        else:
            self._head = node.next
        if node.next is not None:
            node.next.prev = node.prev
        else:
            self._tail = node.prev
        if self._cursor_node is node:
            self._cursor_node = node.next or node.prev
        elif self._cursor_index > 0 and node.prev is not None:
            self._cursor_index -= 1
        node.prev = node.next = None
        self._size -= 1
        if self._size == 0:
            self._cursor_index = 0
            self._cursor_node = None
        else:
            self._cursor_index = min(self._cursor_index, self._size - 1)
            self._invalidate_cursor()

    def remove(self, value: T) -> bool:
        """Elimina la primera aparición de ``value``."""
        node = self.find(value)
        if node is None:
            return False
        self.remove_node(node)
        return True

    def clear(self) -> None:
        """Vacía la lista y reinicia el cursor."""
        self._head = self._tail = None
        self._size = 0
        self._cursor_index = 0
        self._cursor_node = None

    # ------------------------------------------------------------- navegación
    def current(self) -> T:
        """Valor señalado por el cursor."""
        if self._size == 0:
            raise IndexError("La lista está vacía.")
        return self.get_at(self._cursor_index)

    @property
    def step(self) -> int:
        """Índice del cursor."""
        return self._cursor_index

    def seek(self, index: int) -> T:
        """Coloca el cursor en ``index`` y devuelve su valor."""
        index = self._check_index(index)
        node = self.node_at(index)   # resolver antes de mover el cursor
        self._cursor_index = index
        self._cursor_node = node
        return node.value

    def reiniciar(self) -> T:
        """Cursor al primer elemento."""
        return self.seek(0)

    def anterior(self) -> T:
        """Retrocede el cursor un paso (se queda en 0)."""
        if self._size == 0:
            raise IndexError("La lista está vacía.")
        return self.seek(max(0, self._cursor_index - 1))

    def siguiente(self) -> T:
        """Avanza el cursor un paso (se queda en el último)."""
        if self._size == 0:
            raise IndexError("La lista está vacía.")
        return self.seek(min(self._size - 1, self._cursor_index + 1))

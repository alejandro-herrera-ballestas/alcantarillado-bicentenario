"""Lista enlazada simple implementada por los estudiantes (Parte A).

No se usa ``list`` de Python: esa estructura es un arreglo dinámico y no
permite insertar o eliminar en O(1) con una referencia al nodo. Aquí cada
elemento es un :class:`~bicentenario.model.structures.node.Node`.
"""

from __future__ import annotations

from typing import Generic, Iterable, Iterator, TypeVar

from bicentenario.model.structures.node import Node

T = TypeVar("T")

__all__ = ["LinkedList"]


class LinkedList(Generic[T]):
    """Lista enlazada simple con cabeza, cola y contador de tamaño.

    Complejidades: ``append``/``prepend`` O(1); ``get_at``/``insert_at``/
    ``remove`` O(n); ``__len__`` O(1).
    """

    __slots__ = ("_head", "_tail", "_size")

    def __init__(self, values: Iterable[T] | None = None) -> None:
        self._head: Node[T] | None = None
        self._tail: Node[T] | None = None
        self._size = 0
        if values is not None:
            for value in values:
                self.append(value)

    # ------------------------------------------------------------ consultas
    @property
    def head(self) -> Node[T] | None:
        """Primer nodo (o ``None`` si está vacía)."""
        return self._head

    @property
    def tail(self) -> Node[T] | None:
        """Último nodo (o ``None`` si está vacía)."""
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
        return f"LinkedList([{', '.join(repr(v) for v in self)}])"

    # ----------------------------------------------------------- localización
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
        """Nodo en la posición ``index`` (O(n))."""
        index = self._check_index(index)
        node = self._head
        for _ in range(index):
            assert node is not None
            node = node.next
        assert node is not None
        return node

    def get_at(self, index: int) -> T:
        """Valor en la posición ``index``."""
        return self.node_at(index).value

    def find(self, value: object) -> Node[T] | None:
        """Primer nodo cuyo valor es igual a ``value``, o ``None``."""
        node = self._head
        while node is not None:
            if node.value == value:
                return node
            node = node.next
        return None

    def to_list(self) -> list[T]:
        """Copia de los valores en orden de inserción."""
        return list(self)

    # -------------------------------------------------------------- inserción
    def append(self, value: T) -> None:
        """Agrega ``value`` al final (O(1))."""
        node = Node(value)
        if self._tail is None:
            self._head = self._tail = node
        else:
            self._tail.next = node
            self._tail = node
        self._size += 1

    def prepend(self, value: T) -> None:
        """Agrega ``value`` al principio (O(1))."""
        node = Node(value, next=self._head)
        if self._head is None:
            self._tail = node
        self._head = node
        self._size += 1

    def insert_at(self, index: int, value: T) -> None:
        """Inserta ``value`` antes de la posición ``index``.

        ``index == len(self)`` equivale a :meth:`append`.
        """
        index = self._check_index(index, allow_end=True)
        if index == self._size:
            self.append(value)
            return
        if index == 0:
            self.prepend(value)
            return
        previous = self.node_at(index - 1)
        node = Node(value, next=previous.next)
        previous.next = node
        self._size += 1

    # --------------------------------------------------------------- borrado
    def remove(self, value: T) -> bool:
        """Elimina la primera aparición de ``value``; devuelve si la hubo."""
        node = self.find(value)
        if node is None:
            return False
        self.remove_node(node)
        return True

    def remove_node(self, node: Node[T]) -> None:
        """Elimina un nodo ya localizado (O(n) porque busca su predecesor)."""
        if self._head is None:
            raise ValueError("La lista está vacía.")
        if node is self._head:
            self._head = node.next
            if self._head is None:
                self._tail = None
        else:
            previous = self._head
            while previous.next is not node:
                if previous.next is None:
                    raise ValueError("El nodo no pertenece a esta lista.")
                previous = previous.next
            previous.next = node.next
            if node is self._tail:
                self._tail = previous
        node.next = None
        self._size -= 1

    def pop_first(self) -> T:
        """Elimina y devuelve el primer valor."""
        if self._head is None:
            raise IndexError("La lista está vacía.")
        node = self._head
        self.remove_node(node)
        return node.value

    def pop_last(self) -> T:
        """Elimina y devuelve el último valor."""
        if self._tail is None:
            raise IndexError("La lista está vacía.")
        value = self._tail.value
        self.remove_node(self._tail)
        return value

    def clear(self) -> None:
        """Vacía la lista."""
        self._head = self._tail = None
        self._size = 0

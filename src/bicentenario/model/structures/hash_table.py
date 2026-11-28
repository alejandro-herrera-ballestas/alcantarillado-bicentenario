"""Tabla hash con encadenamiento separado, implementada por los estudiantes.

Python ya trae ``dict`` (una tabla hash en C), pero la guía exige implementar
las estructuras centrales. Aquí los cubos son :class:`LinkedList` propias.

El hash de cadenas es **propio y determinista** (FNV-1a de 32 bits) en lugar
del ``hash()`` de Python, que está aleatorizado por proceso. Así el orden de
iteración no cambia entre ejecuciones y se respeta el supuesto S6
(determinismo) de Persona B.
"""

from __future__ import annotations

from typing import Generic, Iterator, TypeVar

from bicentenario.model.structures.linked_list import LinkedList
from bicentenario.model.structures.node import Node

K = TypeVar("K")
V = TypeVar("V")

__all__ = ["HashTable"]


def _hash_key(key: object) -> int:
    """Hash determinista de 32 bits para claves (cadenas FNV-1a)."""
    if isinstance(key, str):
        value = 2166136261
        for character in key:
            value ^= ord(character)
            value = (value * 16777619) & 0xFFFFFFFF
        return value
    if isinstance(key, bool):
        return int(key)
    if isinstance(key, int):
        return key & 0xFFFFFFFF
    if isinstance(key, float):
        return int(key) & 0xFFFFFFFF
    return hash(key) & 0xFFFFFFFF


class HashTable(Generic[K, V]):
    """Tabla hash con *separate chaining* y redimensionado automático.

    Complejidad promedio O(1) para ``put``/``get``/``remove``; O(n) para
    ``items``. Expone una API parecida a ``dict`` para interoperar con el
    resto del proyecto sin adaptadores.
    """

    __slots__ = ("_buckets", "_size", "_max_load")

    def __init__(self, capacity: int = 8, max_load: float = 0.75) -> None:
        if capacity < 1:
            raise ValueError("La capacidad inicial debe ser al menos 1.")
        if not 0 < max_load < 1:
            raise ValueError("El factor de carga debe estar entre 0 y 1.")
        self._buckets: list[LinkedList[tuple[K, V]]] = [
            LinkedList() for _ in range(capacity)
        ]
        self._size = 0
        self._max_load = max_load

    # ------------------------------------------------------------- internos
    def _index(self, key: K) -> int:
        return _hash_key(key) % len(self._buckets)

    def _find(self, key: K) -> tuple[LinkedList[tuple[K, V]], Node[tuple[K, V]] | None]:
        bucket = self._buckets[self._index(key)]
        node = bucket.head
        while node is not None:
            if node.value[0] == key:
                return bucket, node
            node = node.next
        return bucket, None

    def _resize(self) -> None:
        entries = self.items()
        self._buckets = [LinkedList() for _ in range(len(self._buckets) * 2)]
        self._size = 0
        for key, value in entries:
            self.put(key, value)

    # ------------------------------------------------------------ consultas
    def get(self, key: K, default: V | None = None) -> V | None:
        """Valor de ``key``, o ``default`` si no existe."""
        _, node = self._find(key)
        return node.value[1] if node is not None else default

    def get_or_raise(self, key: K) -> V:
        """Valor de ``key``; lanza ``KeyError`` si no existe."""
        _, node = self._find(key)
        if node is None:
            raise KeyError(key)
        return node.value[1]

    def contains(self, key: K) -> bool:
        """``True`` si ``key`` está presente."""
        return self._find(key)[1] is not None

    def keys(self) -> list[K]:
        """Claves en orden determinista de cubo e inserción."""
        return [key for bucket in self._buckets for key, _ in bucket]

    def values(self) -> list[V]:
        """Valores en el mismo orden que :meth:`keys`."""
        return [value for bucket in self._buckets for _, value in bucket]

    def items(self) -> list[tuple[K, V]]:
        """Pares ``(clave, valor)`` en orden determinista."""
        return [entry for bucket in self._buckets for entry in bucket]

    def buckets(self) -> list[LinkedList[tuple[K, V]]]:
        """Vista de los cubos (útil para forzar colisiones en pruebas)."""
        return list(self._buckets)

    @property
    def capacity(self) -> int:
        """Número de cubos."""
        return len(self._buckets)

    def to_dict(self) -> dict[K, V]:
        """Copia a un ``dict`` nativo."""
        return dict(self.items())

    def clear(self) -> None:
        """Vacía la tabla sin cambiar el número de cubos."""
        self._buckets = [LinkedList() for _ in self._buckets]
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def __iter__(self) -> Iterator[K]:
        return iter(self.keys())

    def __contains__(self, key: object) -> bool:
        return self.contains(key)  # type: ignore[arg-type]

    def __getitem__(self, key: K) -> V:
        return self.get_or_raise(key)

    def __setitem__(self, key: K, value: V) -> None:
        self.put(key, value)

    def __delitem__(self, key: K) -> None:
        if not self.remove(key):
            raise KeyError(key)

    def __repr__(self) -> str:
        return f"HashTable({self.to_dict()!r})"

    # ------------------------------------------------------------ modificación
    def put(self, key: K, value: V) -> None:
        """Inserta o actualiza ``key``."""
        bucket, node = self._find(key)
        if node is not None:
            node.value = (key, value)
            return
        bucket.append((key, value))
        self._size += 1
        if self._size / len(self._buckets) > self._max_load:
            self._resize()

    def remove(self, key: K) -> bool:
        """Elimina ``key``; devuelve si estaba presente."""
        bucket, node = self._find(key)
        if node is None:
            return False
        bucket.remove_node(node)
        self._size -= 1
        return True

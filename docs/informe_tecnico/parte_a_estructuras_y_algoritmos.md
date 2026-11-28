# Parte A — Estructuras de datos y algoritmos

**Módulo:** `src/bicentenario/model/{structures,domain,graph,algorithms}` y `io/report_writer.py`
**Responsable:** Persona A
**Estado:** implementado y verificado contra el DataSet real (46 nodos, 59 tuberías).

---

## 1. Estructuras de datos implementadas

La guía exige que las estructuras centrales sean implementadas por los estudiantes.
Python proporciona `list`, `dict` (tabla hash en C), `collections.deque` y `heapq`,
pero **ninguna** se delega para las estructuras obligatorias.

| Estructura | Archivo | Implementación | Complejidades |
|---|---|---|---|
| `Node` | `structures/node.py` | Celda con `value`, `next`, `prev`; `__slots__` | O(1) acceso |
| `LinkedList` | `structures/linked_list.py` | Lista simple con cabeza, cola y contador | `append`/`prepend` O(1); `get_at`/`remove` O(n) |
| `DoublyLinkedList` | `structures/doubly_linked_list.py` | Lista doble + cursor (`get_at`, `anterior`, `siguiente`, `reiniciar`); `__iter__` entrega **valores** | inserción/borrado por nodo O(1); búsqueda O(n) |
| `Stack` | `structures/stack.py` | Nodos apilados en la cima | `push`/`pop`/`peek` O(1) |
| `Queue` | `structures/queue.py` | Frente, cola y contador; `enqueue`/`dequeue` | O(1); `__len__` O(1) |
| `HashTable` | `structures/hash_table.py` | *Separate chaining* con `LinkedList`, redimensionado al 75 % de carga | `put`/`get`/`remove` O(1) promedio |
| `PriorityQueue` | `structures/priority_queue.py` | Heap binario propio, estable por contador de inserción | `push`/`pop` O(log n) |

### Decisiones relevantes

- **Hash determinista:** se usa FNV-1a de 32 bits propio en vez del `hash()` de Python
  (aleatorizado por proceso). Así el orden de iteración es estable y se conserva el
  supuesto S6 de repetibilidad de Persona B.
- **Contrato con Persona B:** `Queue` expone `enqueue`/`dequeue` y `DoublyLinkedList`
  expone `append`/`__len__`/`__iter__`, que son exactamente los nombres que buscan
  `_QueueAdapter` (`simulator.py`) y `_DllAdapter` (`snapshot.py`). No fue necesario
  modificar ningún archivo de B.
- **Alias de compatibilidad:** `push_back`/`add_last`/`insert_last` en la lista doble y
  `push`/`pop`/`put`/`get` en la cola, para tolerar adaptadores externos.

---

## 2. Dominio y grafo

- `domain/{manhole,pipe,basin,scenario}.py`: dataclasses inmutables con los mismos
  nombres de campo que `io.records` (`PipeRecord`, `BasinRecord`, `ScenarioRecord`).
  `from_record()` convierte por atributos, sin importar `io` desde `model` (evita
  import circular).
- `graph/directed_graph.py`: **lista de adyacencia saliente y entrante**. El `dict`
  se usa solo como contenedor indexado; la consulta por ID usa la `HashTable` propia.
  Las adyacencias se devuelven ordenadas con `natural_key` (P2 < P10) para que los
  recorridos sean deterministas.
- `graph/topology.py`: detección de ciclos (DFS iterativo con colores y `Stack`),
  alcanzabilidad desde fuentes y hacia sumideros (BFS con `Queue`), extremos muertos
  y orden topológico (Kahn con `Queue`). Persona C puede delegar aquí sus validaciones
  actuales sin cambiar los mensajes de `io/validators.py`.

**Verificación con el DataSet real:** 46 nodos, 59 tuberías, 8 fuentes
(`1, 6, 9, 17, 18, 19, 20, 27`), 1 sumidero (`31`), 0 ciclos y los 46 nodos son
alcanzables desde las fuentes y pueden llegar al sumidero.

---

## 3. Algoritmos

| Algoritmo | Archivo | Estructura usada | Resultado |
|---|---|---|---|
| BFS | `algorithms/bfs.py` | `Queue` | Orden de visita y árbol de padres |
| DFS | `algorithms/dfs.py` | `Stack` | Orden de visita (iterativo, sin recursión) |
| Reconstrucción de caminos | `algorithms/bfs.py` | `Stack` | Camino `start → goal` sin invertir con `reverse()` |
| Búsqueda por ID | `algorithms/search.py` | `HashTable` | Tubería/nodo/escenario con tolerancia a mayúsculas y prefijo `P` |
| Tuberías críticas | `algorithms/critical_pipes.py` | — | Utilización máxima por tubería, clasificación 25/50/75/100 y orden determinista |
| Balance de masa | `algorithms/mass_balance.py` | — | Identidad `Σ entrante = Σ ofrecido + Σ sumidero + Σ extremo muerto` |
| Comparación de escenarios | `algorithms/scenario_comparison.py` | — | Delta de utilización por tubería y resumen |
| Reporte TXT/CSV | `io/report_writer.py` | `csv` (stdlib) para escritura | `resumen.csv`, críticas, comparación e historial |

La identidad del balance de masa se deriva del modelo de Persona B: en cada nodo no
sumidero, la suma de `PipeState.flow` de las tuberías salientes debe igualar
`NodeState.inflow`; en los sumideros el caudal se descarga (S8) y en los extremos
muertos se acumula (S12c). El agua en tránsito no está expuesta en los `Snapshot`
y se documenta como limitación del verificador.

---

## 4. Pruebas

- `tests/test_structures.py`: 19 pruebas de FIFO/LIFO, cursor, colisiones forzadas,
  redimensionado, heap e integración real con `Simulator`.
- `tests/test_graph_algorithms.py`: 23 pruebas de BFS/DFS contra una red resuelta a
  mano, topología, límites de color, balance (caso correcto y fuga introducida),
  comparación y exportación.

```
python -m unittest discover -s tests -p "test_*.py"
Ran 42 tests ... OK
```

**Verificación end-to-end** con el dataset real y la simulación de B usando
`queue_factory=Queue` y `history_factory=lambda: SimulationHistory(storage=DoublyLinkedList())`:

- 31 snapshots para 30 pasos; dos ejecuciones del mismo escenario idénticas (S6).
- Balance de masa: 31 pasos revisados, 0 incidencias.
- Críticas y comparación exportadas a TXT/CSV sin errores.

---

## 5. Puntos de convivencia con B y C

- **No se modificó** ningún archivo de `model/simulation/`, `io/loader.py`,
  `io/validators.py`, `io/records.py`, `controller/`, `view/` ni `main.py`.
- C mantiene sus validaciones de topología en `io/validators.py`; si decide delegar
  en `graph/topology.py`, debe ser C quien edite ese archivo.
- Los umbrales de color están duplicados deliberadamente en `critical_pipes.py`
  (constantes locales) para que `model` no importe `view/color_scale.py`. Si se
  cambia la escala, sincronizar ambos módulos.
- `openpyxl` no está instalado en el entorno actual: la carga desde Excel de C
  requiere añadirlo a `requirements.txt`. La verificación de esta parte leyó el
  XLSX directamente desde su XML interno, sin dependencias.

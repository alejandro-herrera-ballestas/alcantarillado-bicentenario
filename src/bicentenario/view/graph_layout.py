"""Disposición (posiciones x, y) de los nodos para dibujar la red.

 Capa de cada nodo = camino más largo desde una fuente (el agua fluye de
izquierda a derecha y el sumidero queda a la derecha).
Las fuentes se acercan a su primer destino para acortar tuberías largas.
Una tubería que salta varias capas se parte en tramos con nodos "virtuales"
así reservan su propio carril y la línea no pasa por
detrás de otros nodos, lo que parecería una conexión que no existe.
Dentro de cada capa se ordenan los nodos (reales y virtuales) con el método
del baricentro; se repiten barridos para reducir cruces de tuberías.

"""

from __future__ import annotations

from collections import defaultdict, deque

from bicentenario.io.records import natural_key

Position = tuple[float, float]
EdgePaths = dict[tuple[str, str], list[Position]]


def compute_layout(node_ids, edges, *, coords: dict[str, Position] | None = None,
                   sweeps: int = 8) -> dict[str, Position]:
    """Posiciones normalizadas ``{nodo: (x, y)}`` con x, y en [0, 1].
"""
    return layered_layout(node_ids, edges, coords=coords, sweeps=sweeps)[0]


def layered_layout(node_ids, edges, *, coords: dict[str, Position] | None = None,
                   sweeps: int = 8) -> tuple[dict[str, Position], EdgePaths]:
    """Como ``compute_layout`` pero devuelve también los puntos intermedios de las tuberías.

    Resultado: ``(posiciones, trayectos)``. ``trayectos[(a, b)]`` es la lista de
    puntos normalizados por los que debe pasar la tubería a → b entre sus
    extremos; si la tubería va recta no aparece en el diccionario.
    """
    nodes = sorted(set(node_ids), key=natural_key)
    if not nodes:
        return {}, {}

    if coords and all(n in coords for n in nodes):
        return _normalize({n: coords[n] for n in nodes}), {}

    known = set(nodes)
    edge_list = sorted({(a, b) for a, b in edges if a in known and b in known and a != b},
                       key=lambda e: (natural_key(e[0]), natural_key(e[1])))
    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, list[str]] = defaultdict(list)
    for a, b in edge_list:
        outgoing[a].append(b)
        incoming[b].append(a)

    layer = _assign_layers(nodes, outgoing, incoming)

    # Acercar las fuentes (sin entradas) a su destino más próximo.
    for node in nodes:
        if not incoming[node] and outgoing[node]:
            layer[node] = max(layer[node], min(layer[s] for s in outgoing[node]) - 1)

    # Eliminar capas vacías (por si todas las fuentes se movieron): 0, 1, 2, ...
    rank = {value: i for i, value in enumerate(sorted(set(layer.values())))}
    layer = {n: rank[v] for n, v in layer.items()}
    last_layer = max(layer.values())

    # Nodos virtuales para las tuberías que saltan capas (a → v1 → v2 → ... → b).
    chains: dict[tuple[str, str], list[str]] = {}
    v_out: dict[str, list[str]] = defaultdict(list)
    v_in: dict[str, list[str]] = defaultdict(list)
    for a, b in edge_list:
        span = layer[b] - layer[a]
        if span <= 1:                       # tramo normal (o hacia atrás en un ciclo)
            v_out[a].append(b)
            v_in[b].append(a)
            continue
        chain = [f"\x00{a}>{b}#{k}" for k in range(1, span)]
        for k, name in enumerate(chain, start=1):
            layer[name] = layer[a] + k
        chains[(a, b)] = chain
        path = [a, *chain, b]
        for u, v in zip(path, path[1:]):
            v_out[u].append(v)
            v_in[v].append(u)

    columns: dict[int, list[str]] = defaultdict(list)
    for node in sorted(layer, key=natural_key):
        columns[layer[node]].append(node)
    ordered = {k: sorted(v, key=natural_key) for k, v in columns.items()}

    y = _initial_y(ordered)
    for _ in range(sweeps):
        _sweep(range(1, last_layer + 1), ordered, y, v_in)
        _sweep(range(last_layer - 1, -1, -1), ordered, y, v_out)

    def x_of(name: str) -> float:
        return layer[name] / last_layer if last_layer else 0.5

    positions = {node: (x_of(node), y[node]) for node in nodes}
    paths = {edge: [(x_of(v), y[v]) for v in chain] for edge, chain in chains.items()}
    return positions, paths


def _assign_layers(nodes, outgoing, incoming) -> dict[str, int]:
    """Camino más largo desde las fuentes (orden de Kahn). Tolera ciclos."""
    layer = {n: 0 for n in nodes}
    pending = {n: len(incoming[n]) for n in nodes}
    queue = deque(n for n in nodes if pending[n] == 0)
    done = set()
    while queue:
        node = queue.popleft()
        done.add(node)
        for nxt in outgoing[node]:
            layer[nxt] = max(layer[nxt], layer[node] + 1)
            pending[nxt] -= 1
            if pending[nxt] == 0:
                queue.append(nxt)
    if len(done) < len(nodes):          # ciclos: van después de todo lo demás
        base = max(layer[n] for n in done) + 1 if done else 0
        for n in nodes:
            if n not in done:
                layer[n] = max(layer[n], base)
    return layer


def _initial_y(ordered: dict[int, list[str]]) -> dict[str, float]:
    y = {}
    for members in ordered.values():
        for i, node in enumerate(members):
            y[node] = (i + 0.5) / len(members)
    return y


def _sweep(layers, ordered, y, neighbours) -> None:
    """Reordena cada capa según la posición media de sus vecinos."""
    for k in layers:
        members = ordered.get(k)
        if not members:
            continue

        def barycentre(node: str) -> float:
            near = neighbours[node]
            return sum(y[v] for v in near) / len(near) if near else y[node]

        members.sort(key=lambda n: (barycentre(n), natural_key(n)))
        for i, node in enumerate(members):
            y[node] = (i + 0.5) / len(members)


def _normalize(positions: dict[str, Position]) -> dict[str, Position]:
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]

    def scale(value: float, low: float, high: float) -> float:
        return (value - low) / (high - low) if high > low else 0.5

    return {n: (scale(p[0], min(xs), max(xs)), scale(p[1], min(ys), max(ys)))
            for n, p in positions.items()}
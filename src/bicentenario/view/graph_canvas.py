"""Dibujo de la red sobre un lienzo (RF03, RF07, RF08).

No importa Tkinter: recibe un ``tk.Canvas`` ya creado y solo usa sus métodos
(create_line, itemconfigure, find_overlapping...). Eso permite probar toda la
lógica de dibujo y de clic con un lienzo falso (tests/test_graph_canvas.py).

Convenciones de dibujo
* Tubería = línea con flecha (de nodo inicial a nodo final), coloreada según la
  utilización. Sin dato (simulación sin iniciar) = gris.
* Nodo = círculo blanco. Fuente = círculo celeste con borde azul grueso.
  Sumidero = cuadrado negro.
* La tubería seleccionada se resalta con un halo negro y su ID.
"""

from __future__ import annotations

import math

from bicentenario.view.color_scale import NO_DATA_COLOR

SOURCE_FILL, SOURCE_OUTLINE = "#BBDEFB", "#0D47A1"
SINK_FILL = "#212121"
NODE_FILL, NODE_OUTLINE = "#FFFFFF", "#444444"
HALO_COLOR = "#000000"
FONT = ("Helvetica", 8, "bold")


class GraphCanvas:
    PAD = 46            # margen en píxeles alrededor de la red
    NODE_RADIUS = 12
    PIPE_WIDTH = 4
    HALO_WIDTH = 9
    HIT_RADIUS = 6      # tolerancia (px) al hacer clic sobre una tubería

    def __init__(self, canvas, on_pipe_selected=None):
        """``on_pipe_selected(pipe_id | None)`` se llama al hacer clic (None = clic en vacío)."""
        self.canvas = canvas
        self._on_pipe_selected = on_pipe_selected
        self._layout: dict[str, tuple[float, float]] = {}
        self._paths: dict[tuple[str, str], list[tuple[float, float]]] = {}   # puntos intermedios
        self._pipes: list[tuple[str, str, str]] = []        # (id, nodo inicial, nodo final)
        self._index_by_id: dict[str, int] = {}
        self._sources: set[str] = set()
        self._sinks: set[str] = set()
        self._colors: dict[str, str] = {}
        self._selected: str | None = None
        canvas.bind("<Configure>", self._on_resize)
        canvas.bind("<Button-1>", self._on_click)

    # ------------------------------------------------------------------ datos
    def set_network(self, layout, pipes, sources, sinks, paths=None) -> None:
        """Define la red a dibujar. ``pipes``: objetos con ``id``, ``from_node``, ``to_node``.
        ``paths`` (opcional): ``{(nodo_inicial, nodo_final): [(x, y), ...]}`` con los puntos
        intermedios, normalizados como ``layout``, por los que pasa una tubería larga para
        no tapar otros nodos .
        """
        self._layout = dict(layout)
        self._paths = {edge: list(points) for edge, points in (paths or {}).items()}
        self._pipes = [(p.id, p.from_node, p.to_node) for p in pipes]
        self._index_by_id = {pid: i for i, (pid, _, _) in enumerate(self._pipes)}
        self._sources, self._sinks = set(sources), set(sinks)
        self._colors = {}
        self._selected = None
        self.redraw()

    def set_colors(self, colors: dict[str, str]) -> None:
        """Pinta tuberías: ``{id_tubería: color_hex}``. IDs desconocidos se ignoran."""
        for pipe_id, color in colors.items():
            index = self._index_by_id.get(pipe_id)
            if index is None:
                continue
            self._colors[pipe_id] = color
            self.canvas.itemconfigure(f"pipe:{index}", fill=color)

    def clear_colors(self) -> None:
        """Vuelve todas las tuberías al color "sin dato"."""
        self._colors = {}
        for index in range(len(self._pipes)):
            self.canvas.itemconfigure(f"pipe:{index}", fill=NO_DATA_COLOR)

    def select_pipe(self, pipe_id: str | None) -> None:
        """Resalta una tubería (o quita la selección con ``None``)."""
        self._selected = pipe_id if pipe_id in self._index_by_id else None
        self._draw_selection()

    @property
    def selected(self) -> str | None:
        return self._selected

    # ---------------------------------------------------------------- dibujo
    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        if not self._layout:
            return
        width, height = self._size()
        pixels = {n: self._to_pixels(xy, width, height) for n, xy in self._layout.items()}

        for index, (pipe_id, _a, _b) in enumerate(self._pipes):
            points = self._pipe_points(pipe_id, width, height)
            if points is None:
                continue
            canvas.create_line(*[value for point in points for value in point],
                               width=self.PIPE_WIDTH, arrow="last",
                               arrowshape=(11, 13, 5), capstyle="round", joinstyle="round",
                               fill=self._colors.get(pipe_id, NO_DATA_COLOR),
                               tags=("pipe", f"pipe:{index}"))

        r = self.NODE_RADIUS
        for node, (x, y) in pixels.items():
            if node in self._sinks:
                canvas.create_rectangle(x - r, y - r, x + r, y + r, fill=SINK_FILL,
                                        outline="black", width=1, tags=("node",))
                text_color = "white"
            else:
                is_source = node in self._sources
                canvas.create_oval(x - r, y - r, x + r, y + r,
                                   fill=SOURCE_FILL if is_source else NODE_FILL,
                                   outline=SOURCE_OUTLINE if is_source else NODE_OUTLINE,
                                   width=3 if is_source else 1, tags=("node",))
                text_color = "black"
            canvas.create_text(x, y, text=node, font=FONT, fill=text_color, tags=("node",))
        self._draw_selection()

    def _draw_selection(self) -> None:
        canvas = self.canvas
        canvas.delete("selection")
        if self._selected is None or not self._layout:
            return
        pipe_id = self._selected
        width, height = self._size()
        points = self._pipe_points(pipe_id, width, height)
        if points is None:
            return
        canvas.create_line(*[value for point in points for value in point],
                           width=self.HALO_WIDTH, fill=HALO_COLOR,
                           capstyle="round", joinstyle="round", tags=("selection",))
        # El ID se escribe sobre el tramo más largo de la tubería.
        (x1, y1), (x2, y2) = max(zip(points, points[1:]),
                                 key=lambda seg: math.hypot(seg[1][0] - seg[0][0],
                                                            seg[1][1] - seg[0][1]))
        canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2 - 14, text=pipe_id, fill=HALO_COLOR,
                           font=FONT, tags=("selection",))
        canvas.tag_lower("selection")       # el halo queda debajo de las tuberías

    # ------------------------------------------------------------- geometría
    def _size(self) -> tuple[int, int]:
        # Antes de mostrarse, Tk informa tamaño 1x1: se usa un mínimo razonable.
        return max(int(self.canvas.winfo_width()), 300), max(int(self.canvas.winfo_height()), 200)

    def _to_pixels(self, position, width, height) -> tuple[float, float]:
        x, y = position
        return (self.PAD + x * (width - 2 * self.PAD), self.PAD + y * (height - 2 * self.PAD))

    def _pipe_points(self, pipe_id: str, width: int, height: int):
        """Puntos (en pixeles) de la tubería: inicio, puntos intermedios y fin.

        Los extremos se acortan para no quedar tapados por los nodos. Devuelve
        ``None`` si algún extremo no tiene posición.
        """
        _, a, b = self._pipes[self._index_by_id[pipe_id]]
        if a not in self._layout or b not in self._layout:
            return None
        start = self._to_pixels(self._layout[a], width, height)
        end = self._to_pixels(self._layout[b], width, height)
        middle = [self._to_pixels(p, width, height) for p in self._paths.get((a, b), ())]
        if not middle:
            return list(self._shorten(start, end))
        return [self._toward(start, middle[0]), *middle, self._toward(end, middle[-1])]

    def _toward(self, point, target):
        """Mueve ``point`` hacia ``target`` el espacio que ocupa un nodo (si cabe)."""
        (x1, y1), (x2, y2) = point, target
        length = math.hypot(x2 - x1, y2 - y1)
        gap = self.NODE_RADIUS + 1
        if length <= gap:
            return point
        return (x1 + (x2 - x1) / length * gap, y1 + (y2 - y1) / length * gap)

    def _shorten(self, start, end):
        """Acorta la línea para que no quede tapada por los círculos de los nodos."""
        (x1, y1), (x2, y2) = start, end
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        gap = self.NODE_RADIUS + 1
        if length <= 2 * gap:
            return start, end
        ux, uy = dx / length, dy / length
        return (x1 + ux * gap, y1 + uy * gap), (x2 - ux * gap, y2 - uy * gap)

    # --------------------------------------------------------------- clics
    def pipe_at(self, x: float, y: float) -> str | None:
        """ID de la tubería bajo el punto (x, y) en píxeles, o ``None``."""
        r = self.HIT_RADIUS
        for item in reversed(self.canvas.find_overlapping(x - r, y - r, x + r, y + r)):
            for tag in self.canvas.gettags(item):
                if tag.startswith("pipe:"):
                    return self._pipes[int(tag[5:])][0]
        return None

    def _on_click(self, event) -> None:
        pipe_id = self.pipe_at(event.x, event.y)
        self.select_pipe(pipe_id)
        if self._on_pipe_selected is not None:
            self._on_pipe_selected(pipe_id)

    def _on_resize(self, _event) -> None:
        self.redraw()

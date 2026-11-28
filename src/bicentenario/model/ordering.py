"""Orden «natural» de identificadores, compartido por grafo y algoritmos.

Es el mismo criterio que ``bicentenario.io.records.natural_key`` (P2 < P10).
Se reproduce aquí para que ``model`` no dependa del paquete ``io`` y no se
forme un import circular.
"""

from __future__ import annotations

import re

__all__ = ["natural_key"]


def natural_key(text: object) -> list[tuple[int, int, str]]:
    """Clave de ordenación natural: números antes que letras y P2 < P10."""
    parts = re.split(r"(\d+)", str(text))
    return [
        (0, int(part), "") if part.isdigit() else (1, 0, part.casefold())
        for part in parts
        if part != ""
    ]

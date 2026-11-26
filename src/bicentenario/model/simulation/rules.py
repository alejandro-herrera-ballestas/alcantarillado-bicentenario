"""

implementacion de los supuestos en datos basicos (sin estructuras, debe actualizarse luego de los
cambios de ismael)

Supuestos citados:
    S4    Tiempo discreto: el paso de simulación es ``step_min`` minutos.
    S9    Velocidad de referencia ``V`` (constante y configurable).
    S9b   Tiempo de tránsito mínimo de 1 paso.
    S9c   Redondeo hacia arriba (``ceil``) del tiempo de tránsito.
    S11   Reparto de caudal proporcional a la capacidad de salida.
    S11b  Conservación de masa en el reparto.
    S12   Utilización ``O = Q / Qmax · 100`` (puede superar 100 %).
    S12b  Sobrecarga: se transporta como máximo ``Qmax``; el exceso se retiene.
    S12c  Los nodos sin salida acumulan todo su exceso.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

__all__ = [
    "MIN_TRANSIT_STEPS",
    "REFERENCE_VELOCITY_M_S",
    "SECONDS_PER_MINUTE",
    "route_with_storage",
    "split_capacity",
    "split_flow",
    "transit_steps",
    "utilization_pct",
]

#: Velocidad de referencia del agua, en m/s (supuesto S9; a confirmar con el docente).
REFERENCE_VELOCITY_M_S: float = 1.0

#: Segundos que tiene un minuto (conversión de unidades para el tránsito, S9).
SECONDS_PER_MINUTE: float = 60.0

#: Toda tubería tarda al menos un paso de simulación (supuesto S9b).
MIN_TRANSIT_STEPS: int = 1


# ---------------------------------------------------------------------------
# Validaciones con numeros
# ---------------------------------------------------------------------------
def _finite(value: float, name: str) -> float:
    """Convierte ``value`` en ``float`` y exige que sea un número finito."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} debe ser un número (recibido {value!r}).")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} debe ser un número finito (recibido {value!r}).")
    return number


def _positive(value: float, name: str) -> float:
    """Exige un número finito **mayor que 0**."""
    number = _finite(value, name)
    if number <= 0:
        raise ValueError(f"{name} debe ser mayor que 0 (recibido {value!r}).")
    return number


def _non_negative(value: float, name: str) -> float:
    """Exige un número finito **mayor o igual que 0**."""
    number = _finite(value, name)
    if number < 0:
        raise ValueError(f"{name} no puede ser negativo (recibido {value!r}).")
    return number


# ---------------------------------------------------------------------------
# Supuestos de transito (S9)
# ---------------------------------------------------------------------------
def transit_steps(
    length_m: float,
    velocity_m_s: float = REFERENCE_VELOCITY_M_S,
    step_min: float = 1.0,
) -> int:
    """pasos de simulación que tarda un flujo en recorrer una tubería.
        si la tubería es muy corta, se tarda al menos un paso (S9b).
        si la tubería es muy larga, se redondea hacia arriba (S9c).
        si la velocidad de referencia es muy baja, se tarda más pasos (S9).
        si el paso de simulación es muy grande, se tarda menos pasos (S4).
        si la velocidad de referencia es muy alta, se tarda menos pasos (S9).
    """
    length = _positive(length_m, "La longitud de la tubería (m)")
    velocity = _positive(velocity_m_s, "La velocidad de referencia (m/s)")
    step = _positive(step_min, "El paso de simulación (min)")

    meters_per_step = velocity * SECONDS_PER_MINUTE * step
    return max(MIN_TRANSIT_STEPS, math.ceil(length / meters_per_step))


# ---------------------------------------------------------------------------
# Reparto de caudal en pozos (S11, S11b)
# ---------------------------------------------------------------------------
def split_flow(total_flow: float, capacities: Sequence[float]) -> list[float]:
    
    """reparte un caudal total entre varias salidas según sus capacidades relativas.
    Si el caudal total es 0, todas las salidas reciben 0. Si la capacidad total es 0, 
    se reparte el caudal total por igual entre todas las salidas. 
    Se conserva la masa (S11b) y se corrige el residuo de coma flotante.
    """
    total = _non_negative(total_flow, "El caudal total")
    if len(capacities) == 0:
        raise ValueError("Se necesita al menos una salida para repartir el caudal.")

    weights = [_non_negative(capacity, "La capacidad de una salida") for capacity in capacities]
    count = len(weights)

    if total == 0.0:
        return [0.0] * count

    total_capacity = math.fsum(weights)
    if total_capacity <= 0.0:
        return [total / count] * count

    shares = [total * weight / total_capacity for weight in weights]

    # Corrige el residuo de coma flotante para conservar la masa (S11b).
    residue = total - math.fsum(shares)
    if residue:
        last = max((index for index, weight in enumerate(weights) if weight > 0.0))
        shares[last] += residue
    return shares


# ---------------------------------------------------------------------------
# Utilización de la capacidad (S12, S12d)
# ---------------------------------------------------------------------------
def utilization_pct(flow: float, qmax: float) -> float:
    """Porcentaje de utilización de la capacidad de una tubería.
    si el caudal ofrecido es 0, la utilización es 0 %. 
    Si el caudal ofrecido supera la capacidad máxima, la utilización puede superar 100 % (S12).
    """
    offered = _non_negative(flow, "El caudal ofrecido")
    capacity = _positive(qmax, "La capacidad máxima (Qmax)")
    return offered / capacity * 100.0


# ---------------------------------------------------------------------------
# Sobrecarga y retención de excesos (S12b, S12c)
# ---------------------------------------------------------------------------
def split_capacity(flow: float, qmax: float) -> tuple[float, float]:
    """Separa el caudal ofrecido en ``(transportado, exceso)``.

    Solo se transporta hasta ``Qmax``; el resto es **exceso** que debe
    retenerse en el pozo de aguas arriba y no puede desaparecer del modelo
    (S12b).
    """
    offered = _non_negative(flow, "El caudal ofrecido")
    capacity = _positive(qmax, "La capacidad máxima (Qmax)")
    if offered <= capacity:
        return offered, 0.0
    return capacity, offered - capacity


def route_with_storage(incoming: float, stored: float, qmax: float) -> tuple[float, float]:
    """Aplica la retención de exceso de un pozo en un paso.

    Primero se reintenta evacuar lo retenido en pasos anteriores y luego se
    atiende el caudal nuevo (FIFO por paso): ``disponible = stored + incoming``.
    Se transporta como máximo ``Qmax`` y lo que no cabe queda **retenido** para
    el paso siguiente (S12b). Un nodo sin salida (``qmax`` no aplicable) debe
    tratarse fuera de esta función: aquí ``qmax`` siempre es positivo.
    """
    new_flow = _non_negative(incoming, "El caudal entrante")
    previous = _non_negative(stored, "El exceso retenido")
    capacity = _positive(qmax, "La capacidad máxima (Qmax)")

    available = previous + new_flow
    transported = min(available, capacity)
    retained = available - transported
    return transported, retained

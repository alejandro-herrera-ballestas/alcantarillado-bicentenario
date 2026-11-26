# Supuestos del modelo de simulación — Red de Alcantarillado Ciudad Bicentenario

**Módulo:** `src/bicentenario/model/simulation/` (Persona B)
**Versión:** 1.0 — PARTE 1 (supuestos y reglas hidráulicas)
**Referencias:** Guía del proyecto, secciones 5.2 (método racional), 5.4 (transporte
y tiempos de tránsito), 5.5 (utilización y sobrecargas) y 15 (alcance del modelo).

Este documento define formalmente todos los supuestos del modelo computacional.
Cada supuesto tiene un identificador (`S1`…`S12`) que se cita en los docstrings de
`rules.py`, `rational_method.py`, `snapshot.py` y `simulator.py`, y en las pruebas
de `tests/test_simulation.py`.

---

## 1. Supuestos generales

| ID | Supuesto | Justificación |
|----|----------|---------------|
| **S1** | La red se representa como **grafo dirigido**: vértices = pozos/fuentes/sumideros, aristas = tuberías, con la dirección del sentido previsto de circulación. | Guía §5.1; RF02. |
| **S2** | Las **capacidades máximas `Qmax` son datos de entrada** provistos por el docente (Manning a tubo lleno). **No se recalculan** en la simulación; solo se usan para evaluar utilización y sobrecarga. | Guía §5.3 y §15. |
| **S3** | No se incorpora caudal sanitario horario (no hay datos en el DataSet). Solo escorrentía pluvial. | Guía §5.2 ("si se dispone…"). |
| **S4** | El tiempo es **discreto**: paso `Δt = step_min` minutos (RF05), duración total `duration_min`, con `n_steps = duration/step` exacto. La simulación produce `n_steps + 1` estados (paso 0 = condición inicial), numerados `t = 0 … n_steps`. | `SimulationParams` de Persona C; RF06. |
| **S5** | Cada escenario de precipitación tiene **intensidad `I` constante (mm/h) durante toda la simulación** (perfil rectangular). `I = 0` ⇒ tiempo seco, sin aportes. | Escenarios del DataSet (0/10/30/60/100 mm/h); guía §5.2. |
| **S6** | El modelo es **determinista**: mismo dataset + mismo escenario + mismos parámetros ⇒ **historial idéntico** (bit a bit). No hay aleatoriedad ni dependencia de orden de iteración de diccionarios. | Criterio de validación "consistencia al repetir un mismo escenario". |
| **S7** | El indicador es la **utilización de la capacidad de transporte**, no el llenado físico de la sección transversal (no se modela profundidad, presión ni ecuaciones de Saint-Venant). | Guía §5.5 y §15. |
| **S8** | El **sumidero (PTAR Punta Canoa) descarga el agua fuera del modelo**: lo que llega al nodo sumidero se retira en ese mismo paso y no se acumula ni se reparte. | RF10/guía §5.1. |

---

## 2. Velocidad de referencia y tiempo de tránsito

| ID | Supuesto |
|----|----------|
| **S9** | **Velocidad de referencia `V = 1.0 m/s`** (constante `REFERENCE_VELOCITY_M_S` en `rules.py`). La guía indica que `V` la suministra el docente o se define de los parámetros disponibles; **no viene en el DataSet**, así que se adopta 1.0 m/s como valor nominal de diseño de colectores (supuesto **abierto, a confirmar con el docente**). |

El tiempo de tránsito de la tubería `i` se expresa **en pasos discretos**:

```
V_paso = V [m/s] · 60 [s/min] · Δt [min/paso]     # velocidad en metros por paso
t_i    = max(1, ⌈ L_i / V_paso ⌉ )                # pasos; mínimo 1 (S9b)
```

- **S9b — mínimo 1 paso:** toda tubería tarda al menos **1 paso**, aunque
  `L_i / V_paso < 1`; evita tránsitos de 0 pasos (agua "instantánea"), que la
  guía §5.4 prohíbe explícitamente.
- **S9c — redondeo hacia arriba (`ceil`):** el agua nunca llega *antes* de lo
  que indica la distancia; el residuo fraccionario se conserva en el paso
  siguiente.
- Ejemplo con `Δt = 1 min` (`V_paso = 60 m/paso`): tubería `P1` (L = 1149.04 m)
  ⇒ `t = ⌈19.15⌉ = 20` pasos; tubería `P54` (L = 51.63 m) ⇒ `t = ⌈0.86⌉ = 1` paso.

---

## 3. Generación de caudales (método racional)

| ID | Supuesto |
|----|----------|
| **S10** | El caudal de escorrentía de cada cuenca se calcula con el **método racional**: `Q = 0.00278 · C · I · A` (m³/s), con `C` adimensional, `I` en mm/h y `A` en hectáreas. Se evalúa **una vez por paso** usando la intensidad `I` del escenario activo (S5). |
| **S10b** | **Reparto del aporte de la cuenca:** la cuenca del DataSet **no tiene nodo asignado** (`BasinRecord.node = None`). Supuesto: el caudal total se **reparte entre los nodos fuente** `{1,6,9,17,18,19,20,27}` **proporcionalmente a la suma de `Qmax` de las tuberías que salen de cada fuente** (si alguna fuente no tiene salida o todas las capacidades son 0, reparto **uniforme** entre las fuentes). Es determinista (S6) y conserva masa. *Regla a confirmar con el docente.* |
| **S10c** | Si en un futuro la cuenca tuviera `node` asignado, **todo** su caudal se inyecta en ese nodo (rama prevista por `BasinRecord`). |

> Ejemplo: con `C = 0.75`, `A = 388 ha`: `Q = 0.002085 · I · 388` ⇒
> `I = 10 mm/h → 8.09 m³/s`; `I = 30 → 24.27`; `I = 60 → 48.54`; `I = 100 → 80.90 m³/s`.
> El total de capacidades de la red es ≈ 4.85 m³/s, por lo que **desde `I = 10`
> la red opera en sobrecarga generalizada**: es el comportamiento esperado y
> justifica la regla de retención de excesos (S12).

---

## 4. Reparto de caudal en pozos de convergencia

| ID | Supuesto |
|----|----------|
| **S11** | En un nodo con **una sola tubería de salida**, todo el caudal disponible se inyecta en ella. En un nodo con **varias tuberías de salida**, el caudal se reparte **proporcionalmente a la capacidad `Qmax` de cada salida** (las de mayor capacidad reciben más flujo). Si todas las salidas tuvieran `Qmax = 0`, el reparto es **uniforme**. *La guía §5.4 remite a "la regla definida para el ejercicio"; al no estar publicada, se adopta esta regla — a confirmar con el docente.* |
| **S11b** | El reparto **conserva masa**: `Σ flujos asignados = caudal disponible` (exacto hasta redondeo de coma flotante; las pruebas verifican `math.isclose`). |
| **S11c** | El caudal **en tránsito** dentro de una tubería no está disponible en su nodo de salida hasta que se cumple `t_i` pasos (S9); solo entonces se suma al nodo de destino. |

---

## 5. Utilización y sobrecargas

| ID | Supuesto |
|----|----------|
| **S12** | **Utilización** de la tubería `i` en el paso `k`: `O_i(k) = (Q_i(k) / Qmax_i) · 100`. `Q_i(k)` es el caudal que **ingresa** a la tubería en ese paso. `O` puede superar 100 % (estado "capacidad excedida", rojo oscuro). Con `Qmax_i > 0` (garantiza Persona C en validación), la función está siempre definida. |
| **S12b** | **La sobrecarga no hace desaparecer agua (conservación de masa):** si `Q_i(k) > Qmax_i`, solo `Qmax_i` se transporta; el **exceso `Q_i(k) − Qmax_i` se retiene en el pozo upstream** (almacenamiento/retención simplificado, guía §5.5) y se **reintenta enviar en los pasos siguientes**, sumándose al caudal nuevo de ese paso (FIFO por paso: primero lo retenido, luego lo nuevo). El exceso retenido es un estado observable (`excess` en el `Snapshot`). |
| **S12c** | Un pozo **sin tuberías de salida que no sea sumidero** (extremo muerto; solo aparecería como aviso de validación) **acumula todo** su exceso retenido sin salida. |
| **S12d** | El exceso retenido **no genera utilización** en la tubería (la tubería nunca transporta más de su `Qmax`); la utilización >100 % proviene del caudal **ofrecido** en el paso, no del retenido histórico. |

---

## 6. Limitaciones declaradas (guía §15)

- Resultados académicos ilustrativos: **no constituyen un diagnóstico
  hidráulico certificado** de la infraestructura real de Cartagena.
- No se resuelven las ecuaciones de Saint-Venant ni se modela presión,
  hidrogramas de entrada ni coeficientes de amortiguamiento.
- Los tiempos de tránsito, la velocidad de referencia y las reglas de reparto
  (S9, S10b, S11) son **supuestos del modelo**, sujetos a revisión del docente.

---

## 7. Decisiones abiertas (para confirmar con el docente)

1. **Velocidad de referencia `V`** (S9): ¿1.0 m/s es aceptable o hay un valor oficial?
2. **Regla de reparto en pozos** (S11): ¿proporcional a `Qmax` o uniforme?
3. **Reparto de la cuenca sin nodo** (S10b): ¿proporcional a capacidad de salida de cada fuente o uniforme entre fuentes?

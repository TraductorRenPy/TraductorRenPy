"""Tiempo restante estimado con el ritmo reciente (no con el promedio desde el inicio)."""

from typing import List, Optional, Tuple

Sample = Tuple[float, int]  # (segundos, lotes hechos)


def remaining_seconds(samples: List[Sample], done: int, total: int, window: int = 20) -> Optional[float]:
    """Segundos que faltan según los últimos `window` avances; None si aún no se puede calcular.

    Si el servicio se ralentiza (o se acelera), el estimado lo refleja enseguida.
    """
    if done <= 0 or done >= total or len(samples) < 2:
        return None
    recent = samples[-(window + 1):]
    (t0, d0), (t1, d1) = recent[0], recent[-1]
    if d1 <= d0 or t1 <= t0:
        (t0, d0), (t1, d1) = samples[0], samples[-1]  # sin avance reciente: promedio total
        if d1 <= d0 or t1 <= t0:
            return None
    return (total - done) / ((d1 - d0) / (t1 - t0))

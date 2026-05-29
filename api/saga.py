"""
Saga Orquestada — coordinador de transacciones distribuidas multi-motor.

En persistencia polimórfica no existe transacción global: cada motor gestiona
su propio ACID. Este módulo implementa el patrón Saga (variante orquestada)
para garantizar consistencia eventual: si un paso falla, se deshacen en orden
inverso todos los pasos previos mediante transacciones compensatorias.
"""
from typing import Callable, Any


class SagaOrchestrator:
    """
    Coordina una secuencia de pasos cross-motor con compensación automática.

    Uso típico:
        saga = SagaOrchestrator()
        try:
            result1 = paso_1(...)
            saga.register(compensar_paso_1, result1)

            result2 = paso_2(...)
            saga.register(compensar_paso_2, result2)

        except Exception:
            saga.compensate_all()
            raise
    """

    def __init__(self):
        self._compensations: list[tuple[Callable, tuple, dict]] = []

    def register(self, compensate_fn: Callable, *args: Any, **kwargs: Any) -> None:
        """Registra la compensación del paso que acaba de completarse con éxito."""
        self._compensations.append((compensate_fn, args, kwargs))

    def compensate_all(self) -> list[str]:
        """
        Ejecuta todas las compensaciones registradas en orden LIFO (inverso al de registro).
        No se interrumpe ante fallos individuales; retorna lista de mensajes de error.
        """
        errors = []
        for fn, args, kwargs in reversed(self._compensations):
            try:
                fn(*args, **kwargs)
            except Exception as exc:
                errors.append(f"{fn.__name__}: {exc}")
        return errors

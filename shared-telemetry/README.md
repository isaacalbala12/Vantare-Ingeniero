# shared-telemetry

Extractor de telemetría en tiempo real para Le Mans Ultimate (LMU) basado en memoria compartida.

Este paquete forma parte del ecosistema MOTEC y proporciona una API backend limpia, independiente y sin dependencias de interfaces gráficas para leer e interactuar con los datos de carrera de Le Mans Ultimate.

## Características

- **Sin dependencias de UI**: Remueve cualquier vínculo con Qt, PySide o componentes gráficos. Funciona puramente en consola o servidores de fondo.
- **Modelos Pydantic v2**: Toda la telemetría se expone a través de modelos Pydantic validados y listos para serialización JSON automática.
- **Sincronización por mID**: Asocia de forma dinámica los índices de telemetría de vehículos y los de scoring utilizando los IDs internos de LMU (`mID`).
- **Control de hilos daemon nativos**: Gestión de hilos mediante `threading.Thread` nativo a una frecuencia configurable.
- **Modo Offline**: Permite inyectar estados simulados (`RaceState`) para probar dashboards, motores de estrategia o componentes visuales sin necesidad de arrancar el juego.

## Requisitos

- Python 3.12 o superior.
- Dependencias principales: `pydantic>=2.0.0`
- Correr bajo Windows (ya que la memoria compartida de Le Mans Ultimate usa las APIs del sistema Windows; también incluye soporte básico en Linux si se lee desde `/dev/shm`).

## Instalación

Para instalar el paquete localmente en modo desarrollo:

```bash
pip install -e .
```

## Ejemplo de Uso

```python
import time
from shared_telemetry import TelemetryReader, RaceState

def log_telemetry(state: RaceState):
    print(f"[{state.timestamp}] Piloto: {state.player.driver_name} | "
          f"Marcha: {state.engine.gear} | RPM: {state.engine.rpm:.0f} | "
          f"Presión Rueda FL: {state.tyres.pressures[0]:.1f} kPa")

# Inicializa el lector a una frecuencia de 5Hz
reader = TelemetryReader(callback=log_telemetry, frequency=5.0)
reader.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    reader.stop()
```

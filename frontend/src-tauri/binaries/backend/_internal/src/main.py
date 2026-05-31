import asyncio
import logging
import uuid
import sys
import os

# PyInstaller --onedir: _MEIPASS = _internal/ dir (e.g. dist/backend/_internal)
# PyInstaller --onefile: _MEIPASS = temp extraction dir
# Dev: _MEIPASS not set, use __file__ (backend/src/main.py)
if hasattr(sys, '_MEIPASS'):
    # Bundled mode: sys._MEIPASS = _internal/ dir
    # src/ lives at _MEIPASS/src/, shared_* at _MEIPASS/
    # We use _MEIPASS directly as the root for local modules
    _backend_root = sys._MEIPASS
else:
    # Dev mode: __file__ = backend/src/main.py
    _script_dir = os.path.dirname(os.path.abspath(__file__))  # backend/src/
    _backend_root = os.path.dirname(_script_dir)  # backend/

# Ensure backend root is in path for `from src.config import ...`
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.services.lmu_api import poll_api
from src.services.strategy_service import StrategyService
from src.services.tts_service import TTSService
from src.services.edge_tts_service import EdgeTTSService
from src.services.elevenlabs_tts_service import ElevenLabsTTSService
from src.services.gemini_tts_service import GeminiTTSService
from src.persistence.history_store import HistoryStore
from shared_telemetry import TelemetryReader

from src.routers.health import router as health_router
from src.routers.websocket import router as ws_router, broadcast_sync
from src.routers.llm import router as llm_router
from src.routers.tts import router as tts_router
from src.routers.history import router as history_router
from src.routers.transcribe import router as transcribe_router

from src.intelligence.spotter import SpotterService
from src.intelligence.engine import IntelligenceEngine

# Configuración básica de logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("vantare.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan asíncrono para inicializar y apagar componentes ordenadamente."""
    logger.info("Initializing Ingeniero de IA Backend Services...")

    # 1. Instanciar e inicializar el lector de telemetría física de LMU
    # En Linux, no hay shared memory de LMU. Usamos TelemetryReader en modo offline como fallback.
    # La telemetría real vendrá del frontend Windows vía WebSocket → app.state.latest_client_frame.
    reader = TelemetryReader(offline=True, poll_rate=settings.TELEMETRY_POLL_RATE)
    reader.start()
    app.state.telemetry_reader = reader
    app.state.latest_client_frame = None  # Se poblará desde el frontend vía WebSocket
    app.state.latest_strategy_frame = None  # Se poblará desde el sidecar Windows vía /ws/sidecar
    app.state._last_telemetry_t = 0.0  # Para gap detection en websocket_endpoint
    logger.info(f"TelemetryReader started (offline_mode={reader.offline}). Waiting for frontend telemetry.")

    # 2. Iniciar el Poller REST de la API de LMU en background
    api_poller_task = asyncio.create_task(poll_api())
    app.state.api_poller_task = api_poller_task
    logger.info("LMU REST API poller task spawned")

    # 3. Instanciar e inicializar el orquestador del motor de estrategia (shared-strategy)
    strategy_service = StrategyService(reader)
    strategy_service.start()
    app.state.strategy_service = strategy_service
    logger.info("StrategyService loop spawned")

    # 3b. Esperar a que el primer ciclo de estrategia se complete antes de arrancar el engine
    await strategy_service.wait_until_ready()
    logger.info("StrategyService primer ciclo completado")
    logger.info("Esperando strategy_frame del sidecar Windows en /ws/sidecar. Usando StrategyService offline como fallback.")

    # 4. Instanciar e inicializar SpotterService (20Hz)
    spotter_service = SpotterService(broadcast_callback=broadcast_sync)
    app.state.spotter_service = spotter_service
    logger.info("SpotterService initialized and hooked to WS broadcaster")

    # 5. Inicializar HistoryStore (persistencia de consumo vuelta a vuelta)
    # Debe ir antes de IntelligenceEngine que lo recibe como dependencia
    history_store = HistoryStore()
    app.state.history_store = history_store
    logger.info("HistoryStore initialized (%d records loaded)", len(history_store.get_history()))

    # 5b. Inicializar EventStore (ChromaDB para RAG)
    import uuid
    from src.persistence.event_store import EventStore
    event_store = EventStore()
    event_store.initialize(race_id=str(uuid.uuid4()))
    app.state.event_store = event_store
    logger.info("EventStore initialized (ChromaDB RAG)")

    # 5c. Inicializar AudioQueueManager (sistema de colas CrewChief-style)
    from src.services.audio_queue import AudioQueueManager
    audio_queue = AudioQueueManager(broadcast_callback=broadcast_sync)
    app.state.audio_queue = audio_queue
    logger.info("AudioQueueManager initialized")

    # 5d. Inicializar IntelligenceEngine (0.5Hz / Triggers / Preempción)
    intelligence_engine = IntelligenceEngine(
        broadcast_callback=broadcast_sync,
        history_store=history_store,
        event_store=event_store,
        audio_queue=audio_queue,
        use_legacy_triggers=settings.use_legacy_triggers,
    )
    app.state.intelligence_engine = intelligence_engine
    logger.info("IntelligenceEngine initialized (legacy=%s)", settings.use_legacy_triggers)

    # Si NO es legacy, crear EventManager y arrancar cola
    if not settings.use_legacy_triggers:
        from src.intelligence.event_manager import EventManager
        event_manager = EventManager(audio_queue)
        intelligence_engine.event_manager = event_manager
        audio_queue_task = asyncio.create_task(audio_queue.start())
        app.state.audio_queue_task = audio_queue_task
        logger.info("EventManager + AudioQueue consumer task started")

    # Pasar audio_queue al SpotterService para el express path
    spotter_service.audio_queue = audio_queue

    if not settings.LLM_API_KEY:
        logger.error(
            "╔══════════════════════════════════════════════════╗\n"
            "║  LLM_API_KEY no configurada                    ║\n"
            "║  El LLM no responderá preguntas del piloto.     ║\n"
            "║  Crea backend/.env con:                         ║\n"
            "║    LLM_API_KEY=tu-api-key                       ║\n"
            "╚══════════════════════════════════════════════════╝"
        )

    # 7. Instanciar EdgeTTSService (cloud, sin dependencias locales)
    try:
        edge_tts_service = EdgeTTSService(voice=settings.EDGE_TTS_VOICE)
        app.state.edge_tts_service = edge_tts_service
        logger.info("EdgeTTSService initialized (voice=%s)", settings.EDGE_TTS_VOICE)
    except ImportError as e:
        logger.warning("EdgeTTSService no disponible: falta dependencia 'edge_tts'. %s", e)
        app.state.edge_tts_service = None
    except Exception as e:
        logger.warning("EdgeTTSService no disponible: %s", e)
        app.state.edge_tts_service = None

    # 8. Instanciar Piper TTSService (local, CPU)
    try:
        piper_tts_service = TTSService(settings.TTS_MODEL_PATH)
        app.state.piper_tts_service = piper_tts_service
        logger.info("Piper TTSService initialized")
    except FileNotFoundError as e:
        logger.warning(
            "Piper TTSService no disponible: modelo no encontrado en %s. %s",
            settings.TTS_MODEL_PATH, e
        )
        app.state.piper_tts_service = None
    except ImportError as e:
        logger.warning("Piper TTSService no disponible: falta dependencia. %s", e)
        app.state.piper_tts_service = None
    except Exception as e:
        logger.warning("Piper TTSService no disponible (TTS local desactivado): %s", e)
        app.state.piper_tts_service = None

    # 9. Instanciar ElevenLabs TTSService (cloud, requiere API key)
    if settings.ELEVENLABS_API_KEY:
        try:
            elevenlabs_tts_service = ElevenLabsTTSService(
                api_key=settings.ELEVENLABS_API_KEY,
                voice_id=settings.ELEVENLABS_VOICE_ID,
            )
            app.state.elevenlabs_tts_service = elevenlabs_tts_service
            logger.info("ElevenLabsTTSService initialized")
        except ImportError as e:
            logger.warning("ElevenLabsTTSService no disponible: falta dependencia 'elevenlabs'. %s", e)
            app.state.elevenlabs_tts_service = None
        except Exception as e:
            logger.warning("ElevenLabsTTSService no disponible: %s", e)
            app.state.elevenlabs_tts_service = None
    else:
        logger.info("ElevenLabsTTSService no configurado (ELEVENLABS_API_KEY vacía)")
        app.state.elevenlabs_tts_service = None

    # 10. Instanciar Gemini TTSService (cloud, Google AI Studio)
    if settings.GEMINI_API_KEY:
        try:
            import google.genai
            gemini_tts_service = GeminiTTSService(
                api_key=settings.GEMINI_API_KEY,
                voice_name=settings.GEMINI_TTS_VOICE,
            )
            app.state.gemini_tts_service = gemini_tts_service
            logger.info("GeminiTTSService initialized (voice=%s)", settings.GEMINI_TTS_VOICE)
        except ImportError as e:
            logger.warning("GeminiTTSService no disponible: falta dependencia 'google-genai'. %s", e)
            app.state.gemini_tts_service = None
        except Exception as e:
            logger.warning("GeminiTTSService no disponible: %s", e)
            app.state.gemini_tts_service = None
    else:
        logger.info("GeminiTTSService no configurado (GEMINI_API_KEY vacía)")
        app.state.gemini_tts_service = None

    logger.info(
        "TTS backend activo: %s. Edge=%s Piper=%s ElevenLabs=%s Gemini=%s",
        settings.TTS_BACKEND,
        "OK" if app.state.edge_tts_service else "NO",
        "OK" if app.state.piper_tts_service else "NO",
        "OK" if app.state.elevenlabs_tts_service else "NO",
        "OK" if app.state.gemini_tts_service else "NO",
    )

    yield

    # --- Shutdown ---
    logger.info("Shutting down Ingeniero de IA Backend Services...")

    # 1. Detener el bucle del orquestador de estrategia
    if strategy_service:
        await strategy_service.stop()

    # 2. Cancelar el poller REST de LMU
    if api_poller_task:
        api_poller_task.cancel()
        try:
            await api_poller_task
        except asyncio.CancelledError:
            pass

    # 3. Cancelar tareas LLM pendientes en curso en el IntelligenceEngine
    if hasattr(app.state, "intelligence_engine"):
        engine = app.state.intelligence_engine
        if engine._current_llm_task and not engine._current_llm_task.done():
            engine._current_llm_task.cancel()
            try:
                await engine._current_llm_task
            except asyncio.CancelledError:
                pass
            logger.info("Active LLM streaming task cancelled safely during shutdown.")

    # 4. Guardar historial de consumo a disco
    if hasattr(app.state, "history_store"):
        app.state.history_store.save()
        logger.info("HistoryStore saved to disk (%d records)", len(app.state.history_store.get_history()))

    # 4b. Limpiar EventStore (RAG)
    if hasattr(app.state, "event_store"):
        app.state.event_store.clear()
        logger.info("EventStore cleaned up (ChromaDB RAG)")

    # 5. Detener AudioQueueManager y su tarea consumer
    if hasattr(app.state, "audio_queue"):
        await app.state.audio_queue.stop()
    if hasattr(app.state, "audio_queue_task"):
        app.state.audio_queue_task.cancel()
        try:
            await app.state.audio_queue_task
        except asyncio.CancelledError:
            pass

    # 6. Detener el lector físico de shared memory
    if reader:
        reader.stop()
        
    logger.info("Backend services stopped successfully.")


# Inicializar la aplicación FastAPI
app = FastAPI(
    title="Vantare Ingeniero de IA Backend",
    description="Motor de estrategia y copiloto asíncrono para Le Mans Ultimate",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar middleware de CORS para Tauri y desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",
        "https://tauri.localhost",
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar rutas modulares
app.include_router(health_router)
app.include_router(ws_router)
app.include_router(llm_router)
app.include_router(tts_router)
app.include_router(history_router)
app.include_router(transcribe_router)


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}...")
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_config=None  # PyInstaller: evita crash por sys.stderr=None en --noconsole
    )

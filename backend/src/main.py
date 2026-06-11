import asyncio
import logging
import os
import sys
import uuid

# PyInstaller --onedir: _MEIPASS = _internal/ dir (e.g. dist/backend/_internal)
# PyInstaller --onefile: _MEIPASS = temp extraction dir
# Dev: _MEIPASS not set, use __file__ (backend/src/main.py)
if hasattr(sys, "_MEIPASS"):
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

from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared_telemetry import TelemetryReader
from src.app_runtime.runtime import native_telemetry_enabled
from src.config import settings
from src.intelligence.engine import IntelligenceEngine
from src.intelligence.spotter import SpotterService
from src.persistence.history_store import HistoryStore
from src.persistence.profile_store import ProfileStore
from src.persistence.trace_store import TraceStore
from src.routers.health import router as health_router
from src.routers.history import router as history_router
from src.routers.llm import router as llm_router
from src.routers.profiles import router as profiles_router
from src.routers.traces import router as traces_router
from src.routers.transcribe import router as transcribe_router
from src.routers.tts import router as tts_router
from src.routers.version import router as version_router
from src.routers.websocket import broadcast_sync
from src.routers.websocket import router as ws_router
from src.services.edge_tts_service import EdgeTTSService
from src.services.elevenlabs_tts_service import ElevenLabsTTSService
from src.services.gemini_tts_service import GeminiTTSService
from src.services.lmu_api import poll_api
from src.services.strategy_service import StrategyService
from src.services.tts_service import TTSService
from src.version import APP_VERSION
from src.voice.bridge import VoiceBridge
from src.voice.voice_queue import VoiceQueue

# Configuración básica de logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vantare.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan asíncrono para inicializar y apagar componentes ordenadamente."""
    logger.info("Initializing Ingeniero de IA Backend Services...")

    # 1. Instanciar el lector de telemetría de LMU (shared memory nativa en Windows).
    use_native = native_telemetry_enabled()
    reader = TelemetryReader(offline=not use_native, poll_rate=settings.TELEMETRY_POLL_RATE)
    reader.start()
    app.state.telemetry_reader = reader
    app.state.latest_client_frame = None
    app.state._last_telemetry_t = 0.0
    if use_native:
        logger.info("TelemetryReader started (native shared memory, offline_mode=False)")
    else:
        logger.info(f"TelemetryReader started (offline_mode={reader.offline}). Esperando telemetría del frontend.")

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
    if use_native:
        logger.info("Telemetría nativa Windows activa (shared memory LMU).")
    else:
        logger.info("Telemetría vía frontend WebSocket o StrategyService offline.")

    # 3c. Instanciar VoiceQueue + VoiceBridge (antes de Spotter/Engine)
    voice_queue = VoiceQueue()
    app.state.voice_queue = voice_queue
    voice_bridge = VoiceBridge(
        ws_broadcast=broadcast_sync,
        voice_queue=voice_queue,
        enabled=settings.VOICE_BACKEND_PLAYBACK,
    )
    app.state.voice_bridge = voice_bridge
    logger.info("VoiceBridge initialized (backend playback=%s)", settings.VOICE_BACKEND_PLAYBACK)

    # 4. Instanciar e inicializar SpotterService (20Hz)
    spotter_service = SpotterService(broadcast_callback=voice_bridge.send)
    app.state.spotter_service = spotter_service
    logger.info("SpotterService initialized and hooked to voice bridge + WS broadcaster")

    from src.race.telemetry_hub import TelemetryHub

    telemetry_hub = TelemetryHub()
    app.state.telemetry_hub = telemetry_hub

    # 5. Inicializar HistoryStore (persistencia de consumo vuelta a vuelta)
    # Debe ir antes de IntelligenceEngine que lo recibe como dependencia
    history_store = HistoryStore()
    app.state.history_store = history_store
    logger.info("HistoryStore initialized (%d records loaded)", len(history_store.get_history()))

    profile_store = ProfileStore()
    app.state.profile_store = profile_store
    logger.info("ProfileStore initialized (%d profiles)", len(profile_store.list_profiles()))

    trace_store = TraceStore()
    app.state.trace_store = trace_store
    app.state.trace_playback_task = None
    app.state.trace_playback_active = False
    logger.info("TraceStore initialized")

    # 5b. Inicializar EventStore (ChromaDB para RAG) — opcional, desactivado en beta slim
    event_store = None
    if settings.ENABLE_CHROMA_RAG and not settings.BETA_SLIM:
        try:
            from src.persistence.event_store import EventStore

            event_store = EventStore()
            event_store.initialize(race_id=str(uuid.uuid4()))
            logger.info("EventStore initialized (ChromaDB RAG)")
        except Exception as exc:
            logger.warning(
                "EventStore (ChromaDB RAG) no disponible — el backend arranca sin RAG: %s",
                exc,
            )
    else:
        logger.info("EventStore skipped (BETA_SLIM or RAG disabled)")
    app.state.event_store = event_store

    # 6. Instanciar e inicializar IntelligenceEngine (0.5Hz / Triggers / Preempción)
    intelligence_engine = IntelligenceEngine(
        broadcast_callback=voice_bridge.send,
        history_store=history_store,
        event_store=event_store,
        strategy_service=strategy_service,
    )
    intelligence_engine.sweary_messages = settings.USE_SWEARY_MESSAGES
    intelligence_engine.set_spotter_service(spotter_service)
    from src.intelligence.crewchief_events.game_state import CrewChiefGameStateLoop
    from src.intelligence.crewchief_events.suite_factory import build_crewchief_suite

    intelligence_engine.crewchief_suite = build_crewchief_suite(intelligence_engine)
    app.state.crewchief_loop = CrewChiefGameStateLoop(engine=intelligence_engine)
    app.state.intelligence_engine = intelligence_engine
    app.state.sweary_messages = settings.USE_SWEARY_MESSAGES

    if settings.BETA_SLIM or not settings.ENABLE_COMMENTARY_BATCH:
        intelligence_engine.verbosity.set_enable_commentary_batch(False)

    logger.info("IntelligenceEngine initialized and hooked to VoiceBridge")

    from src.race.tick_loop import RaceTickDeps, race_tick_loop

    race_deps = RaceTickDeps(
        strategy_service=strategy_service,
        spotter_service=spotter_service,
        crewchief_loop=app.state.crewchief_loop,
        intelligence_engine=intelligence_engine,
        telemetry_hub=telemetry_hub,
    )
    race_task = asyncio.create_task(race_tick_loop(race_deps))
    app.state.race_task = race_task
    logger.info("race_tick_loop spawned (20Hz global)")

    if not settings.LLM_API_KEY:
        logger.error(
            "╔══════════════════════════════════════════════════╗\n"
            "║  LLM_API_KEY no configurada                    ║\n"
            "║  EL LLM no responderá preguntas del piloto.     ║\n"
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
        logger.warning("Piper TTSService no disponible: modelo no encontrado en %s. %s", settings.TTS_MODEL_PATH, e)
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
            import importlib.util

            if importlib.util.find_spec("google.genai") is None:
                raise ImportError("google-genai no instalado")

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

    from src.voice.ducking import DuckingController
    from src.voice.moderator import PlaybackModerator
    from src.voice.playback_notify import VoicePlaybackNotifier
    from src.voice.service import voice_loop

    ducking = DuckingController() if settings.VOICE_BACKEND_PLAYBACK else None
    playback_notify = (
        VoicePlaybackNotifier(broadcast_sync) if settings.VOICE_BACKEND_PLAYBACK else None
    )
    app.state.ducking = ducking

    from src.voice.tts_routing import TtsRouting

    app.state.tts_routing = TtsRouting()
    intelligence_engine.set_tts_routing(app.state.tts_routing)

    spotter_cache = None
    tts_manager = None
    voice_player = None

    edge = getattr(app.state, "edge_tts_service", None)
    gemini = getattr(app.state, "gemini_tts_service", None)
    if settings.VOICE_BACKEND_PLAYBACK and edge is not None:
        from src.voice.player_pygame import PygameAudioPlayer
        from src.voice.spotter_cache import SpotterPhraseCache
        from src.voice.tts_manager import TTSManager

        spotter_cache = SpotterPhraseCache(edge)
        try:
            await spotter_cache.warm()
            logger.info("SpotterPhraseCache warmed (%d phrases)", spotter_cache.size)
        except Exception as exc:
            logger.warning("Spotter cache warm failed — live TTS only: %s", exc)
        tts_manager = TTSManager(edge=edge, gemini=gemini, spotter_cache=spotter_cache, routing=app.state.tts_routing)
        voice_player = PygameAudioPlayer()
        logger.info("Voice player: PygameAudioPlayer (real playback)")
    else:
        from src.voice.player_pygame import MockAudioPlayer

        voice_player = MockAudioPlayer()
        logger.warning(
            "Voice playback: MockAudioPlayer (edge=%s, flag=%s)",
            bool(edge),
            settings.VOICE_BACKEND_PLAYBACK,
        )

    app.state.spotter_cache = spotter_cache
    app.state.tts_manager = tts_manager
    app.state.voice_player = voice_player

    voice_moderator = PlaybackModerator()
    app.state.voice_moderator = voice_moderator
    voice_task = asyncio.create_task(
        voice_loop(
            voice_queue,
            voice_player,
            voice_moderator,
            tts=tts_manager,
            ducking=ducking,
            playback_notify=playback_notify,
        )
    )
    app.state.voice_task = voice_task
    logger.info("voice_loop spawned (player=%s)", type(voice_player).__name__)

    logger.info(
        "TTS backend activo: %s. Edge=%s Piper=%s ElevenLabs=%s Gemini=%s",
        settings.TTS_BACKEND,
        "OK" if app.state.edge_tts_service else "NO",
        "OK" if app.state.piper_tts_service else "NO",
        "OK" if app.state.elevenlabs_tts_service else "NO",
        "OK" if app.state.gemini_tts_service else "NO",
    )

    from src.services.mqtt_service import get_mqtt_service

    app.state.mqtt_service = get_mqtt_service()
    if settings.MQTT_ENABLED and settings.ENABLE_MQTT and not settings.BETA_SLIM:
        logger.info("MQTT habilitado → %s:%s/%s", settings.MQTT_BROKER, settings.MQTT_PORT, settings.MQTT_TOPIC)

    if settings.WHISPER_PRELOAD.lower() == "startup" and not settings.BETA_SLIM:
        from src.services.asr_service import preload_whisper

        async def _preload_asr() -> None:
            ok = await asyncio.to_thread(preload_whisper)
            if ok:
                logger.info("Whisper ASR precargado para PTT")
            else:
                logger.warning("Whisper ASR no disponible — PTT dependerá de SpeechRecognition del navegador")

        asyncio.create_task(_preload_asr())

    yield

    # --- Shutdown ---
    logger.info("Shutting down Ingeniero de IA Backend Services...")

    # 1. Cancel voice loop first (don't enqueue more during shutdown)
    voice_task = getattr(app.state, "voice_task", None)
    if voice_task:
        voice_task.cancel()
        with suppress(asyncio.CancelledError):
            await voice_task

    # 2. Detener race tick loop
    race_task = getattr(app.state, "race_task", None)
    if race_task:
        race_task.cancel()
        with suppress(asyncio.CancelledError):
            await race_task

    if strategy_service:
        await strategy_service.stop()

    # 2. Cancelar el poller REST de LMU
    if api_poller_task:
        api_poller_task.cancel()
        with suppress(asyncio.CancelledError):
            await api_poller_task

    # 3. Cancelar tareas LLM pendientes en curso en el IntelligenceEngine
    if hasattr(app.state, "intelligence_engine"):
        engine = app.state.intelligence_engine
        if engine._current_llm_task and not engine._current_llm_task.done():
            engine._current_llm_task.cancel()
            with suppress(asyncio.CancelledError):
                await engine._current_llm_task
            logger.info("Active LLM streaming task cancelled safely during shutdown.")

    # 4. Guardar historial de consumo a disco
    if hasattr(app.state, "history_store"):
        app.state.history_store.save()
        logger.info("HistoryStore saved to disk (%d records)", len(app.state.history_store.get_history()))

    # 4b. Limpiar EventStore (RAG)
    if getattr(app.state, "event_store", None) is not None:
        app.state.event_store.clear()
        logger.info("EventStore cleaned up (ChromaDB RAG)")

    if hasattr(app.state, "mqtt_service"):
        await app.state.mqtt_service.shutdown_worker()
        app.state.mqtt_service.shutdown()

    # 5. Detener el lector físico de shared memory
    if reader:
        reader.stop()

    logger.info("Backend services stopped successfully.")


# Inicializar la aplicación FastAPI
app = FastAPI(
    title="Vantare Ingeniero de IA Backend",
    description="Motor de estrategia y copiloto asíncrono para Le Mans Ultimate",
    version=APP_VERSION,
    lifespan=lifespan,
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
app.include_router(profiles_router)
app.include_router(version_router)
app.include_router(traces_router)


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}...")
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_config=None,  # PyInstaller: evita crash por sys.stderr=None en --noconsole
    )

"""EventStore: gestor de ChromaDB para eventos de carrera.

Indexa cada evento detectado por el StateChangeDetector (sidecar) con un embedding
de la telemetría de ESE momento. La consulta semántica devuelve los N eventos más
similares a la telemetría actual.

Al cerrar sesión, la colección se borra (no hay persistencia entre sesiones).
La feature v1.1 (recopilación centralizada) exportará los datos antes de borrar.
"""

import logging
import time
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

from src.intelligence.formatter import format_event_text

logger = logging.getLogger("vantare.event_store")




class _E5EmbeddingFunction(EmbeddingFunction):
    """Wrapper para multilingual-e5-large compatible con ChromaDB.

    El modelo se carga lazy (solo cuando se indexa el primer evento) para
    no bloquear el arranque del backend.
    """

    def __init__(self) -> None:
        self._model = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        logger.info("Cargando modelo de embeddings multilingual-e5-large...")
        start = time.monotonic()
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(
            "intfloat/multilingual-e5-large",
            device="cpu",
            # Deshabilitar warnings de torch
            config_kwargs={"use_cache": False},
        )
        elapsed = time.monotonic() - start
        logger.info("Modelo de embeddings cargado en %.1fs", elapsed)

    def __call__(self, input: Documents) -> Embeddings:
        """Genera embeddings para una lista de textos."""
        self._ensure_model()
        # E5 requiere prefijo "query:" o "passage:" según el uso
        prefixed = [f"passage: {t}" for t in input]
        vectors = self._model.encode(prefixed, normalize_embeddings=True)
        return vectors.tolist()


class EventStore:
    """Almacén de eventos de carrera con búsqueda semántica vía ChromaDB.

    Cada evento detectado recibe un embedding de la telemetría del momento.
    Las consultas devuelven los eventos históricos con telemetría más similar.

    La colección está namespaced por race_id para poder aislar carreras distintas
    y exportarlas individualmente (v1.1).
    """

    def __init__(
        self,
        persist_path: str = "./.chroma_db",
        collection_name: str = "race_events",
    ) -> None:
        # Resolve and normalize the path to prevent path traversal
        self._persist_path = str(Path(persist_path).resolve().expanduser())
        self._collection_name = collection_name
        self._client: Optional[chromadb.Client] = None
        self._collection: Optional[Any] = None
        self._current_race_id: Optional[str] = None
        self._embedding_fn = _E5EmbeddingFunction()

    # --- Lifecycle ---

    def initialize(self, race_id: str) -> None:
        """Inicializa ChromaDB y crea/obtiene la colección para esta carrera.

        Llámase desde el lifespan de FastAPI cuando arranca una sesión.
        """
        self._current_race_id = race_id

        # Cliente persistente — recrear client si estaba cerrado tras clear()
        self._client = chromadb.PersistentClient(path=self._persist_path)

        # Eliminar colección anterior si existe (limpieza)
        try:
            self._client.delete_collection(self._collection_name)
        except (ValueError, chromadb.errors.NotFoundError):
            pass  # No existía

        self._collection = self._client.create_collection(
            name=self._collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "EventStore inicializado: race_id=%s, persist_path=%s",
            race_id, self._persist_path,
        )

    def clear(self) -> None:
        """Borra la colección y los archivos de persistencia.

        Llámase desde el shutdown de FastAPI.
        """
        try:
            if self._client is not None:
                try:
                    self._client.delete_collection(self._collection_name)
                    logger.info("Colección ChromaDB eliminada")
                except (ValueError, chromadb.errors.NotFoundError, chromadb.errors.InternalError) as exc:
                    logger.debug("ChromaDB collection already absent during clear: %s", exc)
        except Exception as e:
            logger.warning("Error al limpiar ChromaDB: %s", e)
        self._collection = None
        self._client = None
        self._current_race_id = None

    # --- Indexación ---

    def store_event(self, frame: dict, event_type: str, lap: int) -> None:
        """Indexa un evento en ChromaDB.

        Args:
            frame: TelemetryFrame completo como dict (del sidecar).
            event_type: Tipo de evento (ej. "lap_completed", "safety_car").
            lap: Número de vuelta actual.
        """
        if self._collection is None:
            logger.warning("EventStore no inicializado — ignorando evento %s", event_type)
            return

        now = time.time()
        text = format_event_text(frame, event_type, lap)
        event_id = f"{event_type}_{lap}_{int(now * 1000)}"

        self._collection.add(
            documents=[text],
            ids=[event_id],
            metadatas=[{
                "type": event_type,
                "lap": lap,
                "timestamp": now,
                "race_id": self._current_race_id or "",
                "session_type": frame.get("session_type", "race"),
            }],
        )

    def store_events_batch(self, frames: list[tuple[dict, str, int]]) -> None:
        """Indexa múltiples eventos en batch (más eficiente).

        Args:
            frames: Lista de tuplas (frame_dict, event_type, lap).
        """
        if self._collection is None or not frames:
            return

        documents: list[str] = []
        ids: list[str] = []
        metadatas: list[dict] = []
        now = time.time()
        race_id = self._current_race_id or ""

        for frame, event_type, lap in frames:
            text = format_event_text(frame, event_type, lap)
            documents.append(text)
            ids.append(f"{event_type}_{lap}_{int(now * 1000 + len(ids))}")
            metadatas.append({
                "type": event_type,
                "lap": lap,
                "timestamp": now,
                "race_id": race_id,
                "session_type": frame.get("session_type", "race"),
            })

        self._collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadatas,
        )

    # --- Consulta ---

    def query(self, frame: dict, top_k: int = 5) -> list[dict]:
        """Busca los eventos históricos con telemetría más similar a la actual.

        Args:
            frame: TelemetryFrame actual como dict.
            top_k: Número de resultados a devolver.

        Returns:
            Lista de dicts con keys: text, type, lap, timestamp.
        """
        if self._collection is None:
            return []

        # El texto de consulta usa el mismo formato que los documentos
        query_text = format_event_text(frame, "query", frame.get("lap_number", 1))

        results = self._collection.query(
            query_texts=[query_text],
            n_results=min(top_k, 50),  # límite de ChromaDB
        )

        if not results or not results.get("ids"):
            return []

        output: list[dict] = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            output.append({
                "text": results["documents"][0][i] if results["documents"] else "",
                "type": meta.get("type", "unknown"),
                "lap": meta.get("lap", 0),
                "timestamp": meta.get("timestamp", 0.0),
                "distance": results["distances"][0][i] if results["distances"] else 0.0,
            })

        return output

    # --- Getters ---

    def get_collection_count(self) -> int:
        """Número de eventos en la colección actual."""
        if self._collection is None:
            return 0
        return self._collection.count()

    def get_current_race_id(self) -> Optional[str]:
        return self._current_race_id

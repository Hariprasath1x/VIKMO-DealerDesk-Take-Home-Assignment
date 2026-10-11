import threading

_model_lock = threading.Lock()
_embedding_model = None

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def get_embedding_model():
    """
    Lazy-loads and caches the sentence-transformers model.
    Thread-safe singleton.
    """
    global _embedding_model
    if _embedding_model is None:
        with _model_lock:
            if _embedding_model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    _embedding_model = SentenceTransformer(MODEL_NAME)
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to load embedding model '{MODEL_NAME}'. "
                        f"Ensure dependencies are installed and model files are accessible. Error: {e}"
                    )
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Encodes a list of strings into normalized dense vector embeddings.
    """
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """
    Encodes a single query string into a normalized dense vector embedding.
    """
    embeddings = embed_texts([query])
    return embeddings[0] if embeddings else []

import pickle
import threading

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..config import INDEX_PATH
from ..db import db_session
from .text_matching import tokenize

_lock = threading.Lock()
_cache = None


def rebuild_index():
    """Recompute the TF-IDF index from the chunks table and persist it to disk."""
    with db_session() as conn:
        rows = conn.execute("SELECT id, source_label, text FROM chunks").fetchall()

    chunks = [{"id": r["id"], "source": r["source_label"], "text": r["text"]} for r in rows]
    if not chunks:
        index = {"vectorizer": None, "matrix": None, "chunks": []}
    else:
        vectorizer = TfidfVectorizer(tokenizer=tokenize, token_pattern=None, stop_words="english", max_features=20000)
        matrix = vectorizer.fit_transform([c["text"] for c in chunks])
        index = {"vectorizer": vectorizer, "matrix": matrix, "chunks": chunks}

    with _lock:
        global _cache
        _cache = index
        with open(INDEX_PATH, "wb") as f:
            pickle.dump(index, f)
    return index


def load_index():
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
    try:
        with open(INDEX_PATH, "rb") as f:
            index = pickle.load(f)
    except FileNotFoundError:
        index = rebuild_index()
    with _lock:
        _cache = index
    return index


def retrieve(query: str, top_k: int = 5) -> list:
    index = load_index()
    if not index["chunks"] or index["vectorizer"] is None:
        return []

    q_vec = index["vectorizer"].transform([query])
    sims = cosine_similarity(q_vec, index["matrix"]).flatten()
    ranked = sims.argsort()[::-1][:top_k]

    results = []
    for i in ranked:
        if sims[i] <= 0:
            continue
        chunk = index["chunks"][i]
        results.append({"source": chunk["source"], "text": chunk["text"], "score": float(sims[i])})
    return results

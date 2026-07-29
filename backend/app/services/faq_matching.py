import pickle
import threading

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..config import DATA_DIR
from ..db import db_session
from .text_matching import tokenize

FAQ_INDEX_PATH = DATA_DIR / "faq_index.pkl"

# TF-IDF cosine similarity on short FAQ questions runs much hotter than on full page
# chunks, so this needs a higher bar than general retrieval — tuned empirically.
MATCH_THRESHOLD = 0.35

_lock = threading.Lock()
_cache = None


def rebuild_index():
    """Recompute the FAQ-question TF-IDF index. Call whenever faqs are added/edited."""
    with db_session() as conn:
        rows = conn.execute("SELECT id, question, answer, category, priority FROM faqs").fetchall()

    faqs = [dict(r) for r in rows]
    if not faqs:
        index = {"vectorizer": None, "matrix": None, "faqs": []}
    else:
        vectorizer = TfidfVectorizer(tokenizer=tokenize, token_pattern=None, stop_words="english", max_features=5000)
        matrix = vectorizer.fit_transform([f["question"] for f in faqs])
        index = {"vectorizer": vectorizer, "matrix": matrix, "faqs": faqs}

    with _lock:
        global _cache
        _cache = index
        with open(FAQ_INDEX_PATH, "wb") as fh:
            pickle.dump(index, fh)
    return index


def load_index():
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
    try:
        with open(FAQ_INDEX_PATH, "rb") as fh:
            index = pickle.load(fh)
    except FileNotFoundError:
        index = rebuild_index()
    with _lock:
        _cache = index
    return index


def match(query: str):
    """Return the best-matching approved FAQ for `query`, or None if nothing clears
    MATCH_THRESHOLD. This is the fast path — a hit here skips general KB retrieval."""
    index = load_index()
    if not index["faqs"] or index["vectorizer"] is None:
        return None

    q_vec = index["vectorizer"].transform([query])
    sims = cosine_similarity(q_vec, index["matrix"]).flatten()
    best_i = sims.argmax()
    if sims[best_i] < MATCH_THRESHOLD:
        return None

    faq = index["faqs"][best_i]
    return {**faq, "score": float(sims[best_i])}

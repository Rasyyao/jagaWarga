import hashlib
import json
import numpy as np
import redis
from sentence_transformers import SentenceTransformer
from shared.config import get_settings

settings = get_settings()

_redis_client: redis.Redis | None = None

def get_redis() -> redis.Redis:
    global _redis_client 
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=False)
    return _redis_client

_embed_model : SentenceTransformer | None =  None

def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _embed_model

HASH_PREFIX  = "dedup:hash:"   
EMBED_PREFIX = "dedup:embed:"  
INDEX_KEY    = "dedup:index"    
TTL          = settings.DEDUP_CACHE_TTL  

def compute_hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode('utf-8')).hexdigest()

def compute_embedding(text : str) -> np.ndarray:
    model = get_embed_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.astype(np.float32)

def cosine_similarity(a : np.ndarray, b : np.ndarray) -> float:
    return float(np.dot(a, b) / np.linalg.norm(a) * (np.linalg.norm(b) + 1e-10))

def check_duplicate(text: str, report_id : str) -> dict:
    r = get_redis()
    cache_key = compute_hash(text)
    
    existing_id = r.get(f"{HASH_PREFIX}{cache_key}")
    if existing_id:
        return {
            "is_duplicate": True,
            "cache_key": cache_key,
            "similar_report_id": existing_id.decode("utf-8"),
            "similarity_score": 1.0,
            "match_type": "exact",
        }
        
    query_embed = compute_embedding(text)
    stored_ids = r.lrange(INDEX_KEY, 0, -1)
    
    best_score = 0.0
    best_id = None
    
    for rid_bytes in stored_ids:
        rid = rid_bytes.decode("utf-8")
        embed_bytes = r.get(f"{EMBED_PREFIX}{rid}")
        if not embed_bytes:
            continue
        
        store_embed = np.frombuffer(embed_bytes, dtype=np.float32)
        score = cosine_similarity(query_embed, store_embed)
        
        if score > best_score:
            best_score = score
            best_id = rid
            
    if best_score >= settings.DEDUP_SIMILARITY_THRESHOLD and best_id:
        return {
            "is_duplicate": True,
            "cache_key": cache_key,
            "similar_report_id": best_id,
            "similarity_score": round(best_score, 4),
            "match_type": "semantic",
        }
            
    pipe = r.pipeline()
    pipe.setex(f"{HASH_PREFIX}{cache_key}", TTL, report_id.encode("utf-8"))
    pipe.set(f"{EMBED_PREFIX}{report_id}", query_embed.tobytes())
    pipe.expire(f"{EMBED_PREFIX}{report_id}", TTL)
    pipe.rpush(INDEX_KEY, report_id)
    pipe.execute()

    return {
        "is_duplicate": False,
        "cache_key": cache_key,
        "similar_report_id": None,
        "similarity_score": None,
        "match_type": None,
    }
        
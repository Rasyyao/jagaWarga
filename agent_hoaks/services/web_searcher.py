from typing import List, Dict
from shared.searcher import web_search

FACT_CHECK_WEBSITES = [
    "turnbackhoax.id",
    "cekfakta.com",
    "cekfakta.tempo.co",
    "kominfo.go.id",
    "liputan6.com",
    "medcom.id",
    "kompas.com",
    "detik.com",
]


def search_hoax(claims: List[str]) -> List[Dict[str, str]]:
    query = claims[0] if claims else ""
    if not query:
        return []
    return web_search(query, FACT_CHECK_WEBSITES)

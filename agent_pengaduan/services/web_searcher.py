from typing import List, Dict
from shared.searcher import web_search

GOV_WEBSITES = [
    "pln.co.id",
    "jakartaone.id",
    "jakarta.go.id",
    "lapor.go.id",
    "kompas.com",
    "detik.com",
    "tribunnews.com",
    "antaranews.com",
]


def search_complaint(claims: List[str]) -> List[Dict[str, str]]:
    query = claims[0] if claims else ""
    if not query:
        return []
    return web_search(query, GOV_WEBSITES)

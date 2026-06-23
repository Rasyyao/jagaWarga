import os
from typing import List, Dict
from serpapi import GoogleSearch


def web_search(query: str, whitelist: List[str], num_results: int = 10) -> List[Dict[str, str]]:
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise ValueError("SERPAPI_KEY not found in environment variables")

    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "num": num_results,
        "gl": "id",
        "hl": "id",
    }

    organic = GoogleSearch(params).get_dict().get("organic_results", [])

    return [
        {
            "url": item.get("link", ""),
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "date": item.get("date", ""),
        }
        for item in organic
        if any(domain in item.get("link", "").lower() for domain in whitelist)
    ][:5]

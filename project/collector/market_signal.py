# -*- coding: utf-8 -*-
"""Discover early marine sales signals through the Naver News Search API."""

from __future__ import annotations

import asyncio
import hashlib
import html
import os
import re
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx

from .base import BaseCollector, clean_text, env_int


DEFAULT_SIGNAL_QUERIES = [
    "관공선 건조", "경비함 경비정 건조", "국가어업지도선 건조", "소방선 소방정 건조",
    "연안여객선 신조 대체선", "차도선 도항선 건조", "하이브리드 선박 건조", "전기추진 선박 건조",
    "선박 인버터 컨버터", "선박 VFD 추진모터", "선박 축발전기 DC Grid", "친환경선박 기본설계",
    "선박 장비선정위원회", "해상풍력 CTV SOV", "선박 개조 전기추진", "조선소 전기추진 시스템",
]


def _plain(value: Any) -> str:
    text = html.unescape(str(value or ""))
    return clean_text(re.sub(r"<[^>]+>", " ", text))


def _date(value: Any) -> str | None:
    try:
        return parsedate_to_datetime(str(value or "")).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        match = re.search(r"20\d{2}-\d{2}-\d{2}", str(value or ""))
        return match.group(0) if match else None


class NaverMarketSignalCollector(BaseCollector):
    name = "NaverMarketSignals"
    source_type = "NEWS"
    operations: Dict[str, Dict[str, str]] = {}

    def __init__(self) -> None:
        super().__init__()
        self.client_id = os.getenv("NAVER_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("NAVER_CLIENT_SECRET", "").strip()

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def queries(self) -> List[str]:
        configured = [clean_text(value) for value in re.split(r"[\n,;]+", os.getenv("SALES_SIGNAL_QUERIES", "")) if clean_text(value)]
        queries = configured or DEFAULT_SIGNAL_QUERIES
        return list(dict.fromkeys(queries))[: env_int("SALES_SIGNAL_MAX_QUERIES", 20, 1, 60)]

    async def _search(self, query: str) -> List[Dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET이 설정되지 않았습니다.")
        response = await self.http_client().get(
            "https://openapi.naver.com/v1/search/news.json",
            params={"query": query, "display": env_int("SALES_SIGNAL_RESULTS_PER_QUERY", 30, 1, 100), "start": 1, "sort": "date"},
            headers={"X-Naver-Client-Id": self.client_id, "X-Naver-Client-Secret": self.client_secret},
        )
        response.raise_for_status()
        return response.json().get("items") or []

    async def collect(self, seed_projects: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
        semaphore = asyncio.Semaphore(env_int("SALES_SIGNAL_CONCURRENCY", 3, 1, 6))

        async def one(query: str) -> tuple[str, List[Dict[str, Any]]]:
            async with semaphore:
                return query, await self._search(query)

        responses = await asyncio.gather(*(one(query) for query in self.queries()), return_exceptions=True)
        results: List[Dict[str, Any]] = []
        seen: set[str] = set()
        errors: List[Exception] = []
        for response in responses:
            if isinstance(response, Exception):
                errors.append(response)
                continue
            query, rows = response
            for row in rows:
                title = _plain(row.get("title"))
                summary = _plain(row.get("description"))
                url = clean_text(row.get("originallink") or row.get("link"))
                key = hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                publisher = urlparse(url).netloc.removeprefix("www.") if url else "네이버 뉴스"
                project = self.clean_item(
                    "naverMarketSignal",
                    {
                        "title": title,
                        "publisher": publisher,
                        "description": summary,
                        "pubDate": row.get("pubDate"),
                        "originallink": url,
                        "link": row.get("link"),
                        "discoveryQuery": query,
                    },
                    title=title,
                    publisher=publisher,
                    source_url=url or "https://search.naver.com/search.naver",
                    registered_at=_date(row.get("pubDate")),
                )
                if project:
                    project["rawPayload"]["_salesIntelligence"].setdefault("riskFlags", []).append("뉴스 발견 단계: 공식 발주·예산 근거 추가 확인 필요")
                    results.append(project)
                if len(results) >= self.max_items:
                    return results
        if not results and errors and len(errors) == len(responses):
            raise RuntimeError(f"네이버 영업신호 검색 실패: {errors[-1]}")
        return results


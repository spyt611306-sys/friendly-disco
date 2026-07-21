# -*- coding: utf-8 -*-
"""나라장터 이전 단계의 선박·드라이브 영업 신호를 뉴스 검색으로 발굴한다."""

from __future__ import annotations

import asyncio
import html
import os
import re
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from .base import BaseCollector, clean_text


DEFAULT_SIGNAL_QUERIES = [
    "하이브리드 선박 건조 전기추진",
    "관공선 대체건조 기본설계",
    "해양경찰 3000톤 경비함 건조",
    "어업관리단 어업지도선 건조",
    "소방청 소방정 건조",
    "여객선 차도선 친환경 건조",
    "CTV 해상풍력 지원선 건조",
    "선박 전기추진 인버터 VFD",
    "선박 추진모터 컨버터",
    "선박 축발전기 DC grid",
    "항만 육상전원 shore power 인버터",
    "해상풍력 해상변전소 컨버터",
    "선박 하이브리드 retrofit 개조",
    "관공선 장비선정위원회",
    "함정 기본설계 추진체계",
    "친환경선박 예산 발주계획",
    "조선소 전기추진 시스템 공급",
]


def _clean_html(value: Any) -> str:
    text = html.unescape(str(value or ""))
    return clean_text(re.sub(r"<[^>]+>", " ", text))


def _safe_url(value: Any) -> Optional[str]:
    url = str(value or "").strip()
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _date_only(value: Any) -> Optional[str]:
    text = _clean_html(value)
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        match = re.search(r"(20\d{2})[-/.]?(\d{2})[-/.]?(\d{2})", text)
        return "-".join(match.groups()) if match else None


def signal_queries() -> List[str]:
    configured = os.getenv("SALES_SIGNAL_QUERIES", "")
    values = [token.strip() for token in re.split(r"[\n,;]+", configured) if token.strip()]
    source = values or DEFAULT_SIGNAL_QUERIES
    maximum = max(1, min(40, int(os.getenv("SALES_SIGNAL_MAX_QUERIES", "15"))))
    return list(dict.fromkeys(source))[:maximum]


class MarketSignalCollector(BaseCollector):
    name = "MarineSalesSignalSearch"
    source_type = "NEWS"
    operations: Dict[str, Dict[str, str]] = {}

    def configured(self) -> bool:
        naver = bool(os.getenv("NAVER_CLIENT_ID") and os.getenv("NAVER_CLIENT_SECRET"))
        google = os.getenv("GOOGLE_NEWS_VERIFY_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
        return naver or google

    async def _naver_rows(self, query: str) -> List[Dict[str, Any]]:
        response = await self._http_get(
            "https://openapi.naver.com/v1/search/news.json",
            {
                "query": query,
                "display": max(1, min(30, int(os.getenv("SALES_SIGNAL_RESULTS_PER_QUERY", "10")))),
                "sort": "date",
            },
            headers={
                "X-Naver-Client-Id": os.getenv("NAVER_CLIENT_ID", "").strip(),
                "X-Naver-Client-Secret": os.getenv("NAVER_CLIENT_SECRET", "").strip(),
            },
        )
        return response.json().get("items") or []

    async def _google_rows(self, query: str) -> List[Dict[str, Any]]:
        response = await self._http_get(
            "https://news.google.com/rss/search",
            {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
        )
        root = ET.fromstring(response.text.lstrip("\ufeff"))
        maximum = max(1, min(30, int(os.getenv("SALES_SIGNAL_RESULTS_PER_QUERY", "10"))))
        rows: List[Dict[str, Any]] = []
        for node in root.findall(".//item")[:maximum]:
            source_node = node.find("source")
            rows.append({
                "title": node.findtext("title") or "",
                "description": node.findtext("description") or "",
                "link": node.findtext("link") or "",
                "originallink": node.findtext("link") or "",
                "pubDate": node.findtext("pubDate") or "",
                "publisher": _clean_html(source_node.text if source_node is not None else "Google News"),
            })
        return rows

    async def _search(self, query: str) -> Tuple[str, List[Dict[str, Any]]]:
        if os.getenv("NAVER_CLIENT_ID", "").strip() and os.getenv("NAVER_CLIENT_SECRET", "").strip():
            try:
                return "NAVER_NEWS", await self._naver_rows(query)
            except Exception:
                if os.getenv("GOOGLE_NEWS_VERIFY_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
                    raise
        return "GOOGLE_NEWS_RSS", await self._google_rows(query)

    async def collect(self, seed_projects: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        semaphore = asyncio.Semaphore(max(1, min(6, int(os.getenv("SALES_SIGNAL_CONCURRENCY", "3")))))

        async def bounded(query: str) -> Tuple[str, str, List[Dict[str, Any]]]:
            async with semaphore:
                provider, rows = await self._search(query)
                return query, provider, rows

        batches = await asyncio.gather(*(bounded(query) for query in signal_queries()), return_exceptions=True)
        projects: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            query, provider, rows = batch
            for row in rows:
                title = _clean_html(row.get("title"))
                summary = _clean_html(row.get("description"))
                url = _safe_url(row.get("originallink") or row.get("link"))
                if not title or not url:
                    continue
                fingerprint = f"{url}|{title.lower()}"
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                publisher = _clean_html(row.get("publisher")) or urlparse(url).netloc.removeprefix("www.")
                project = self.clean_item(
                    f"market_signal:{provider}",
                    {
                        **row,
                        "title": title,
                        "description": summary,
                        "publisher": publisher,
                        "link": url,
                        "_marketSignal": {"query": query, "provider": provider},
                    },
                    title=title,
                    publisher=publisher,
                    source_url=url,
                    registered_at=_date_only(row.get("pubDate")),
                )
                if not project:
                    continue
                for source in project.get("sources") or []:
                    source["evidenceKind"] = "INDEPENDENT_NEWS"
                    source["provider"] = provider
                    source["summary"] = summary[:500]
                projects.append(project)
                if len(projects) >= self.max_items:
                    return projects
        return projects

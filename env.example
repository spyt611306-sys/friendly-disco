# -*- coding: utf-8 -*-
"""공식 조달 근거와 외부 뉴스 근거를 교차 평가하는 프로젝트 검증기."""

from __future__ import annotations

import asyncio
import hashlib
import html
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import httpx


OFFICIAL_TYPES = {"G2B", "PUBLIC_STD", "PUBLIC_NOTICE", "SHIP", "G2B_DOCUMENT"}
NEWS_TYPES = {"NEWS", "PRESS"}
MARINE_ANCHORS = {
    "선박", "함정", "경비정", "경비함", "관공선", "소방정", "병원선", "실습선", "연구선", "지도선",
    "차도선", "청항선", "행정선", "예인선", "방제선", "건조", "신조", "개조", "전기추진", "하이브리드",
    "ship", "vessel", "shipbuilding", "patrol",
}
STOPWORDS = {
    "사업", "공고", "입찰", "용역", "구매", "제작", "관련", "대한", "대한민국", "추진", "계획", "정보",
    "및", "위한", "통한", "대상", "시행", "공개", "모집", "결과", "계약", "최종", "the", "for", "and",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_html(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split()).strip()


def tokens(value: Any) -> Set[str]:
    words = re.findall(r"[0-9A-Za-z가-힣]+", clean_html(value).lower())
    return {word for word in words if len(word) >= 2 and word not in STOPWORDS}


def safe_url(value: Any) -> Optional[str]:
    url = str(value or "").strip()
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else None


def source_key(source: Dict[str, Any]) -> str:
    return f"{safe_url(source.get('url')) or ''}|{clean_html(source.get('title')).lower()}"


def merge_sources(*groups: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for group in groups:
        for source in group or []:
            if not isinstance(source, dict):
                continue
            key = source_key(source) or str(source.get("id") or "")
            if key and key not in merged:
                merged[key] = source
    return list(merged.values())


class ProjectVerifier:
    """네이버 뉴스 API를 우선 사용하고, 선택적으로 Google News RSS를 보조로 사용한다."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self.naver_client_id = os.getenv("NAVER_CLIENT_ID", "").strip()
        self.naver_client_secret = os.getenv("NAVER_CLIENT_SECRET", "").strip()
        self.google_enabled = os.getenv("GOOGLE_NEWS_VERIFY_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
        self.timeout = max(5, int(os.getenv("VERIFY_TIMEOUT_SECONDS", "20")))
        self.max_results = max(1, min(20, int(os.getenv("VERIFY_NEWS_RESULTS", "8"))))
        self.minimum_match = max(35, min(95, int(os.getenv("VERIFY_MIN_MATCH_SCORE", "58"))))
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={"User-Agent": "MarineSalesIntelligence/3.2 (+project-verification)"},
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
            trust_env=False,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    def build_query(self, project: Dict[str, Any]) -> str:
        title_tokens = sorted(tokens(project.get("name")))
        anchors = [word for word in title_tokens if any(anchor in word or word in anchor for anchor in MARINE_ANCHORS)]
        specific = [word for word in title_tokens if word not in anchors]
        company = clean_html(project.get("company"))
        chosen = [*anchors[:3], *specific[:4]]
        query = " ".join(dict.fromkeys([*chosen, company]))
        return query[:180] or clean_html(project.get("name"))[:180]

    def match_score(self, project: Dict[str, Any], article: Dict[str, Any]) -> int:
        project_text = " ".join([
            clean_html(project.get("name")), clean_html(project.get("company")),
            clean_html(project.get("announcementNo")), clean_html(project.get("projectNo")),
        ])
        article_text = " ".join([clean_html(article.get("title")), clean_html(article.get("description"))])
        project_tokens = tokens(project_text)
        article_tokens = tokens(article_text)
        if not project_tokens or not article_tokens:
            return 0
        overlap = project_tokens & article_tokens
        coverage = len(overlap) / max(1, min(8, len(project_tokens)))
        agency_tokens = tokens(project.get("company"))
        agency_hit = bool(agency_tokens & article_tokens)
        marine_hit = any(anchor in article_text.lower() for anchor in MARINE_ANCHORS)
        identifiers = [project.get("announcementNo"), project.get("contractNo"), project.get("projectNo")]
        identifier_hit = any(str(value) in article_text for value in identifiers if value)
        score = round(coverage * 62 + (18 if agency_hit else 0) + (10 if marine_hit else 0) + (25 if identifier_hit else 0))
        return min(100, score)

    async def search_news(self, project: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str, List[str]]:
        query = self.build_query(project)
        warnings: List[str] = []
        if self.naver_client_id and self.naver_client_secret:
            try:
                return await self._search_naver(project, query), "NAVER_NEWS", warnings
            except Exception as exc:  # 외부 장애가 공식 근거를 무효화하지 않도록 보조 채널로 전환
                warnings.append(f"네이버 뉴스 확인 실패: {type(exc).__name__}")
        if self.google_enabled:
            try:
                return await self._search_google_rss(project, query), "GOOGLE_NEWS_RSS", warnings
            except Exception as exc:
                warnings.append(f"Google News RSS 확인 실패: {type(exc).__name__}")
        warnings.append("활성화된 뉴스 검색 채널이 없습니다.")
        return [], "NONE", warnings

    async def _search_naver(self, project: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
        response = await self.client.get(
            "https://openapi.naver.com/v1/search/news.json",
            params={"query": query, "display": self.max_results, "sort": "date"},
            headers={
                "X-Naver-Client-Id": self.naver_client_id,
                "X-Naver-Client-Secret": self.naver_client_secret,
            },
        )
        response.raise_for_status()
        return self._rank_articles(project, response.json().get("items") or [], "NAVER_NEWS")

    async def _search_google_rss(self, project: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
        response = await self.client.get(
            "https://news.google.com/rss/search",
            params={"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.text.lstrip("\ufeff"))
        rows: List[Dict[str, Any]] = []
        for node in root.findall(".//item")[: self.max_results]:
            source_node = node.find("source")
            rows.append({
                "title": node.findtext("title") or "",
                "description": node.findtext("description") or "",
                "link": node.findtext("link") or "",
                "originallink": node.findtext("link") or "",
                "pubDate": node.findtext("pubDate") or "",
                "publisher": clean_html(source_node.text if source_node is not None else "Google News"),
            })
        return self._rank_articles(project, rows, "GOOGLE_NEWS_RSS")

    def _rank_articles(self, project: Dict[str, Any], rows: List[Dict[str, Any]], provider: str) -> List[Dict[str, Any]]:
        evidence: List[Dict[str, Any]] = []
        for row in rows:
            score = self.match_score(project, row)
            url = safe_url(row.get("originallink") or row.get("link"))
            if score < self.minimum_match or not url:
                continue
            published = clean_html(row.get("pubDate"))
            try:
                published_date = parsedate_to_datetime(published).date().isoformat()
            except (TypeError, ValueError, OverflowError):
                match = re.search(r"20\d{2}-\d{2}-\d{2}", published)
                published_date = match.group(0) if match else None
            title = clean_html(row.get("title"))
            publisher = clean_html(row.get("publisher")) or urlparse(url).netloc.removeprefix("www.")
            digest = hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:16]
            evidence.append({
                "id": f"NEWS-{digest}",
                "title": title,
                "publisher": publisher,
                "url": url,
                "date": published_date,
                "type": "NEWS",
                "evidenceKind": "INDEPENDENT_NEWS",
                "matchScore": score,
                "provider": provider,
                "summary": clean_html(row.get("description"))[:500],
            })
        evidence.sort(key=lambda item: (item.get("matchScore") or 0, item.get("date") or ""), reverse=True)
        return evidence[:5]

    async def verify(self, project: Dict[str, Any], search_external: bool = True) -> Dict[str, Any]:
        result = dict(project)
        existing_sources = [source for source in project.get("sources") or [] if isinstance(source, dict)]
        official_sources = [
            source for source in existing_sources
            if str(source.get("type") or project.get("sourceType") or "").upper() in OFFICIAL_TYPES
            or str(source.get("evidenceKind") or "").upper() == "OFFICIAL"
        ]
        existing_news = [
            source for source in existing_sources
            if str(source.get("type") or "").upper() in NEWS_TYPES
            or str(source.get("evidenceKind") or "").upper() == "INDEPENDENT_NEWS"
        ]
        found_news: List[Dict[str, Any]] = []
        provider = "EXISTING_EVIDENCE"
        warnings: List[str] = []
        query = self.build_query(project)
        if search_external:
            found_news, provider, warnings = await self.search_news(project)
        news_sources = merge_sources(existing_news, found_news)
        all_sources = merge_sources(existing_sources, found_news)
        official_count = len(merge_sources(official_sources))
        direct_official_count = sum(1 for source in official_sources if safe_url(source.get("url")) and source.get("isDirectLink") is not False)
        attachment_count = sum(1 for source in official_sources if str(source.get("evidenceKind") or "").upper() == "OFFICIAL_ATTACHMENT")
        news_publishers = {clean_html(source.get("publisher")).lower() for source in news_sources if source.get("publisher")}

        if official_count and news_sources:
            status, confidence = "CROSS_VERIFIED", min(99, 90 + min(9, len(news_sources) * 3))
            reason = f"공식 조달/기관 근거 {official_count}건과 독립 뉴스 근거 {len(news_sources)}건이 교차 확인되었습니다."
        elif official_count:
            status, confidence = "OFFICIAL_CONFIRMED", min(89, 72 + min(17, official_count * 5))
            reason = f"공식 조달/기관 데이터 {official_count}건에서 프로젝트가 확인되었습니다. 원문·첨부 바로가기 {direct_official_count}건을 확인할 수 있습니다."
        elif len(news_publishers) >= 2:
            status, confidence = "NEWS_CORROBORATED", min(79, 60 + len(news_publishers) * 6)
            reason = f"서로 다른 뉴스 출처 {len(news_publishers)}곳에서 관련 내용이 확인되었으나 공식 조달 근거 확인이 필요합니다."
        else:
            status, confidence = "NEEDS_REVIEW", 35 if news_sources else 15
            reason = "공식 근거 또는 충분한 독립 뉴스 근거를 확인하지 못했습니다. 수동 검토가 필요합니다."

        if official_count and direct_official_count == 0:
            warnings.append("공식 API 레코드는 확인됐지만 원문 바로가기가 없어 공고·사업번호로 나라장터 수동 검색이 필요합니다.")

        checked_at = now_iso()
        verification = {
            "status": status,
            "confidence": confidence,
            "reason": reason,
            "checkedAt": checked_at,
            "query": query,
            "provider": provider,
            "officialEvidenceCount": official_count,
            "directOfficialEvidenceCount": direct_official_count,
            "attachmentEvidenceCount": attachment_count,
            "newsEvidenceCount": len(news_sources),
            "evidenceUrls": [source["url"] for source in all_sources if safe_url(source.get("url"))],
            "warnings": warnings,
        }
        raw = {**(project.get("rawPayload") or {}), "_verification": verification}
        history = list(project.get("history") or [])
        event_id = hashlib.sha1(f"{project.get('dedupeKey')}|{status}|{checked_at[:10]}".encode("utf-8")).hexdigest()[:16]
        if not any(item.get("id") == f"V-{event_id}" for item in history if isinstance(item, dict)):
            history.append({
                "id": f"V-{event_id}", "date": checked_at[:10], "action": "EVIDENCE_VERIFIED", "detail": reason,
            })
        result.update({
            "verificationStatus": status,
            "verificationConfidence": confidence,
            "verificationCheckedAt": checked_at,
            "rawPayload": raw,
            "sources": all_sources,
            "history": history,
        })
        return result

    async def verify_many(self, projects: List[Dict[str, Any]], limit: int = 30) -> List[Dict[str, Any]]:
        semaphore = asyncio.Semaphore(max(1, min(6, int(os.getenv("VERIFY_CONCURRENCY", "3")))))

        async def one(project: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self.verify(project)

        selected = projects[: max(1, limit)]
        return await asyncio.gather(*(one(project) for project in selected))

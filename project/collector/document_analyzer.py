# -*- coding: utf-8 -*-
"""Download and summarize official procurement attachments with strict limits.

Only compact evidence snippets and keyword matches are stored. Full documents are not
persisted in PostgreSQL, which keeps the dashboard responsive and avoids duplicating
potentially large procurement files.
"""

from __future__ import annotations

import io
import os
import re
import zlib
from copy import deepcopy
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse
from zipfile import BadZipFile, ZipFile

import httpx
import olefile
from pypdf import PdfReader

from .base import EQUIPMENT_WEIGHTS, SOLUTION_GROUPS, clean_text, env_int, matched_terms, normalized


def _truthy(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _xml_text(data: bytes) -> str:
    text = data.decode("utf-8", errors="ignore")
    text = re.sub(r"<[^>]+>", " ", text)
    return clean_text(text)


def _compact_text(text: str, limit: int = 150000) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    return clean_text(text)[:limit]


class DocumentAnalyzer:
    def __init__(self) -> None:
        self.enabled = _truthy("DOCUMENT_ANALYSIS_ENABLED", "true")
        self.max_bytes = env_int("DOCUMENT_MAX_BYTES", 15_000_000, 100_000, 50_000_000)
        self.max_pages = env_int("DOCUMENT_MAX_PDF_PAGES", 40, 1, 200)
        self.timeout = env_int("DOCUMENT_TIMEOUT_SECONDS", 25, 5, 90)
        configured_hosts = [item.strip().lower() for item in os.getenv("DOCUMENT_ALLOWED_HOSTS", "g2b.go.kr").split(",") if item.strip()]
        self.allowed_hosts = configured_hosts or ["g2b.go.kr"]
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={"User-Agent": "ShipDeliveryIntelligence/3.2 (+official-document-analysis)"},
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            trust_env=False,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    def _allowed_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        hostname = (parsed.hostname or "").lower()
        return parsed.scheme == "https" and any(hostname == host or hostname.endswith(f".{host}") for host in self.allowed_hosts)

    async def _download(self, url: str) -> Tuple[bytes, str, str]:
        if not self._allowed_url(url):
            raise ValueError("허용되지 않은 첨부문서 호스트")
        async with self.client.stream("GET", url) as response:
            response.raise_for_status()
            content_length = int(response.headers.get("content-length") or 0)
            if content_length and content_length > self.max_bytes:
                raise ValueError(f"첨부문서 용량이 제한({self.max_bytes:,} bytes)을 초과")
            chunks: List[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > self.max_bytes:
                    raise ValueError(f"첨부문서 용량이 제한({self.max_bytes:,} bytes)을 초과")
                chunks.append(chunk)
            disposition = response.headers.get("content-disposition", "")
            filename_match = re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)", disposition, flags=re.I)
            filename = unquote(filename_match.group(1).strip()) if filename_match else PurePosixPath(urlparse(str(response.url)).path).name
            return b"".join(chunks), response.headers.get("content-type", ""), filename

    def _detect_format(self, data: bytes, content_type: str, filename: str) -> str:
        extension = PurePosixPath(filename.lower()).suffix.lstrip(".")
        if data.startswith(b"%PDF") or "pdf" in content_type:
            return "pdf"
        if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1") or extension == "hwp":
            return "hwp"
        if data.startswith(b"PK\x03\x04"):
            if extension in {"hwpx", "docx", "xlsx", "pptx"}:
                return extension
            return "zip"
        if extension in {"txt", "csv", "xml", "html", "htm"} or content_type.startswith("text/"):
            return extension or "text"
        return extension or "binary"

    def _extract_pdf(self, data: bytes) -> str:
        reader = PdfReader(io.BytesIO(data))
        return " ".join((page.extract_text() or "") for page in reader.pages[: self.max_pages])

    def _extract_zip_xml(self, data: bytes, fmt: str) -> str:
        with ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            if fmt == "hwpx":
                targets = [name for name in names if name.startswith("Contents/") and name.endswith(".xml")]
            elif fmt == "docx":
                targets = [name for name in names if name.startswith("word/") and name.endswith(".xml")]
            elif fmt == "xlsx":
                targets = [name for name in names if (name.startswith("xl/worksheets/") or name == "xl/sharedStrings.xml") and name.endswith(".xml")]
            else:
                targets = [name for name in names if name.lower().endswith((".xml", ".txt", ".csv"))]
            parts: List[str] = []
            for name in targets[:80]:
                info = archive.getinfo(name)
                if info.file_size > 5_000_000:
                    continue
                parts.append(_xml_text(archive.read(name)))
            return " ".join(parts)

    def _extract_hwp(self, data: bytes) -> str:
        with olefile.OleFileIO(io.BytesIO(data)) as document:
            header = document.openstream("FileHeader").read() if document.exists("FileHeader") else b""
            compressed = len(header) >= 40 and bool(int.from_bytes(header[36:40], "little") & 1)
            section_names = sorted(
                (entry for entry in document.listdir() if len(entry) == 2 and entry[0] == "BodyText" and entry[1].startswith("Section")),
                key=lambda entry: int(re.sub(r"\D", "", entry[1]) or 0),
            )
            parts: List[str] = []
            for entry in section_names[:80]:
                stream = document.openstream(entry).read()
                if compressed:
                    try:
                        stream = zlib.decompress(stream, -15)
                    except zlib.error:
                        continue
                parts.append(stream.decode("utf-16le", errors="ignore"))
            return " ".join(parts)

    def _extract_text(self, data: bytes, fmt: str) -> str:
        if fmt == "pdf":
            return self._extract_pdf(data)
        if fmt == "hwp":
            return self._extract_hwp(data)
        if fmt in {"hwpx", "docx", "xlsx", "pptx", "zip"}:
            return self._extract_zip_xml(data, fmt)
        if fmt in {"txt", "text", "csv", "xml", "html", "htm"}:
            for encoding in ("utf-8", "cp949", "euc-kr"):
                try:
                    return data.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return data.decode("utf-8", errors="ignore")
        raise ValueError(f"본문 추출을 지원하지 않는 형식: {fmt}")

    def _summarize(self, text: str) -> Dict[str, Any]:
        compact = _compact_text(text)
        source = normalized(compact)
        equipment = matched_terms(source, EQUIPMENT_WEIGHTS)
        solution_areas = [label for label, terms in SOLUTION_GROUPS.items() if matched_terms(source, terms)]
        anchor = next((normalized(term) for term in equipment if normalized(term) in source), "")
        start = max(0, source.find(anchor) - 180) if anchor else 0
        excerpt = source[start : start + 900]
        return {
            "matchedKeywords": equipment[:30],
            "solutionAreas": solution_areas,
            "excerpt": excerpt,
            "textLength": len(compact),
        }

    async def analyze_source(self, source: Dict[str, Any]) -> Dict[str, Any]:
        url = clean_text(source.get("url"))
        data, content_type, filename = await self._download(url)
        fmt = self._detect_format(data, content_type, filename)
        text = self._extract_text(data, fmt)
        summary = self._summarize(text)
        if summary["textLength"] < 20:
            raise ValueError("추출 가능한 본문이 없습니다. 스캔 문서는 OCR 확인이 필요합니다.")
        return {"status": "ANALYZED", "filename": filename or source.get("title"), "format": fmt, "bytes": len(data), **summary}

    async def enrich_project(self, project: Dict[str, Any], max_attachments: int = 2) -> Dict[str, Any]:
        if not self.enabled:
            return project
        result = deepcopy(project)
        sources = [source for source in result.get("sources") or [] if isinstance(source, dict)]
        document_sources = [source for source in sources if str(source.get("evidenceKind") or "").upper() == "OFFICIAL_ATTACHMENT"][:max_attachments]
        documents: List[Dict[str, Any]] = []
        for source in document_sources:
            try:
                analysis = await self.analyze_source(source)
            except (httpx.HTTPError, ValueError, BadZipFile, OSError, zlib.error) as exc:
                analysis = {"status": "FAILED", "error": clean_text(str(exc))[:300]}
            source.update({
                "analysisStatus": analysis.get("status"),
                "documentFormat": analysis.get("format"),
                "matchedKeywords": analysis.get("matchedKeywords") or [],
                "summary": analysis.get("excerpt") or "",
            })
            documents.append({"sourceId": source.get("id"), "title": source.get("title"), "url": source.get("url"), **analysis})

        successful = [item for item in documents if item.get("status") == "ANALYZED"]
        if not documents:
            return result
        raw = deepcopy(result.get("rawPayload") or {})
        raw["_documents"] = {"analyzedCount": len(successful), "documents": documents}
        sales = deepcopy(raw.get("_salesIntelligence") or {})
        document_keywords = sorted({term for item in successful for term in item.get("matchedKeywords") or []})
        document_solutions = sorted({term for item in successful for term in item.get("solutionAreas") or []})
        if document_keywords:
            targeting = deepcopy(raw.get("_abbTargeting") or {})
            targeting["score"] = min(100, int(targeting.get("score") or 0) + min(18, 5 + len(document_solutions) * 4))
            targeting["priority"] = "HOT" if targeting["score"] >= 78 else "WARM" if targeting["score"] >= 58 else "WATCH"
            detail = deepcopy(targeting.get("detail") or {})
            detail["equipmentKeywords"] = sorted(set((detail.get("equipmentKeywords") or []) + document_keywords))
            targeting["detail"] = detail
            raw["_abbTargeting"] = targeting
            sales["opportunityClass"] = "P0"
            sales["solutionAreas"] = sorted(set((sales.get("solutionAreas") or []) + document_solutions))
            sales["salesReasons"] = list(sales.get("salesReasons") or []) + [f"공식 첨부문서에서 장비 키워드 확인: {', '.join(document_keywords[:6])}"]
            sales["recommendedAction"] = "첨부 규격서의 용량·전압·선급 조건을 검토하고 발주처/설계사에 즉시 사양 제안"
            result["matchedKeywords"] = sorted(set((result.get("matchedKeywords") or []) + document_keywords))
            result["keywordText"] = " ".join(result["matchedKeywords"])
        raw["_salesIntelligence"] = sales
        result["rawPayload"] = raw
        result["sources"] = sources
        return result

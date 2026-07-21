# -*- coding: utf-8 -*-
"""공공데이터 수집기의 공통 HTTP, 파싱, 정규화, 스코어링 계층."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote
from xml.etree import ElementTree as ET

import httpx

from sales_intelligence import classify_sales_opportunity

logger = logging.getLogger("sdi.collector")

MARINE_KEYWORDS = [
    "선박", "함정", "함선", "조선", "조선소", "실습선", "탐사선", "탐사실습선", "행정선", "청항선",
    "안내선", "관공선", "경비함", "경비정", "순시선", "예인선", "방제선", "지원선", "부선", "소방정",
    "차도선", "병원선", "연구선", "어업지도선", "지도선", "함정정비", "신조", "대체건조", "건조",
    "ship", "vessel", "patrol vessel", "training ship", "government vessel", "shipyard", "shipbuilding",
    "dry dock", "offshore vessel", "coast guard vessel", "crew transfer vessel", "ctv",
]

WATCHLIST_TERMS = [
    "실습선", "탐사선", "어업지도선", "경비함", "경비정", "소방정", "차도선", "병원선", "청항선",
    "행정선", "관공선", "하이브리드", "전기추진", "축발전기", "dc grid", "3000톤", "3,000톤",
]

BUYER_WEIGHTS: Dict[str, int] = {
    "해양경찰": 18, "해경": 16, "coast guard": 16, "소방청": 15, "소방본부": 15,
    "해양수산부": 14, "어업관리단": 14, "항만공사": 12, "해양환경공단": 12,
    "지방자치단체": 8, "시청": 7, "도청": 7, "군청": 7, "수산과학원": 10, "대학교": 8,
}

EQUIPMENT_WEIGHTS: Dict[str, int] = {
    "하이브리드": 18, "hybrid": 18, "전기추진": 18, "electric propulsion": 18,
    "인버터": 14, "inverter": 14, "드라이브": 14, "vfd": 14, "배터리": 12, "battery": 12,
    "ess": 12, "축발전기": 12, "shaft generator": 12, "pti": 10, "pto": 10, "dc grid": 14,
    "추진모터": 12, "propulsion motor": 12, "배전반": 7, "switchboard": 7, "waterjet": 6, "워터젯": 6,
}

SHIPYARD_TERMS = [
    "대선조선", "HJ중공업", "에이치제이중공업", "한진중공업", "강남조선", "동성조선", "극동조선",
    "삼강엠앤티", "SK오션플랜트", "대한조선", "케이조선", "HSG성동조선", "금하네이벌텍",
    "동남중공업", "삼원중공업", "코리아월드써비스", "신진조선", "세진중공업", "조선소", "shipyard",
]

BUILD_TERMS = ["건조", "대체건조", "신조", "제작구매", "제조구매", "개조", "성능개량", "기본설계", "상세설계"]

NOISE_TERMS = [
    "정수장", "해수담수화", "혈액투석", "의약품", "학교 체육관", "냉난방", "하수관", "상수관",
    "배수개선", "아스콘", "마네킹", "농업", "교량", "도로", "터널", "청진기", "압축가스",
]

TITLE_FIELDS = [
    "bidNtceNm", "cntrctNm", "orderPlanNm", "prdctClsfcNoNm", "referNm", "bsnsNm", "bidNm",
    "title", "subject", "ntceNm", "vsslNm", "shipNm", "VSSL_NM", "newsTitle",
]
PUBLISHER_FIELDS = [
    "dminsttNm", "orderInsttNm", "cntrctInsttNm", "dmndInsttNm", "pubPrcrmntLrgClsfcNm",
    "agency", "publisher", "insttNm",
]
ANNOUNCEMENT_FIELDS = ["bidNtceNo", "ntceNo", "bidPbancNo", "announcementNo"]
CONTRACT_FIELDS = ["cntrctNo", "contractNo", "untyCntrctNo"]
PROJECT_FIELDS = ["orderPlanNo", "bsnsNo", "projectNo", "refNo"]
REGION_FIELDS = ["prtcptPsblRgnNm", "rgnNm", "region", "area", "sidoNm"]
VALUE_FIELDS = ["presmptPrce", "asignBdgtAmt", "totPrdprc", "cntrctAmt", "sumOrderAmt", "fnlSucsfAmt", "orderValue"]
REGISTERED_FIELDS = ["bidNtceDt", "rgstDt", "ntceDt", "createdAt", "registeredAt", "opengDt", "orderYear", "pubDate"]
CONTRACT_DATE_FIELDS = ["cntrctCnclsDate", "contractDate"]
DELIVERY_FIELDS = ["dlvrDate", "deliveryDate", "thtmCmpltnDate", "deliveryDueDate"]
SHIPYARD_FIELDS = ["cntrctCorpNm", "sucsfbidCorpNm", "shipyard", "builder"]
DESCRIPTION_FIELDS = ["description", "summary", "content", "body", "newsSummary"]
LINK_FIELDS = [
    "bidNtceDtlUrl", "bidNtceUrl", "cntrctDtlInfoUrl", "orderPlanUrl", "prespecUrl",
    "ntceDtlUrl", "detailUrl", "originallink", "link", "url",
]


def env_int(name: str, default: int, minimum: int = 1, maximum: int = 10000) -> int:
    try:
        return max(minimum, min(maximum, int(os.getenv(name, str(default)))))
    except (TypeError, ValueError):
        return default


def chunk_days(start: date, end: date, chunk_size: int) -> List[Tuple[date, date]]:
    chunk_size = max(1, chunk_size)
    windows: List[Tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        right = min(end, cursor + timedelta(days=chunk_size - 1))
        windows.append((cursor, right))
        cursor = right + timedelta(days=1)
    return windows


get_env_int = env_int


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", "").split()).strip()


def normalized(value: Any) -> str:
    return re.sub(r"[\s\-_/·ㆍ,.:;()\[\]{}]+", " ", clean_text(value).lower()).strip()


def env_terms(name: str) -> List[str]:
    return [clean_text(value) for value in os.getenv(name, "").split(",") if clean_text(value)]


def first_value(item: Dict[str, Any], fields: Iterable[str]) -> str:
    for field in fields:
        value = item.get(field)
        if value not in (None, ""):
            return clean_text(value)
    return ""


def normalize_date(value: Any) -> Optional[str]:
    text = clean_text(value)
    if not text:
        return None
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    if len(digits) == 6:
        return f"{digits[:4]}-{digits[4:6]}-01"
    if len(digits) == 4:
        return f"{digits}-01-01"
    return None


def is_cctv_noise(text: str) -> bool:
    norm = normalized(text)
    has_cctv = any(term in norm for term in ["cctv", "폐쇄회로", "감시카메라", "영상정보처리기기", "영상감시"])
    has_marine = any(term in norm for term in ["선박", "함정", "경비정", "병원선", "vessel", "ship"])
    explicit_ctv = bool(re.search(r"(^|[^a-z])ctv([^a-z]|$)", norm)) and not bool(
        re.search(r"(^|[^a-z])cctv([^a-z]|$)", norm)
    )
    return has_cctv and not has_marine and not explicit_ctv


def infer_stage(operation_name: str, title: str = "") -> str:
    text = normalized(f"{operation_name} {title}")
    if any(term in text for term in ["준공", "인도완료", "delivered", "completed"]):
        return "DELIVERED"
    if any(term in text for term in ["건조중", "기골", "진수", "under construction"]):
        return "BUILD"
    if any(term in text for term in ["cntrct", "contract", "계약"]):
        return "CONTRACT"
    if any(term in text for term in ["scsbid", "award", "낙찰", "opengresult"]):
        return "EVALUATION"
    if any(term in text for term in ["prespec", "publicprcure", "사전규격", "hrcsp"]):
        return "PRESPEC"
    if any(term in text for term in ["orderplan", "발주계획"]):
        return "PLAN"
    if any(term in text for term in ["bidpblanc", "입찰공고", "bid"]):
        return "BID"
    return "LEAD"


def stable_key(
    source_type: str,
    title: str,
    publisher: str,
    announcement_no: str = "",
    contract_no: str = "",
    project_no: str = "",
    registered_at: str = "",
) -> str:
    for prefix, value in (("ANN", announcement_no), ("CON", contract_no), ("PJT", project_no)):
        key = re.sub(r"[^0-9a-z가-힣]", "", normalized(value))
        if key:
            return f"{prefix}:{key}"
    identity = f"{normalized(title)[:120]}|{normalized(publisher)[:60]}|{registered_at[:4]}|{source_type}"
    return f"TXT:{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:28]}"


def parse_xml_payload(text: str) -> Dict[str, Any]:
    root = ET.fromstring(text)

    def node_to_value(node: ET.Element) -> Any:
        children = list(node)
        if not children:
            return clean_text(node.text)
        result: Dict[str, Any] = {}
        for child in children:
            value = node_to_value(child)
            if child.tag in result:
                current = result[child.tag]
                result[child.tag] = current + [value] if isinstance(current, list) else [current, value]
            else:
                result[child.tag] = value
        return result

    return {root.tag: node_to_value(root)}


def find_mapping(payload: Any, keys: Iterable[str]) -> Dict[str, Any]:
    if isinstance(payload, dict):
        for key in keys:
            candidate = payload.get(key)
            if isinstance(candidate, dict):
                return candidate
        for value in payload.values():
            found = find_mapping(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = find_mapping(value, keys)
            if found:
                return found
    return {}


def find_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        if all(isinstance(item, dict) for item in payload):
            return payload
        for item in payload:
            found = find_items(item)
            if found:
                return found
    if isinstance(payload, dict):
        for key in ("item", "items", "data", "rows", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = value.get("item")
                if isinstance(nested, list):
                    return [item for item in nested if isinstance(item, dict)]
                if isinstance(nested, dict):
                    return [nested]
        for value in payload.values():
            found = find_items(value)
            if found:
                return found
    return []


class BaseCollector:
    name = "BaseCollector"
    source_type = "OTHER"
    base_url = ""
    key_env_name = "DATA_GO_KR_API_KEY"
    key_param_name = "serviceKey"
    default_type = "json"
    default_num_rows = 100
    operations: Dict[str, Dict[str, str]] = {}

    def __init__(self) -> None:
        self.max_pages = env_int("MAX_PAGES_PER_OPERATION", 10, 1, 100)
        self.max_items = env_int("MAX_ITEMS_PER_OPERATION", 1000, 1, 10000)
        self.timeout_seconds = float(env_int("API_TIMEOUT_SECONDS", 25, 5, 120))
        self.retry_count = env_int("API_RETRY_COUNT", 3, 0, 6)
        self._client: Optional[httpx.AsyncClient] = None

    def http_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                follow_redirects=True,
                headers={"Accept": "application/json, application/xml, text/xml"},
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def api_key(self) -> str:
        candidates = [
            self.key_env_name,
            "SHIP_API_KEY" if self.source_type == "SHIP" else "",
            "PUBLIC_DATA_API_KEY",
            "DATA_GO_KR_API_KEY",
        ]
        for name in candidates:
            if name:
                value = os.getenv(name, "").strip()
                if value:
                    return unquote(value)
        return ""

    def evaluate_relevance(self, text: str) -> Dict[str, Any]:
        return classify_sales_opportunity(text)

    async def _http_get(
        self,
        url: str,
        params: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        last_error: Optional[Exception] = None
        for attempt in range(self.retry_count + 1):
            try:
                response = await self.http_client().get(url, params=params, headers=headers)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"retryable HTTP {response.status_code}", request=response.request, response=response
                    )
                response.raise_for_status()
                return response
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                last_error = exc
                if attempt >= self.retry_count:
                    break
                await asyncio.sleep(min(8.0, 0.6 * (2 ** attempt)))
        raise RuntimeError(f"{self.name} 요청 실패: {last_error}")

    async def request_operation(self, operation_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if operation_name not in self.operations:
            raise ValueError(f"지원하지 않는 operation: {operation_name}")
        if not self.base_url:
            raise RuntimeError(f"{self.name} base URL이 설정되지 않았습니다.")
        key = self.api_key()
        if not key:
            raise RuntimeError(f"{self.name} API 키가 설정되지 않았습니다.")

        operation = self.operations[operation_name]
        url = f"{self.base_url.rstrip('/')}/{operation.get('path', operation_name).lstrip('/')}"
        query: Dict[str, Any] = {
            self.key_param_name: key,
            "pageNo": 1,
            "numOfRows": self.default_num_rows,
            **(params or {}),
        }
        if self.default_type:
            query.setdefault("type", self.default_type)

        started = time.perf_counter()
        response = await self._http_get(url, query)
        text = response.text.lstrip("\ufeff").strip()
        try:
            payload = response.json() if "json" in response.headers.get("content-type", "").lower() or text.startswith(("{", "[")) else parse_xml_payload(text)
        except (json.JSONDecodeError, ET.ParseError, ValueError) as exc:
            raise RuntimeError(f"{self.name}/{operation_name} 응답 파싱 실패") from exc

        header = find_mapping(payload, ("header", "cmmMsgHeader"))
        body = find_mapping(payload, ("body",))
        result_code = clean_text(header.get("resultCode") or header.get("returnReasonCode") or "")
        result_message = clean_text(header.get("resultMsg") or header.get("returnAuthMsg") or "")
        if result_code and result_code not in {"00", "0", "000"}:
            raise RuntimeError(f"{self.name} API 오류 {result_code}: {result_message or 'unknown error'}")
        items = find_items(body or payload)
        return {
            "header": header,
            "body": body,
            "items": items,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    async def request_all_pages(self, operation_name: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        seen: set[str] = set()
        base_params = dict(params or {})
        for page in range(1, self.max_pages + 1):
            result = await self.request_operation(
                operation_name,
                {**base_params, "pageNo": page, "numOfRows": self.default_num_rows},
            )
            items = result["items"]
            if not items:
                break
            added = 0
            for item in items:
                fingerprint = hashlib.sha1(
                    json.dumps(item, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
                ).hexdigest()
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                rows.append(item)
                added += 1
                if len(rows) >= self.max_items:
                    return rows
            total_count = int(str(result["body"].get("totalCount") or "0").replace(",", "") or 0)
            if added == 0 or len(items) < self.default_num_rows or (total_count and len(rows) >= total_count):
                break
        return rows

    def build_project(self, operation_name: str, item: Dict[str, Any], source_url: str) -> Optional[Dict[str, Any]]:
        title = first_value(item, TITLE_FIELDS)
        if not title:
            return None
        publisher = first_value(item, PUBLISHER_FIELDS)
        combined = f"{title} {publisher} {first_value(item, SHIPYARD_FIELDS)} {first_value(item, DESCRIPTION_FIELDS)}"
        relevance = self.evaluate_relevance(combined)
        if relevance["priority"] == "DROP":
            return None

        announcement_no = first_value(item, ANNOUNCEMENT_FIELDS)
        contract_no = first_value(item, CONTRACT_FIELDS)
        project_no = first_value(item, PROJECT_FIELDS)
        registered_at = normalize_date(first_value(item, REGISTERED_FIELDS))
        contract_date = normalize_date(first_value(item, CONTRACT_DATE_FIELDS))
        delivery_date = normalize_date(first_value(item, DELIVERY_FIELDS))
        region = first_value(item, REGION_FIELDS)
        order_value = first_value(item, VALUE_FIELDS)
        shipyard = first_value(item, SHIPYARD_FIELDS)
        stage = infer_stage(operation_name, title)
        dedupe_key = stable_key(
            self.source_type, title, publisher, announcement_no, contract_no, project_no, registered_at or ""
        )
        collected_at = now_iso()
        record_url = first_value(item, LINK_FIELDS)
        is_direct_link = record_url.startswith(("https://", "http://"))
        if not is_direct_link:
            record_url = source_url
        raw_payload = {
            **item,
            "_abbTargeting": {
                "classificationVersion": relevance["classification_version"],
                "score": relevance["score"],
                "priority": relevance["priority"],
                "salesCategory": relevance["sales_category"],
                "opportunityType": relevance["opportunity_type"],
                "salesTiming": relevance["sales_timing"],
                "confidence": relevance["confidence"],
                "reason": relevance["reason"],
                "recommendedAction": relevance["recommended_action"],
                "detail": {
                    "gateKeywords": relevance["platform_keywords"],
                    "buyerKeywords": relevance["buyer_keywords"],
                    "equipmentKeywords": relevance["equipment_keywords"],
                    "platformKeywords": relevance["platform_keywords"],
                    "shipyardKeywords": relevance["shipyard_keywords"],
                    "buildKeywords": relevance["build_keywords"],
                    "watchlistHits": relevance["watchlist_hits"],
                    "earlySignalKeywords": relevance["early_signal_keywords"],
                    "excludeKeywords": relevance["exclude_keywords"],
                    "componentScores": {
                        "driveScore": relevance["drive_score"],
                        "motorScore": relevance["motor_score"],
                        "powerScore": relevance["power_score"],
                    },
                },
            },
            "_collection": {"collectedAt": collected_at, "collector": self.name, "operation": operation_name},
        }
        identifier = hashlib.sha1(dedupe_key.encode("utf-8")).hexdigest()[:16].upper()
        source_id = hashlib.sha1(f"{record_url}|{title}".encode("utf-8")).hexdigest()[:16]
        history_id = hashlib.sha1(f"{dedupe_key}|{operation_name}|{collected_at[:10]}".encode("utf-8")).hexdigest()[:16]
        return {
            "dedupeKey": dedupe_key,
            "id": f"SDI-{identifier}",
            "name": title,
            "company": publisher,
            "announcementNo": announcement_no or None,
            "contractNo": contract_no or None,
            "projectNo": project_no or None,
            "region": region or None,
            "orderValue": order_value or None,
            "currency": "KRW",
            "registeredAt": registered_at,
            "contractDate": contract_date,
            "deliveryDate": delivery_date,
            "shipyard": shipyard or None,
            "stage": stage,
            "sourceType": self.source_type,
            "sourceService": self.name,
            "sourceOperation": operation_name,
            "verificationStatus": "UNVERIFIED",
            "matchedKeywords": relevance["matched_keywords"],
            "keywordText": " ".join(relevance["matched_keywords"]),
            "rawPayload": raw_payload,
            "history": [{
                "id": f"H-{history_id}",
                "date": collected_at[:10],
                "action": "COLLECTED",
                "detail": (
                    f"{self.name}/{operation_name} 수집 · ABB {relevance['score']}점 "
                    f"{relevance['priority']} · {relevance['sales_category']}"
                ),
            }],
            "sources": [{
                "id": f"S-{source_id}",
                "title": title,
                "publisher": publisher or self.name,
                "url": record_url,
                "apiUrl": source_url,
                "isDirectLink": is_direct_link,
                "date": registered_at or collected_at[:10],
                "type": self.source_type,
                "evidenceKind": "OFFICIAL" if self.source_type in {"G2B", "PUBLIC_STD", "PUBLIC_NOTICE", "SHIP"} else "DISCOVERY",
            }],
        }

    def clean_item(
        self,
        operation_name: str,
        raw_payload: Dict[str, Any],
        title: str,
        publisher: str,
        source_url: str,
        announcement_no: Optional[str] = None,
        contract_no: Optional[str] = None,
        project_no: Optional[str] = None,
        region: Optional[str] = None,
        order_value: Optional[str] = None,
        currency: str = "KRW",
        registered_at: Optional[str] = None,
        contract_date: Optional[str] = None,
        delivery_date: Optional[str] = None,
        shipyard: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        item = {
            **raw_payload,
            "title": title,
            "publisher": publisher,
            "announcementNo": announcement_no,
            "contractNo": contract_no,
            "projectNo": project_no,
            "region": region,
            "orderValue": order_value,
            "currency": currency,
            "registeredAt": registered_at,
            "contractDate": contract_date,
            "deliveryDate": delivery_date,
            "shipyard": shipyard,
        }
        return self.build_project(operation_name, item, source_url)

    async def collect(self, seed_projects: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        return []

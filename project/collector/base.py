import asyncio
import json
import logging
import os
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger("sdi.collector")

SHIP_CORE_KEYWORDS = [
    # 해양 / 선박 / 조선 핵심 문맥
    "선박", "함정", "함선", "조선", "조선소", "해양", "해군", "항만",
    "marine", "ship", "shipbuilding", "shipyard", "vessel", "offshore",
    "fpso", "flng", "fso", "barge", "tug", "towage",
    "관공선", "경비함", "순시선", "병원선", "예인선", "부선", "어업지도선",
    "지원선", "운반선", "작업선", "준설선", "급유선", "청항선", "파일럿보트",
    "pilot boat", "crew boat", "patrol vessel", "naval", "coast guard",
    "해양경찰", "해경", "선대", "선박건조", "신조", "개조", "탑재"
]

SHIP_DRIVE_KEYWORDS = [
    # 마린 전동화 / 드라이브 / 전력변환 핵심 장비 문맥
    "드라이브", "전력변환장치", "주파수변환장치", "인버터", "컨버터",
    "vfd", "vf drive", "variable frequency drive", "frequency converter",
    "power converter", "power conversion system", "pcs",
    "추진전동기", "추진모터", "모터", "전동기",
    "propulsion", "electric propulsion", "propulsion motor",
    "shaft generator", "pti", "pto", "thruster", "azimuth thruster",
    "hybrid", "battery", "ess", "energy storage system",
    "배터리", "하이브리드", "전기추진", "전기식 추진", "추진제어", "전동 추진"
]

SHIP_PLATFORM_KEYWORDS = [
    # 선종 / 선박 타입 문맥
    "lng선", "lpg선", "컨테이너선", "벌크선", "탱커", "유조선", "가스선",
    "ro-ro", "ropax", "car carrier", "pcc", "pctc", "drillship",
    "offshore vessel", "support vessel", "research vessel",
    "ferry", "passenger ship", "cargo ship", "coaster"
]

NON_MARINE_EXCLUDE_KEYWORDS = [
    # 비해양 일반 산업/시설 문맥
    "도로", "교량", "철도", "지하철", "터널", "건축", "건물", "청사", "학교",
    "병원", "하수", "상수", "정수", "하수처리", "배수지", "농업", "축산", "산림",
    "드론", "항공", "자동차", "전기차", "엘리베이터", "냉난방", "보일러",
    "태양광", "풍력", "소각", "소방서", "도로공사", "관로", "하천"
]


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def pick_first(data: Dict[str, Any], keys: Iterable[str], default: Optional[str] = None) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text != "":
            return text
    return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(str(value).replace(",", ""))
    except Exception:
        return default


def chunk_days(start_date: date, end_date: date, step_days: int) -> List[Tuple[date, date]]:
    chunks: List[Tuple[date, date]] = []
    cursor = start_date
    while cursor <= end_date:
        right = min(cursor + timedelta(days=step_days - 1), end_date)
        chunks.append((cursor, right))
        cursor = right + timedelta(days=1)
    return chunks


def xml_to_dict(element: ET.Element) -> Any:
    children = list(element)
    if not children:
        return (element.text or "").strip()
    data: Dict[str, Any] = {}
    for child in children:
        child_value = xml_to_dict(child)
        if child.tag in data:
            if not isinstance(data[child.tag], list):
                data[child.tag] = [data[child.tag]]
            data[child.tag].append(child_value)
        else:
            data[child.tag] = child_value
    return data


def normalize_items(parsed: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    response = parsed.get("response", parsed)
    header = response.get("header", {}) or {}
    body = response.get("body", {}) or {}
    items = body.get("items", {})
    if isinstance(items, dict) and "item" in items:
        items = items.get("item")
    if items is None:
        return [], header, body
    if isinstance(items, dict):
        return [items], header, body
    if isinstance(items, list):
        return items, header, body
    return [], header, body


def normalize_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def find_keyword_matches(text: str, keywords: List[str]) -> List[str]:
    normalized = normalize_text(text)
    matches: List[str] = []
    for keyword in keywords:
        if keyword.lower() in normalized:
            matches.append(keyword)
    return sorted(set(matches), key=lambda x: keywords.index(x))


def evaluate_ship_relevance(text: str, source_type: str) -> Dict[str, Any]:
    normalized = normalize_text(text)

    core_matches = find_keyword_matches(normalized, SHIP_CORE_KEYWORDS)
    drive_matches = find_keyword_matches(normalized, SHIP_DRIVE_KEYWORDS)
    platform_matches = find_keyword_matches(normalized, SHIP_PLATFORM_KEYWORDS)
    exclude_matches = find_keyword_matches(normalized, NON_MARINE_EXCLUDE_KEYWORDS)

    # 해수부 선박 API에서 온 데이터는 우선 통과
    if source_type == "SHIP":
        matched = list(dict.fromkeys(core_matches + platform_matches + drive_matches))
        return {
            "is_target": True,
            "matched_keywords": matched,
            "reason": "SHIP source_type direct pass",
        }

    has_strong_ship_context = (
        bool(platform_matches)
        or "선박" in normalized
        or "함정" in normalized
        or "함선" in normalized
        or "조선" in normalized
        or "조선소" in normalized
        or "marine" in normalized
        or "ship" in normalized
        or "vessel" in normalized
        or "offshore" in normalized
        or "해양경찰" in normalized
        or "해경" in normalized
        or "해군" in normalized
        or "항만" in normalized
    )

    has_target_combo = bool(core_matches) and bool(drive_matches)

    # 비해양 문맥이 강하고 해양 핵심 문맥이 없으면 제외
    if exclude_matches and not has_strong_ship_context and not has_target_combo:
        return {
            "is_target": False,
            "matched_keywords": [],
            "reason": f"excluded by non-marine keywords: {exclude_matches}",
        }

    # 강한 선박 문맥 + 장비/플랫폼/다중 코어 키워드
    if has_strong_ship_context and (drive_matches or platform_matches or len(core_matches) >= 2):
        matched = list(dict.fromkeys(core_matches + platform_matches + drive_matches))
        return {
            "is_target": True,
            "matched_keywords": matched,
            "reason": "strong ship context matched",
        }

    # 선박/해양 문맥 + 드라이브/전력변환 문맥 조합
    if has_target_combo:
        matched = list(dict.fromkeys(core_matches + platform_matches + drive_matches))
        return {
            "is_target": True,
            "matched_keywords": matched,
            "reason": "ship + drive combo matched",
        }

    return {
        "is_target": False,
        "matched_keywords": [],
        "reason": "not marine-drive relevant",
    }


class BaseCollector:
    name = "base"
    source_type = "G2B"
    base_url = ""
    key_env_name = "DATA_GO_KR_API_KEY"
    key_param_name = "ServiceKey"
    default_type = "json"
    default_num_rows = 100
    operations: Dict[str, Dict[str, Any]] = {}

    def __init__(self) -> None:
        self.service_key = os.getenv(self.key_env_name, "").strip()

    def ensure_key(self) -> None:
        if not self.service_key:
            raise RuntimeError(f"{self.key_env_name} 가 설정되지 않았습니다.")

    async def request_operation(self, operation_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_key()
        request_params = {k: v for k, v in params.items() if v is not None and v != ""}
        request_params[self.key_param_name] = self.service_key
        if self.default_type and "type" not in request_params:
            request_params["type"] = self.default_type

        url = f"{self.base_url}/{operation_name}"
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url, params=request_params)
                elapsed = round((time.perf_counter() - started) * 1000, 2)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "json" in content_type or response.text.lstrip().startswith("{"):
                    parsed = response.json()
                else:
                    root = ET.fromstring(response.text)
                    parsed = {root.tag: xml_to_dict(root)}
                items, header, body = normalize_items(parsed)
                logger.info(
                    "[API] collector=%s operation=%s count=%s response_ms=%s resultCode=%s",
                    self.name,
                    operation_name,
                    len(items),
                    elapsed,
                    header.get("resultCode"),
                )
                return {
                    "url": url,
                    "params": request_params,
                    "parsed": parsed,
                    "items": items,
                    "header": header,
                    "body": body,
                    "elapsed_ms": elapsed,
                }
        except Exception as exc:
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "[API-ERROR] collector=%s operation=%s response_ms=%s error=%s",
                self.name,
                operation_name,
                elapsed,
                str(exc),
            )
            raise

    async def request_all_pages(self, operation_name: str, base_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        page_no = 1
        num_rows = safe_int(base_params.get("numOfRows"), self.default_num_rows)
        all_items: List[Dict[str, Any]] = []
        while True:
            params = dict(base_params)
            params["pageNo"] = page_no
            params["numOfRows"] = num_rows
            result = await self.request_operation(operation_name, params)
            items = result["items"]
            body = result["body"]
            total_count = safe_int(body.get("totalCount"), 0)
            all_items.extend(items)
            if not items:
                break
            if total_count and len(all_items) >= total_count:
                break
            if len(items) < num_rows:
                break
            page_no += 1
        logger.info("[PAGE-END] collector=%s operation=%s total=%s", self.name, operation_name, len(all_items))
        return all_items

    def build_project(self, operation_name: str, raw: Dict[str, Any], source_url: str) -> Optional[Dict[str, Any]]:
        name = pick_first(raw, [
            "bidNtceNm", "cntrctNm", "bizNm", "orderPlanNm", "prdctClsfcNoNm", "vsslKorNm", "vsslNm",
            "corpNm", "dminsttNm", "bfSpecRgstNo", "untyCntrctNo", "cntrctNo"
        ])
        company = pick_first(raw, [
            "dminsttNm", "orderInsttNm", "ntceInsttNm", "cntrctInsttNm", "corpNm", "prtAgNm", "vsslNlty"
        ], "-")
        announcement_no = pick_first(raw, ["bidNtceNo", "bfSpecRgstNo"])
        contract_no = pick_first(raw, ["untyCntrctNo", "cntrctNo"])
        project_no = pick_first(raw, ["orderPlanUntyNo", "vsslNo", "imoNo", "mrNum"])
        region = pick_first(raw, ["prtcptPsblRgnNm", "cnstwkRgnNm", "insttLctNm", "rgnNm", "prtAgNm"])
        order_value = pick_first(raw, [
            "sumOrderAmt", "orderContrctAmt", "cntrctAmt", "fnlSucsfAmt", "sucsfbidAmt", "bssamt",
            "sumOrderDolAmt", "totAmt", "totPrdprc"
        ])
        currency = "USD" if pick_first(raw, ["sumOrderDolAmt"]) else "KRW"
        registered_at = pick_first(raw, [
            "bidNtceDate", "rgstDt", "opengDate", "cntrctCnclsDate", "cntrctDate", "vsslCnstrDt",
            "etryptDt", "pubDate"
        ])
        contract_date = pick_first(raw, ["cntrctCnclsDate", "cntrctDate"])
        delivery_date = pick_first(raw, ["dlvrTmlmtDate", "cmplnDate", "tkoffDt"])
        shipyard = pick_first(raw, ["mkerNm", "cnstrCmpnyNm", "shipyard"])
        keyword_text = " ".join([str(v) for v in raw.values() if v is not None])

        relevance = evaluate_ship_relevance(keyword_text, self.source_type)
        matched_keywords = relevance["matched_keywords"]
        ship_related = relevance["is_target"]

        if not ship_related:
            logger.info(
                "[FILTERED] collector=%s operation=%s reason=%s title=%s",
                self.name,
                operation_name,
                relevance.get("reason"),
                (name or "")[:120],
            )
            return None

        dedupe_key = announcement_no or contract_no or project_no or (name or "")
        if not dedupe_key:
            return None
        return {
            "id": str(uuid.uuid4()),
            "dedupeKey": f"{self.name}:{dedupe_key}",
            "name": name or "이름없음",
            "company": company,
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
            "sourceType": self.source_type,
            "sourceService": self.name,
            "sourceOperation": operation_name,
            "verificationStatus": "COLLECTED",
            "matchedKeywords": matched_keywords,
            "keywordText": keyword_text,
            "rawPayload": raw,
            "history": [
                {
                    "id": str(uuid.uuid4()),
                    "date": now_iso(),
                    "action": "COLLECTED",
                    "detail": f"{self.name}/{operation_name} 수집"
                }
            ],
            "sources": [
                {
                    "id": str(uuid.uuid4()),
                    "title": operation_name,
                    "publisher": self.name,
                    "url": source_url,
                    "date": registered_at or now_iso(),
                    "type": self.source_type,
                }
            ],
        }

    async def collect(self, seed_projects: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        return []

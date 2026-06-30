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

SHIP_KEYWORDS = [
    "선박", "조선", "조선소", "해양", "해군", "lng", "lpg", "fpso", "offshore", "marine",
    "ship", "shipbuilding", "dock", "dry dock", "엔진", "펌프", "밸브", "배관", "용접",
    "블록", "기자재", "프로펠러", "전장", "기관"
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


def keyword_matches(text: str) -> List[str]:
    haystack = (text or "").lower()
    matches: List[str] = []
    for keyword in SHIP_KEYWORDS:
        if keyword.lower() in haystack:
            matches.append(keyword)
    return sorted(set(matches), key=lambda x: SHIP_KEYWORDS.index(x.lower()) if x.lower() in SHIP_KEYWORDS else 999)


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
        matched_keywords = keyword_matches(keyword_text)
        ship_related = bool(matched_keywords) or self.source_type == "SHIP"
        if not ship_related:
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

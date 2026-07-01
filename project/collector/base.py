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

# 1) 해양/선박 필수 게이트 키워드
REQUIRED_MARINE_GATE_KEYWORDS = [
    "선박", "함정", "함선", "조선", "조선소", "실습선", "탐사실습선", "해양수산탐사실습선", "행정선", "청항선", "관공선",
    "경비함", "순시선", "예인선", "방제선", "지원선", "부선", "경비정", "소방정", "차도선", "함정정비",
    "3천톤", "3000톤", "3,000톤", "동해행정선", "군산실습선", "군산청항선", "우도차도선",
    "ship", "vessel", "patrol vessel", "training ship", "government vessel", "shipyard",
    "shipbuilding", "dry dock", "dock", "offshore vessel", "coast guard vessel", "crew transfer vessel", "ctv"
]

# 2) ABB 드라이브 기술영업 관점 우선 고객/발주처 문맥
ABB_BUYER_KEYWORDS: Dict[str, int] = {
    "해양경찰": 30,
    "해경": 28,
    "coast guard": 28,
    "해군": 30,
    "navy": 30,
    "조선소": 26,
    "shipyard": 26,
    "항만공사": 18,
    "항만": 14,
    "관공선": 18,
    "방위사업청": 20,
    "함정": 22,
}

# 3) ABB 관심 장비/솔루션 문맥
ABB_EQUIPMENT_KEYWORDS: Dict[str, int] = {
    "전력변환장치": 28,
    "주파수변환장치": 28,
    "드라이브": 22,
    "인버터": 20,
    "컨버터": 20,
    "vfd": 24,
    "vf drive": 24,
    "variable frequency drive": 26,
    "frequency converter": 26,
    "power converter": 24,
    "power conversion system": 26,
    "pcs": 18,
    "전기추진": 24,
    "전동 추진": 24,
    "electric propulsion": 24,
    "propulsion": 14,
    "propulsion motor": 18,
    "추진모터": 18,
    "추진전동기": 20,
    "전동기": 12,
    "모터": 10,
    "shaft generator": 16,
    "pti": 16,
    "pto": 14,
    "thruster": 16,
    "azimuth thruster": 18,
    "하이브리드": 18,
    "hybrid": 18,
    "배터리": 16,
    "battery": 16,
    "ess": 16,
    "energy storage system": 18,
}

# 4) 선종 / 플랫폼 문맥
SHIP_PLATFORM_KEYWORDS: Dict[str, int] = {
    "lng선": 18,
    "lpg선": 18,
    "컨테이너선": 16,
    "벌크선": 14,
    "탱커": 16,
    "유조선": 16,
    "가스선": 16,
    "fpso": 22,
    "flng": 22,
    "fso": 18,
    "offshore vessel": 18,
    "support vessel": 16,
    "research vessel": 16,
    "병원선": 18,
    "경비함": 22,
    "순시선": 18,
    "예인선": 16,
    "부선": 14,
    "파일럿보트": 16,
    "pilot boat": 16,
    "crew boat": 16,
    "차도선": 22,
    "실습선": 24,
    "탐사실습선": 26,
    "행정선": 24,
    "청항선": 24,
    "관공선": 22,
    "소방정": 22,
    "ctv": 22,
    "crew transfer vessel": 24,
    "해양수산탐사실습선": 30,
}

# 5) 비해양 일반 산업 제외 문맥
NON_MARINE_EXCLUDE_KEYWORDS: Dict[str, int] = {
    "도로": 16,
    "교량": 16,
    "철도": 18,
    "지하철": 18,
    "터널": 16,
    "건축": 14,
    "건물": 14,
    "청사": 12,
    "학교": 12,
    "병원": 12,
    "하수": 18,
    "상수": 18,
    "정수": 18,
    "하수처리": 22,
    "배수지": 18,
    "농업": 18,
    "축산": 16,
    "산림": 16,
    "드론": 20,
    "항공": 20,
    "자동차": 18,
    "전기차": 18,
    "엘리베이터": 18,
    "냉난방": 16,
    "보일러": 16,
    "태양광": 18,
    "풍력": 16,
    "소각": 18,
    "소방서": 14,
    "관로": 18,
    "하천": 16,
}

GENERIC_SUPPLY_EXCLUDE_KEYWORDS: Dict[str, int] = {
    "밸브": 26,
    "플랜지": 26,
    "파이프": 24,
    "배관": 22,
    "박스": 22,
    "청진기": 26,
    "의약품": 28,
    "소모품": 18,
    "압축가스": 18,
    "냉난방기": 24,
    "히트펌프": 24,
    "폭발물": 18,
    "플라스틱": 16,
}

WATCHLIST_TERMS = [
    "군산실습선", "해림2호", "우도차도선", "우도 차도선",
    "해경청3000톤", "3000톤", "3천톤", "3019함", "3020함",
    "동해행정선", "군산청항선", "소방청300t", "소방정",
    "관공선", "실습선", "탐사실습선", "행정선", "청항선",
    "순시선", "경비함", "하이브리드 전기추진", "전기추진",
    "ctv", "crew transfer vessel", "말콘"
]


TITLE_HARD_EXCLUDE_KEYWORDS = [
    "정수장", "해수담수화", "혈액투석", "의약품", "체육관", "냉난방", "학교", "하수", "상수",
    "배수개선", "아스콘", "마네킹", "농업", "엘리베이터", "병원", "도로", "교량", "터널",
    "청진기", "박스", "플랜지", "파이프", "압축가스"
]

ABB_DRIVE_KEYWORDS: Dict[str, int] = {
    "드라이브": 24, "vfd": 26, "vf drive": 26, "variable frequency drive": 28,
    "주파수변환장치": 28, "frequency converter": 28, "전력변환장치": 26, "power converter": 24,
    "컨버터": 20, "인버터": 18, "전기추진": 20, "electric propulsion": 20, "propulsion": 10
}

ABB_MOTOR_KEYWORDS: Dict[str, int] = {
    "모터": 16, "전동기": 18, "추진모터": 22, "추진전동기": 24, "propulsion motor": 22,
    "shaft generator": 16, "thruster": 16, "azimuth thruster": 18
}

ABB_POWER_KEYWORDS: Dict[str, int] = {
    "배터리": 16, "battery": 16, "ess": 16, "energy storage system": 18,
    "pcs": 18, "pto": 14, "pti": 16, "hybrid": 18, "하이브리드": 18
}

def get_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

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


def find_keyword_matches(text: str, keywords: Iterable[str]) -> List[str]:
    normalized = normalize_text(text)
    matches: List[str] = []
    for keyword in keywords:
        if keyword.lower() in normalized:
            matches.append(keyword)
    return sorted(set(matches))


def weighted_hits(text: str, weighted_keywords: Dict[str, int]) -> Tuple[int, List[str]]:
    normalized = normalize_text(text)
    score = 0
    hits: List[str] = []
    for keyword, weight in weighted_keywords.items():
        if keyword.lower() in normalized:
            score += weight
            hits.append(keyword)
    return score, hits


def unique_keep_order(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def watchlist_hits(text: str) -> List[str]:
    normalized = normalize_text(text)
    return [term for term in WATCHLIST_TERMS if term.lower() in normalized]


def classify_priority(score: int) -> str:
    if score >= 85:
        return "HOT"
    if score >= 65:
        return "WARM"
    if score >= 45:
        return "WATCH"
    return "DROP"


def evaluate_ship_relevance(title_text: str, company_text: str, full_text: str, source_type: str) -> Dict[str, Any]:
    title_norm = normalize_text(title_text)
    company_norm = normalize_text(company_text)
    full_norm = normalize_text(full_text)

    title_gate_matches = find_keyword_matches(title_norm, REQUIRED_MARINE_GATE_KEYWORDS)
    company_gate_matches = find_keyword_matches(company_norm, REQUIRED_MARINE_GATE_KEYWORDS)
    gate_matches = unique_keep_order(title_gate_matches + company_gate_matches)
    hard_title_excludes = find_keyword_matches(title_norm, TITLE_HARD_EXCLUDE_KEYWORDS)
    watch_hits = watchlist_hits(full_norm)

    ship_source_bonus = 28 if source_type == "SHIP" else 0
    exclude_score, exclude_hits = weighted_hits(full_norm, NON_MARINE_EXCLUDE_KEYWORDS)
    commodity_exclude_score, commodity_exclude_hits = weighted_hits(title_norm, GENERIC_SUPPLY_EXCLUDE_KEYWORDS)

    buyer_title_score, buyer_title_hits = weighted_hits(title_norm, ABB_BUYER_KEYWORDS)
    buyer_company_score, buyer_company_hits = weighted_hits(company_norm, ABB_BUYER_KEYWORDS)
    buyer_full_score, buyer_full_hits = weighted_hits(full_norm, ABB_BUYER_KEYWORDS)

    equip_title_score, equip_title_hits = weighted_hits(title_norm, ABB_EQUIPMENT_KEYWORDS)
    equip_full_score, equip_full_hits = weighted_hits(full_norm, ABB_EQUIPMENT_KEYWORDS)

    platform_title_score, platform_title_hits = weighted_hits(title_norm, SHIP_PLATFORM_KEYWORDS)
    platform_full_score, platform_full_hits = weighted_hits(full_norm, SHIP_PLATFORM_KEYWORDS)

    drive_title_score, drive_title_hits = weighted_hits(title_norm, ABB_DRIVE_KEYWORDS)
    drive_full_score, drive_full_hits = weighted_hits(full_norm, ABB_DRIVE_KEYWORDS)
    motor_title_score, motor_title_hits = weighted_hits(title_norm, ABB_MOTOR_KEYWORDS)
    motor_full_score, motor_full_hits = weighted_hits(full_norm, ABB_MOTOR_KEYWORDS)
    power_title_score, power_title_hits = weighted_hits(title_norm, ABB_POWER_KEYWORDS)
    power_full_score, power_full_hits = weighted_hits(full_norm, ABB_POWER_KEYWORDS)

    has_equipment = bool(equip_title_hits or equip_full_hits or drive_title_hits or drive_full_hits or motor_title_hits or motor_full_hits or power_title_hits or power_full_hits)
    has_buyer = bool(buyer_title_hits or buyer_company_hits or buyer_full_hits)
    has_platform = bool(platform_title_hits or platform_full_hits or title_gate_matches or watch_hits or source_type == "SHIP")
    buyer_only = has_buyer and not has_platform and not has_equipment
    generic_supply_only = bool(commodity_exclude_hits) and not has_platform and source_type != "SHIP" and not watch_hits

    if buyer_only:
        return {
            "is_target": False,
            "score": 0,
            "priority": "DROP",
            "matched_keywords": [],
            "reason": "buyer-only procurement without ship/platform context",
            "detail": {
                "gateKeywords": gate_matches,
                "buyerKeywords": unique_keep_order(buyer_title_hits + buyer_company_hits + buyer_full_hits),
                "equipmentKeywords": unique_keep_order(equip_title_hits + equip_full_hits),
                "platformKeywords": unique_keep_order(platform_title_hits + platform_full_hits + watch_hits),
                "watchlistHits": watch_hits,
                "excludeKeywords": unique_keep_order(exclude_hits + commodity_exclude_hits + hard_title_excludes),
                "componentScores": {"driveScore": 0, "motorScore": 0, "powerScore": 0},
            },
        }

    if generic_supply_only:
        return {
            "is_target": False,
            "score": 0,
            "priority": "DROP",
            "matched_keywords": [],
            "reason": "generic commodity procurement without vessel context",
            "detail": {
                "gateKeywords": gate_matches,
                "buyerKeywords": unique_keep_order(buyer_title_hits + buyer_company_hits + buyer_full_hits),
                "equipmentKeywords": unique_keep_order(equip_title_hits + equip_full_hits),
                "platformKeywords": unique_keep_order(platform_title_hits + platform_full_hits + watch_hits),
                "watchlistHits": watch_hits,
                "excludeKeywords": unique_keep_order(exclude_hits + commodity_exclude_hits + hard_title_excludes),
                "componentScores": {"driveScore": 0, "motorScore": 0, "powerScore": 0},
            },
        }

    if hard_title_excludes and source_type != "SHIP" and not has_platform:
        return {
            "is_target": False,
            "score": 0,
            "priority": "DROP",
            "matched_keywords": [],
            "reason": "title hard-excluded as non-marine",
            "detail": {
                "gateKeywords": gate_matches,
                "buyerKeywords": unique_keep_order(buyer_title_hits + buyer_company_hits + buyer_full_hits),
                "equipmentKeywords": unique_keep_order(equip_title_hits + equip_full_hits),
                "platformKeywords": unique_keep_order(platform_title_hits + platform_full_hits + watch_hits),
                "watchlistHits": watch_hits,
                "excludeKeywords": unique_keep_order(exclude_hits + commodity_exclude_hits + hard_title_excludes),
                "componentScores": {"driveScore": 0, "motorScore": 0, "powerScore": 0},
            },
        }

    if source_type != "SHIP" and not has_platform:
        return {
            "is_target": False,
            "score": 0,
            "priority": "DROP",
            "matched_keywords": [],
            "reason": "ship/platform keyword missing in title/company",
            "detail": {
                "gateKeywords": gate_matches,
                "buyerKeywords": unique_keep_order(buyer_title_hits + buyer_company_hits + buyer_full_hits),
                "equipmentKeywords": unique_keep_order(equip_title_hits + equip_full_hits),
                "platformKeywords": unique_keep_order(platform_title_hits + platform_full_hits + watch_hits),
                "watchlistHits": watch_hits,
                "excludeKeywords": unique_keep_order(exclude_hits + commodity_exclude_hits),
                "componentScores": {"driveScore": 0, "motorScore": 0, "powerScore": 0},
            },
        }

    score = ship_source_bonus
    score += platform_title_score * 3 + max(0, platform_full_score - platform_title_score)
    score += buyer_title_score + buyer_company_score + max(0, buyer_full_score - buyer_title_score - buyer_company_score)
    score += equip_title_score * 2 + max(0, equip_full_score - equip_title_score)
    if watch_hits:
        score += 60
    if has_platform and has_equipment:
        score += 18
    if has_platform and has_buyer:
        score += 12
    if has_buyer and has_equipment:
        score += 8

    if exclude_hits:
        score -= int(exclude_score * 0.35)
    if commodity_exclude_hits and not has_equipment and not watch_hits:
        score -= commodity_exclude_score
    elif commodity_exclude_hits and not watch_hits:
        score -= int(commodity_exclude_score * 0.5)

    drive_score = drive_title_score * 2 + max(0, drive_full_score - drive_title_score)
    motor_score = motor_title_score * 2 + max(0, motor_full_score - motor_title_score)
    power_score = power_title_score * 2 + max(0, power_full_score - power_title_score)
    if has_platform:
        drive_score += 8 if drive_score else 0
        motor_score += 8 if motor_score else 0
        power_score += 6 if power_score else 0

    priority = classify_priority(score)
    matched_keywords = unique_keep_order(
        gate_matches + watch_hits + platform_title_hits + platform_full_hits + buyer_title_hits + buyer_company_hits + buyer_full_hits + equip_title_hits + equip_full_hits
    )

    detail = {
        "gateKeywords": gate_matches,
        "buyerKeywords": unique_keep_order(buyer_title_hits + buyer_company_hits + buyer_full_hits),
        "equipmentKeywords": unique_keep_order(equip_title_hits + equip_full_hits),
        "platformKeywords": unique_keep_order(platform_title_hits + platform_full_hits + title_gate_matches + watch_hits),
        "watchlistHits": watch_hits,
        "excludeKeywords": unique_keep_order(exclude_hits + commodity_exclude_hits + hard_title_excludes),
        "componentScores": {"driveScore": drive_score, "motorScore": motor_score, "powerScore": power_score},
    }

    if priority == "DROP":
        return {
            "is_target": False,
            "score": score,
            "priority": priority,
            "matched_keywords": matched_keywords,
            "reason": "score below ABB marine-drive threshold",
            "detail": detail,
        }

    return {
        "is_target": True,
        "score": score,
        "priority": priority,
        "matched_keywords": matched_keywords,
        "reason": "ABB marine-drive scoring passed",
        "detail": detail,
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
        self.service_key = self.resolve_service_key()

    def resolve_service_key(self) -> str:
        candidates = [
            self.key_env_name,
            "DATA_GO_KR_API_KEY",
            "PUBLIC_DATA_API_KEY",
            "SHIP_API_KEY",
        ]
        for env_name in candidates:
            value = os.getenv(env_name, "").strip()
            if value:
                return value
        return ""

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
        max_pages = get_env_int("MAX_PAGES_PER_OPERATION", 3)
        max_items = get_env_int("MAX_ITEMS_PER_OPERATION", 300)
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
            if max_pages and page_no >= max_pages:
                break
            if max_items and len(all_items) >= max_items:
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
            "sumOrderDolAmt", "totAmt", "totPrdprc", "presmptPrce", "asignBdgtAmt", "presmptPrce"
        ])
        currency = "USD" if pick_first(raw, ["sumOrderDolAmt"]) else "KRW"
        registered_at = pick_first(raw, [
            "bidNtceDate", "rgstDt", "opengDate", "cntrctCnclsDate", "cntrctDate", "vsslCnstrDt",
            "etryptDt", "pubDate"
        ])
        contract_date = pick_first(raw, ["cntrctCnclsDate", "cntrctDate"])
        delivery_date = pick_first(raw, ["dlvrTmlmtDt", "dlvrTmlmtDate", "cmplnDate", "tkoffDt"])
        shipyard = pick_first(raw, ["mkerNm", "cnstrCmpnyNm", "shipyard"])
        keyword_text = " ".join([str(v) for v in raw.values() if v is not None])

        relevance = evaluate_ship_relevance(
            title_text=name or "",
            company_text=company or "",
            full_text=keyword_text,
            source_type=self.source_type,
        )

        if not relevance["is_target"]:
            logger.info(
                "[FILTERED] collector=%s operation=%s reason=%s score=%s title=%s",
                self.name,
                operation_name,
                relevance.get("reason"),
                relevance.get("score"),
                (name or "")[:120],
            )
            return None

        dedupe_key = announcement_no or contract_no or project_no or (name or "")
        if not dedupe_key:
            return None

        abb_meta = {
            "score": relevance["score"],
            "priority": relevance["priority"],
            "reason": relevance["reason"],
            "detail": relevance["detail"],
        }
        spec_doc_urls = [
            raw.get("specDocFileUrl1"),
            raw.get("specDocFileUrl2"),
            raw.get("specDocFileUrl3"),
            raw.get("specDocFileUrl4"),
            raw.get("specDocFileUrl5"),
        ]
        spec_doc_urls = [url for url in spec_doc_urls if url]
        raw_payload = dict(raw)
        raw_payload["_abbTargeting"] = abb_meta
        raw_payload["_displayHint"] = {"score": relevance["score"], "priority": relevance["priority"], "matchedKeywords": relevance["matched_keywords"]}
        raw_payload["_attachments"] = {"specDocUrls": spec_doc_urls}
        raw_payload["_verified"] = {
            "status": "UNVERIFIED",
            "reason": "collector ingestion only",
            "evidenceUrls": spec_doc_urls[:],
        }

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
            "verificationStatus": relevance["priority"],
            "matchedKeywords": relevance["matched_keywords"],
            "keywordText": keyword_text,
            "rawPayload": raw_payload,
            "history": [
                {
                    "id": str(uuid.uuid4()),
                    "date": now_iso(),
                    "action": "COLLECTED",
                    "detail": f"{self.name}/{operation_name} 수집 | ABB score={relevance['score']} priority={relevance['priority']}"
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

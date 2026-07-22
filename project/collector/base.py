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

logger = logging.getLogger("sdi.collector")

VESSEL_PLATFORM_TERMS = [
    "선박", "함정", "함선", "관공선", "특수선", "경비함", "경비정", "순시선", "구조정", "연안구조정",
    "소방선", "소방정", "국가어업지도선", "어업지도선", "수산지도선", "지도선", "행정선", "청항선",
    "방제선", "예인선", "지원선", "병원선", "연구선", "시험선", "조사선", "측량선", "탐사선", "실습선",
    "차도선", "도항선", "카페리", "여객선", "연안여객선", "쾌속선", "유람선", "페리", "바지선", "부선",
    "준설선", "작업선", "해상풍력지원선", "풍력지원선", "승무원운송선", "크루보트", "ctv", "sov",
    "ship", "vessel", "ferry", "patrol boat", "patrol vessel", "government vessel", "coast guard vessel",
    "fire boat", "research vessel", "training ship", "crew transfer vessel", "service operation vessel",
]

MARINE_INFRA_TERMS = [
    "해상풍력", "부유식풍력", "해양플랜트", "해양에너지", "조력발전", "파력발전", "항만전력", "육상전원공급",
    "육상전원", "amp 시스템", "shore power", "cold ironing", "항만하역", "전기추진시스템", "선박전력시스템",
]

MARINE_KEYWORDS = [
    *VESSEL_PLATFORM_TERMS,
    "조선", "조선소", "선박건조", "함정건조", "선박개조", "함정정비", "도크", "선급", "한국선급",
    "shipyard", "shipbuilding", "dry dock", "marine propulsion", "naval architecture",
]

WATCHLIST_TERMS = [
    "대체건조", "신조선", "선박 현대화", "친환경선박", "하이브리드선박", "하이브리드 추진", "전기추진",
    "배터리 추진", "축발전기", "dc grid", "마이크로그리드", "3000톤", "3,000톤", "500톤급", "540톤",
    "장비선정위원회", "기자재선정위원회", "기술제안서", "기본설계", "실시설계", "상세설계",
]

BUYER_WEIGHTS: Dict[str, int] = {
    "해양경찰": 18, "해경": 16, "coast guard": 16, "소방청": 15, "소방본부": 15,
    "해양수산부": 14, "어업관리단": 14, "항만공사": 12, "해양환경공단": 12,
    "지방자치단체": 8, "시청": 7, "도청": 7, "군청": 7, "수산과학원": 10, "대학교": 8,
}

EQUIPMENT_WEIGHTS: Dict[str, int] = {
    "하이브리드": 18, "hybrid": 18, "전기추진": 18, "electric propulsion": 18,
    "인버터": 14, "inverter": 14, "컨버터": 14, "converter": 14, "드라이브": 14, "vfd": 14, "vsd": 14,
    "dc/dc": 16, "dc-dc": 16, "dc/ac": 16, "dc-ac": 16, "ac/dc": 16, "ac-dc": 16,
    "afe": 12, "active front end": 12, "정류기": 10, "회생제동": 10, "제동저항": 8,
    "배터리": 12, "battery": 12, "ess": 12, "bess": 12, "pcs": 12, "에너지저장장치": 12,
    "축발전기": 12, "shaft generator": 12, "pti": 10, "pto": 10, "dc grid": 14, "dc 배전": 14,
    "추진모터": 12, "propulsion motor": 12, "전동기": 8, "발전기": 8, "diesel generator": 10,
    "genset": 10, "pms": 10, "ems": 10, "전력관리시스템": 10, "배전반": 7, "switchboard": 7,
    "바우스러스터": 8, "bow thruster": 8, "아지무스 스러스터": 8, "waterjet": 6, "워터젯": 6,
    "소방펌프": 8, "냉각펌프": 6, "펌프": 4, "윈치": 4, "크레인": 4, "압축기": 4, "컴프레서": 4,
}

SOLUTION_GROUPS: Dict[str, List[str]] = {
    "가변속 드라이브": ["vfd", "vsd", "드라이브", "frequency converter", "주파수변환기", "가변속"],
    "전력변환": ["인버터", "inverter", "컨버터", "converter", "dc/dc", "dc-dc", "dc/ac", "dc-ac", "ac/dc", "ac-dc", "afe", "정류기"],
    "전기·하이브리드 추진": ["전기추진", "하이브리드", "electric propulsion", "propulsion motor", "추진모터", "pti", "pto"],
    "발전·전력관리": ["발전기", "genset", "diesel generator", "축발전기", "pms", "ems", "배전반", "switchboard", "dc grid"],
    "배터리·ESS": ["배터리", "battery", "ess", "bess", "pcs", "에너지저장장치"],
    "보조기기 구동": ["펌프", "fan", "팬", "압축기", "컴프레서", "윈치", "크레인", "thruster", "스러스터", "waterjet", "워터젯"],
}

SHIPYARD_TERMS = [
    "대선조선", "HJ중공업", "에이치제이중공업", "한진중공업", "강남조선", "동성조선", "극동조선",
    "삼강엠앤티", "SK오션플랜트", "대한조선", "케이조선", "HSG성동조선", "금하네이벌텍",
    "동남중공업", "삼원중공업", "코리아월드써비스", "신진조선", "세진중공업", "조선소", "shipyard",
]

BUILD_TERMS = [
    "선박건조", "함정건조", "건조사업", "건조공사", "대체건조", "신조", "신조선", "제작구매", "제조구매",
    "선박개조", "함정개조", "성능개량", "현대화", "수명연장", "기본설계", "개념설계", "실시설계", "상세설계",
    "설계용역", "장비선정위원회", "기자재선정위원회", "type approval", "형식승인",
]

NOISE_TERMS = [
    "정수장", "해수담수화", "혈액투석", "의약품", "학교 체육관", "냉난방", "하수관", "상수관",
    "배수개선", "아스콘", "마네킹", "농업", "교량", "도로", "터널", "청진기", "압축가스", "방탄방패",
    "방탄헬멧", "사무용가구", "급식", "학교시설", "태양광 인버터", "승강기", "건물자동제어",
]

TITLE_FIELDS = [
    "bidNtceNm", "cntrctNm", "orderPlanNm", "bizNm", "orderBizNm", "bfSpecBizNm", "prcrmntReqNm",
    "prdctClsfcNoNm", "rprsntPrdctClsfcNoNm", "referNm", "bsnsNm", "bidNm",
    "title", "subject", "ntceNm", "vsslNm", "shipNm", "VSSL_NM", "newsTitle",
]
PUBLISHER_FIELDS = [
    "dminsttNm", "orderInsttNm", "cntrctInsttNm", "dmndInsttNm", "bidDminsttNm", "bfSpecDminsttNm",
    "bfSpecNtceInsttNm", "ntceInsttNm", "pubPrcrmntLrgClsfcNm",
    "agency", "publisher", "insttNm",
]
ANNOUNCEMENT_FIELDS = ["bidNtceNo", "ntceNo", "bidPbancNo", "announcementNo"]
CONTRACT_FIELDS = ["cntrctNo", "contractNo", "untyCntrctNo"]
PROJECT_FIELDS = ["bfSpecRgstNo", "prcrmntReqNo", "orderPlanUntyNo", "orderPlanNo", "orderPlanSno", "bsnsNo", "projectNo", "refNo"]
REGION_FIELDS = ["prtcptPsblRgnNm", "rgnNm", "region", "area", "sidoNm"]
VALUE_FIELDS = ["presmptPrce", "asignBdgtAmt", "rprsntAmt", "thtmBdgtAmt", "totSrvceBdgtAmt", "totCnstwkScleAmt", "orderContrctAmt", "totPrdprc", "cntrctAmt", "sumOrderAmt", "fnlSucsfAmt", "orderValue"]
REGISTERED_FIELDS = ["bidNtceDt", "rgstDt", "rcptDt", "nticeDt", "ntceDt", "createdAt", "registeredAt", "opengDt", "orderYear", "pubDate"]
CONTRACT_DATE_FIELDS = ["cntrctCnclsDate", "contractDate"]
DELIVERY_FIELDS = ["dlvrDate", "dlvrTmlmtDt", "rprsntDedtDate", "deliveryDate", "thtmCmpltnDate", "deliveryDueDate"]
SHIPYARD_FIELDS = ["cntrctCorpNm", "sucsfbidCorpNm", "shipyard", "builder"]
DESCRIPTION_FIELDS = [
    "description", "summary", "content", "body", "newsSummary", "specCntnts", "rmrkCntnts", "usgCntnts",
    "cnstwkPrdCntnts", "rprsntSpecDtlsCntnts", "prdctDtlList", "opninCntnts",
]
LINK_FIELDS = [
    "bidNtceDtlUrl", "bidNtceUrl", "cntrctDtlInfoUrl", "cntrctInfoUrl", "orderPlanUrl", "prespecUrl",
    "bfSpecDtlUrl", "prcrmntReqInfoUrl", "ntceDtlUrl", "detailUrl", "originallink", "link", "url",
]

ATTACHMENT_URL_FIELDS = [
    *(f"specDocFileUrl{index}" for index in range(1, 6)),
    *(f"specDocOpninFileUrl{index}" for index in range(1, 6)),
    *(f"atchFileUrl{index}" for index in range(1, 11)),
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


def matched_terms(source: str, terms: Iterable[str]) -> List[str]:
    """Return normalized unique matches without repeatedly normalizing the source text."""
    result: List[str] = []
    seen: set[str] = set()
    for term in terms:
        clean_term = clean_text(term)
        normalized_term = normalized(clean_term)
        if normalized_term and normalized_term in source and normalized_term not in seen:
            result.append(clean_term)
            seen.add(normalized_term)
    return result


def searchable_item_text(item: Dict[str, Any], limit: int = 18000) -> str:
    """Flatten meaningful scalar API fields so equipment hidden outside the title is searchable."""
    preferred = [
        *TITLE_FIELDS, *PUBLISHER_FIELDS, *SHIPYARD_FIELDS, *DESCRIPTION_FIELDS,
        "specItemCntnts1", "specItemCntnts2", "specItemCntnts3", "specItemCntnts4", "specItemCntnts5",
        "prdctClsfcNoNm", "rprsntPrdctClsfcNoNm", "krnPrdctNm", "engRprsntPrdctNm",
    ]
    values: List[str] = []
    seen_fields: set[str] = set()
    for field in preferred:
        value = item.get(field)
        if value not in (None, ""):
            values.append(clean_text(value))
            seen_fields.add(field)
    for field, value in item.items():
        if field in seen_fields or not isinstance(value, (str, int, float)):
            continue
        field_name = field.lower()
        if any(token in field_name for token in ("nm", "name", "cntnt", "spec", "title", "desc", "rmrk", "dtl")):
            values.append(clean_text(value))
        if sum(len(part) for part in values) >= limit:
            break
    return " ".join(values)[:limit]


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
    if any(term in text for term in ["prcrmntreq", "조달요청"]):
        return "REQUEST"
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
    key_param_name = "ServiceKey"
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
                trust_env=False,
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

    def is_configured(self) -> bool:
        if self.operations:
            return bool(self.api_key())
        feed_env_name = getattr(self, "feed_env_name", "")
        if feed_env_name:
            return bool(os.getenv(feed_env_name, "").strip())
        return True

    def evaluate_relevance(self, text: str) -> Dict[str, Any]:
        source = normalized(text)
        vessel_platform = matched_terms(source, VESSEL_PLATFORM_TERMS)
        marine_infra = matched_terms(source, MARINE_INFRA_TERMS)
        marine_context = matched_terms(source, MARINE_KEYWORDS)
        hard_noise = matched_terms(source, NOISE_TERMS)
        if is_cctv_noise(source) or (hard_noise and not vessel_platform and not marine_infra and not marine_context):
            return {
                "score": 0, "priority": "DROP", "matched_keywords": [], "shipyard_keywords": [],
                "build_keywords": [], "platform_keywords": [], "watchlist_hits": [], "buyer_keywords": [],
                "equipment_keywords": [], "exclude_keywords": ["noise"], "drive_score": 0, "motor_score": 0,
                "power_score": 0, "opportunity_class": "P3", "solution_areas": [], "sales_reasons": [],
                "risk_flags": ["비선박 일반 구매로 판정"], "recommended_action": "기본 목록에서 제외 후 필요 시 수동 검토",
            }

        platform = sorted(set(vessel_platform + marine_infra + marine_context))
        watchlist = matched_terms(source, [*WATCHLIST_TERMS, *env_terms("SHIP_WATCHLIST_TERMS")])
        shipyards = matched_terms(source, [*SHIPYARD_TERMS, *env_terms("SHIPYARD_WATCHLIST")])
        builds = matched_terms(source, [*BUILD_TERMS, *env_terms("VESSEL_BUILD_WATCHLIST")])
        buyers = matched_terms(source, BUYER_WEIGHTS)
        equipment = matched_terms(source, EQUIPMENT_WEIGHTS)
        solution_areas = [label for label, terms in SOLUTION_GROUPS.items() if matched_terms(source, terms)]
        has_electric = any(term in source for term in ["전기추진", "하이브리드", "hybrid", "battery", "배터리", "ess", "dc grid"])
        has_drive = any(term in source for term in ["인버터", "inverter", "컨버터", "converter", "드라이브", "drive", "vfd", "vsd", "afe", "dc/dc", "dc-dc", "dc/ac", "ac/dc"])
        has_motor = any(term in source for term in ["추진", "모터", "motor", "축발전기", "shaft generator"])
        has_power = any(term in source for term in ["배터리", "battery", "ess", "bess", "dc grid", "배전", "switchboard", "pcs", "발전기", "genset"])

        relevance = min(40, len(vessel_platform) * 7 + len(marine_infra) * 6 + len(builds) * 5 + len(watchlist) * 3)
        solution_fit = min(38, sum(EQUIPMENT_WEIGHTS.get(term.lower(), EQUIPMENT_WEIGHTS.get(term, 4)) for term in equipment))
        buyer_fit = min(15, sum(BUYER_WEIGHTS.get(term.lower(), BUYER_WEIGHTS.get(term, 4)) for term in buyers))
        early_bonus = 10 if (vessel_platform or marine_infra) and builds else 0
        score = min(100, relevance + solution_fit + buyer_fit + early_bonus + (5 if shipyards and builds else 0))
        if not platform and not builds and not watchlist and not shipyards and not buyers:
            score = 0
        # Generic build terms or buyer names alone are insufficient; they stay out unless a marine anchor exists.
        is_marine_candidate = bool(vessel_platform or marine_infra or marine_context or watchlist or shipyards)
        if not is_marine_candidate:
            score = 0
        priority = "HOT" if score >= 78 else "WARM" if score >= 58 else "WATCH" if is_marine_candidate else "DROP"
        drive_score = min(100, (55 if has_electric else 10) + (25 if has_drive else 0) + len(equipment) * 3)
        motor_score = min(100, (50 if has_electric else 8) + (30 if has_motor else 0) + len(platform) * 2)
        power_score = min(100, (48 if has_power else 5) + (20 if has_electric else 0) + len(equipment) * 2)
        matched = sorted(set(platform + watchlist + equipment))
        opportunity_class = "P0" if equipment and is_marine_candidate else "P1" if builds and is_marine_candidate else "P2" if is_marine_candidate else "P3"
        sales_reasons: List[str] = []
        if solution_areas:
            sales_reasons.append(f"장비 적용 가능 영역: {', '.join(solution_areas[:3])}")
        if builds:
            sales_reasons.append(f"설계·건조 신호 확인: {', '.join(builds[:3])}")
        if buyers:
            sales_reasons.append(f"관공선 핵심 발주기관 문맥: {', '.join(buyers[:2])}")
        if not equipment and is_marine_candidate:
            sales_reasons.append("장비명이 확정되기 전 단계로 사양 반영 가능성을 조기 추적해야 합니다.")
        risk_flags: List[str] = []
        if hard_noise:
            risk_flags.append(f"혼합 문맥 포함: {', '.join(hard_noise[:2])}")
        if not equipment:
            risk_flags.append("직접 장비명 미확인")
        if not builds:
            risk_flags.append("신조·개조 일정 미확인")
        recommended_action = (
            "규격서에서 전압·용량·추진계통을 확인하고 설계사/조선소 접점을 확보"
            if opportunity_class == "P0" else
            "기본·실시설계 발주처와 설계사를 확인해 ABB 사양 반영 시점을 선점"
            if opportunity_class == "P1" else
            "예산·발주계획·대체건조 여부를 주기적으로 재확인"
            if opportunity_class == "P2" else
            "수동 검토"
        )
        return {
            "score": score,
            "priority": priority,
            "matched_keywords": matched,
            "shipyard_keywords": sorted(set(shipyards)),
            "build_keywords": sorted(set(builds)),
            "platform_keywords": sorted(set(platform)),
            "watchlist_hits": sorted(set(watchlist)),
            "buyer_keywords": sorted(set(buyers)),
            "equipment_keywords": sorted(set(equipment)),
            "exclude_keywords": [],
            "drive_score": drive_score,
            "motor_score": motor_score,
            "power_score": power_score,
            "opportunity_class": opportunity_class,
            "solution_areas": solution_areas,
            "sales_reasons": sales_reasons,
            "risk_flags": risk_flags,
            "recommended_action": recommended_action,
        }

    async def _http_get(self, url: str, params: Dict[str, Any]) -> httpx.Response:
        last_error: Optional[Exception] = None
        for attempt in range(self.retry_count + 1):
            try:
                response = await self.http_client().get(url, params=params)
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
        combined = searchable_item_text(item)
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
        identifiers = {
            "announcementNo": announcement_no or None,
            "contractNo": contract_no or None,
            "projectNo": project_no or None,
            "prespecNo": clean_text(item.get("bfSpecRgstNo")) or None,
            "procurementRequestNo": clean_text(item.get("prcrmntReqNo")) or None,
            "orderPlanNo": clean_text(item.get("orderPlanUntyNo") or item.get("orderPlanNo")) or None,
        }
        attachment_rows: List[Dict[str, Any]] = []
        for index, field in enumerate(ATTACHMENT_URL_FIELDS, start=1):
            attachment_url = clean_text(item.get(field))
            if not attachment_url.startswith(("https://", "http://")):
                continue
            attachment_rows.append({
                "field": field,
                "url": attachment_url,
                "title": f"공식 첨부문서 {len(attachment_rows) + 1}",
            })
        raw_payload = {
            **item,
            "_abbTargeting": {
                "score": relevance["score"],
                "priority": relevance["priority"],
                "detail": {
                    "gateKeywords": relevance["platform_keywords"],
                    "buyerKeywords": relevance["buyer_keywords"],
                    "equipmentKeywords": relevance["equipment_keywords"],
                    "platformKeywords": relevance["platform_keywords"],
                    "shipyardKeywords": relevance["shipyard_keywords"],
                    "buildKeywords": relevance["build_keywords"],
                    "watchlistHits": relevance["watchlist_hits"],
                    "excludeKeywords": relevance["exclude_keywords"],
                    "componentScores": {
                        "driveScore": relevance["drive_score"],
                        "motorScore": relevance["motor_score"],
                        "powerScore": relevance["power_score"],
                    },
                },
            },
            "_salesIntelligence": {
                "opportunityClass": relevance["opportunity_class"],
                "solutionAreas": relevance["solution_areas"],
                "salesReasons": relevance["sales_reasons"],
                "riskFlags": relevance["risk_flags"],
                "recommendedAction": relevance["recommended_action"],
                "searchableTextLength": len(combined),
            },
            "_evidence": {
                "identifiers": identifiers,
                "directOfficialLink": is_direct_link,
                "attachmentCount": len(attachment_rows),
                "searchHint": next((value for value in identifiers.values() if value), title),
            },
            "_collection": {"collectedAt": collected_at, "collector": self.name, "operation": operation_name},
        }
        identifier = hashlib.sha1(dedupe_key.encode("utf-8")).hexdigest()[:16].upper()
        source_id = hashlib.sha1(f"{record_url}|{title}".encode("utf-8")).hexdigest()[:16]
        history_id = hashlib.sha1(f"{dedupe_key}|{operation_name}|{collected_at[:10]}".encode("utf-8")).hexdigest()[:16]
        sources = [{
            "id": f"S-{source_id}",
            "title": title,
            "publisher": publisher or self.name,
            "url": record_url,
            "apiUrl": source_url,
            "isDirectLink": is_direct_link,
            "date": registered_at or collected_at[:10],
            "type": self.source_type,
            "evidenceKind": "OFFICIAL" if self.source_type in {"G2B", "PUBLIC_STD", "PUBLIC_NOTICE", "SHIP"} else "DISCOVERY",
            "evidenceMode": "DIRECT" if is_direct_link else "API_ONLY",
            "recordIdentifiers": identifiers,
            "operation": operation_name,
        }]
        for attachment in attachment_rows:
            attachment_id = hashlib.sha1(attachment["url"].encode("utf-8")).hexdigest()[:16]
            sources.append({
                "id": f"DOC-{attachment_id}",
                "title": attachment["title"],
                "publisher": publisher or "나라장터",
                "url": attachment["url"],
                "apiUrl": source_url,
                "isDirectLink": True,
                "date": registered_at or collected_at[:10],
                "type": "G2B_DOCUMENT",
                "evidenceKind": "OFFICIAL_ATTACHMENT",
                "field": attachment["field"],
            })
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
                "detail": f"{self.name}/{operation_name} 수집 · ABB {relevance['score']}점 {relevance['priority']}",
            }],
            "sources": sources,
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

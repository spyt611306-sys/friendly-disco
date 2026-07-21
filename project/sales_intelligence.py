# -*- coding: utf-8 -*-
"""ABB Marine Drive 영업기회 분류 엔진.

수요기관명이나 '건조' 한 단어만으로 후보가 되는 것을 막고, 먼저 실제 선박
문맥을 확인한 뒤 드라이브 솔루션 적합도와 프로젝트 선점 시점을 평가한다.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, List


CLASSIFICATION_VERSION = 2

VESSEL_TERMS = [
    "선박", "관공선", "함정", "경비함", "경비정", "순시선", "고속정", "구조정", "소방정",
    "어업지도선", "국가어업지도선", "지도선", "병원선", "실습선", "연구선", "탐사선", "시험선",
    "차도선", "여객선", "카페리", "연안여객선", "청항선", "행정선", "방제선", "예인선", "지원선",
    "작업선", "준설선", "해상풍력지원선", "해상풍력 설치선", "crew transfer vessel", "service operation vessel",
    "offshore support vessel", "coast guard vessel", "patrol vessel", "government vessel", "research vessel",
    "training ship", "ferry", "shipbuilding", "newbuilding", "new build", "vessel", "ship", "ctv", "sov",
]

TARGET_PLATFORM_TERMS = [
    "하이브리드 선박", "하이브리드 추진", "전기추진선", "전기추진 선박", "친환경선박", "친환경 선박",
    "3000톤", "3,000톤", "3000t", "3천톤", "대형경비함", "어업지도선", "국가어업지도선",
    "경비함", "경비정", "소방정", "차도선", "여객선", "카페리", "ctv", "crew transfer vessel",
    "해상풍력지원선", "해상풍력 지원선", "service operation vessel", "sov",
]

MARINE_INFRA_TERMS = [
    "항만 육상전원", "선박 육상전원", "육상전원공급설비", "amp 설비", "shore power", "cold ironing",
    "항만 크레인", "부두 크레인", "sts 크레인", "rtg 크레인", "해상변전소", "offshore substation",
    "해상풍력", "offshore wind", "해양플랜트", "offshore platform",
]

BUYER_TERMS = [
    "해양경찰청", "해양경찰", "해경", "동해어업관리단", "서해어업관리단", "남해어업관리단", "어업관리단",
    "소방청", "소방본부", "해양수산부", "지방해양수산청", "항만공사", "해양환경공단",
    "국립수산과학원", "수산과학원", "해양대학교", "수산대학교", "지방자치단체", "도청", "시청", "군청",
]

SHIPYARD_TERMS = [
    "HD현대중공업", "현대중공업", "한화오션", "삼성중공업", "HJ중공업", "에이치제이중공업", "한진중공업",
    "대선조선", "강남조선", "동성조선", "극동조선", "SK오션플랜트", "삼강엠앤티", "대한조선",
    "케이조선", "HSG성동조선", "금하네이벌텍", "동남중공업", "삼원중공업", "코리아월드써비스",
    "신진조선", "세진중공업", "조선소", "shipyard",
]

DIRECT_SOLUTION_TERMS = [
    "vfd", "variable frequency drive", "variable speed drive", "frequency converter", "propulsion drive", "thruster drive", "marine drive",
    "inverter", "converter", "drive system", "acs880", "acs6080", "afe", "active front end",
    "인버터", "컨버터", "주파수변환기", "주파수 변환기", "가변주파수", "가변속 드라이브", "가변속제어장치", "드라이브 시스템", "추진 드라이브",
    "추진 인버터", "추진 컨버터", "전기추진", "하이브리드 선박", "하이브리드 추진", "하이브리드 시스템",
    "hybrid vessel", "hybrid propulsion", "dc grid", "dc 배전", "직류배전",
    "축발전기", "shaft generator", "pti", "pto", "추진모터", "propulsion motor", "전동기", "전기모터",
    "ess", "energy storage system", "배터리 추진", "battery propulsion", "pcs", "power conversion system",
    "전력변환장치", "회생제동", "brake chopper", "제동저항", "waterjet drive", "워터젯 드라이브",
]

POWER_SYSTEM_TERMS = [
    "배전반", "switchboard", "전력관리시스템", "power management system", "pms", "발전기", "generator",
    "육상전원", "shore connection", "shore power", "변압기", "transformer", "전력계통", "power system",
]

NEWBUILD_TERMS = [
    "신조", "신조선", "건조", "건조사업", "선박 건조", "함정 건조", "대체건조", "제작구매", "제조구매",
    "newbuilding", "new build", "shipbuilding",
]

RETROFIT_TERMS = [
    "개조", "성능개량", "현대화", "수명연장", "대체설치", "교체공사", "노후 추진", "retrofit", "conversion",
    "upgrade", "modernization", "repowering", "re-powering",
]

EARLY_SIGNAL_TERMS = [
    "기본설계", "개념설계", "상세설계", "실시설계", "설계용역", "설계 공모", "타당성조사", "타당성 검토",
    "예산편성", "예산 반영", "중기재정", "건조계획", "도입계획", "발주계획", "사전규격", "규격서",
    "제안요청서", "장비선정위원회", "장비 선정위원회", "기술위원회", "사양검토", "사양 협의", "기본계획",
    "연구용역", "착수보고", "설계심의", "투자심사", "예비타당성", "feasibility", "concept design",
    "basic design", "front end engineering", "feed study",
]

NON_SALES_EQUIPMENT_TERMS = [
    "계측기", "측정기", "센서", "유량계", "압력계", "온도계", "무전기", "통신장비", "위성통신",
    "레이더", "ais", "항해장비", "전자해도", "cctv", "감시카메라", "영상감시장치", "소화기", "소방호스",
    "구명조끼", "구명정", "방탄방패", "방탄복", "총기", "탄약", "피복", "침구", "식자재", "윤활유",
    "도료", "페인트", "노트북", "컴퓨터", "프린터", "복합기", "서버", "소프트웨어 유지보수",
]

HARD_NOISE_TERMS = [
    "정수장", "하수처리장", "해수담수화", "혈액투석", "의약품", "체육관", "냉난방", "공기조화기",
    "하수관", "상수관", "배수개선", "아스콘", "교량", "도로", "터널", "농업용", "농기계", "건조기",
    "방탄방패", "방탄복", "총기", "탄약", "청사 cctv", "학교 cctv", "주차장 cctv",
]


def _normalize(value: Any) -> str:
    return re.sub(r"[\s\-_/·ㆍ,.:;()\[\]{}]+", " ", str(value or "").lower()).strip()


def _env_terms(name: str) -> List[str]:
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]


def _contains(text: str, term: str) -> bool:
    needle = _normalize(term)
    if not needle:
        return False
    if re.fullmatch(r"[a-z0-9 ]+", needle):
        pattern = r"(?<![a-z0-9])" + re.escape(needle).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
        return bool(re.search(pattern, text))
    return needle in text


def _hits(text: str, terms: Iterable[str]) -> List[str]:
    return sorted({term for term in terms if _contains(text, term)}, key=lambda value: (len(value), value), reverse=True)


def _empty_result(exclude_hits: List[str], reason: str) -> Dict[str, Any]:
    return {
        "classification_version": CLASSIFICATION_VERSION,
        "gate_passed": False,
        "sales_category": "EXCLUDE",
        "opportunity_type": "UNRELATED",
        "sales_timing": "IGNORE",
        "score": 0,
        "priority": "DROP",
        "confidence": 98 if exclude_hits else 90,
        "reason": reason,
        "recommended_action": "영업 파이프라인에서 제외",
        "matched_keywords": [],
        "shipyard_keywords": [],
        "build_keywords": [],
        "platform_keywords": [],
        "watchlist_hits": [],
        "buyer_keywords": [],
        "equipment_keywords": [],
        "early_signal_keywords": [],
        "exclude_keywords": exclude_hits,
        "drive_score": 0,
        "motor_score": 0,
        "power_score": 0,
    }


def classify_sales_opportunity(value: Any) -> Dict[str, Any]:
    """텍스트를 ABB Marine Drives 영업 관점으로 분류한다."""

    text = _normalize(value)
    vessel_hits = _hits(text, [*VESSEL_TERMS, *_env_terms("VESSEL_CONTEXT_TERMS")])
    target_hits = _hits(text, [*TARGET_PLATFORM_TERMS, *_env_terms("SHIP_WATCHLIST_TERMS")])
    infrastructure_hits = _hits(text, MARINE_INFRA_TERMS)
    buyer_hits = _hits(text, BUYER_TERMS)
    shipyard_hits = _hits(text, [*SHIPYARD_TERMS, *_env_terms("SHIPYARD_WATCHLIST")])
    solution_hits = _hits(text, [*DIRECT_SOLUTION_TERMS, *_env_terms("DRIVE_SOLUTION_TERMS")])
    power_hits = _hits(text, POWER_SYSTEM_TERMS)
    newbuild_hits = _hits(text, [*NEWBUILD_TERMS, *_env_terms("VESSEL_BUILD_WATCHLIST")])
    if "건조기" in text and not _hits(text, ["선박 건조", "함정 건조", "건조사업", "대체건조", "신조"]):
        newbuild_hits = [term for term in newbuild_hits if term != "건조"]
    retrofit_hits = _hits(text, RETROFIT_TERMS)
    early_hits = _hits(text, EARLY_SIGNAL_TERMS)
    non_sales_hits = _hits(text, NON_SALES_EQUIPMENT_TERMS)
    hard_noise_hits = _hits(text, HARD_NOISE_TERMS)

    cctv_noise = "cctv" in text and not bool(re.search(r"(?<![a-z])ctv(?![a-z])", text))
    tonnage_context = bool(_hits(text, ["3000톤", "3,000톤", "3000t", "3천톤"])) and bool(buyer_hits)
    shipyard_project = bool(shipyard_hits and (newbuild_hits or retrofit_hits or early_hits or solution_hits))
    watchlist_context = bool(target_hits and (buyer_hits or newbuild_hits or retrofit_hits or early_hits or solution_hits))
    infrastructure_project = bool(infrastructure_hits and (solution_hits or power_hits or retrofit_hits or early_hits))
    marine_gate = bool(vessel_hits or shipyard_project or tonnage_context or watchlist_context or infrastructure_project)

    if not marine_gate:
        reason = "실제 선박·함정·조선소 프로젝트 문맥이 확인되지 않았습니다."
        return _empty_result(sorted(set(hard_noise_hits + non_sales_hits)), reason)

    # CCTV가 선박 문맥 안에서 등장하면 참고 장비로 남기되, CTV 선박을 CCTV로 오인하지 않는다.
    if cctv_noise and not solution_hits and not newbuild_hits and not retrofit_hits and not early_hits:
        non_sales_hits = sorted(set(non_sales_hits + ["CCTV"]))

    high_value_platform = bool(target_hits)
    project_signal = bool(newbuild_hits or retrofit_hits or early_hits)
    direct_fit = bool(solution_hits)
    non_core_hits = sorted(set(non_sales_hits + hard_noise_hits))

    if direct_fit:
        category = "DIRECT_SALES"
        opportunity_type = (
            "RETROFIT" if retrofit_hits else "NEWBUILD" if newbuild_hits else
            "MARINE_INFRA" if infrastructure_hits and not vessel_hits else "PROPULSION_POWER"
        )
        timing = "IMMEDIATE" if not early_hits else "EARLY"
        base_score = 72
        recommended_action = "추진·보조부하의 모터 용량, 전압, 단선도, 선급 및 장비선정 일정을 확인해 VFD 사양 반영을 추진"
        reason = "선박 문맥과 VFD·인버터·컨버터·전기추진 관련 직접 솔루션 신호가 함께 확인되었습니다."
    elif non_core_hits and not (newbuild_hits or early_hits):
        category = "REFERENCE"
        opportunity_type = "NON_DRIVE_EQUIPMENT"
        timing = "MONITOR"
        base_score = 18
        recommended_action = "드라이브·모터·전력변환 범위와 연계되는지 확인할 때만 영업 프로젝트로 승격"
        reason = "선박 관련 공고는 맞지만 현재 내용은 계측·통신·안전·소모품 등 드라이브 비핵심 범위입니다."
    elif project_signal and (high_value_platform or buyer_hits or shipyard_hits or infrastructure_hits):
        category = "EARLY_PROJECT"
        opportunity_type = (
            "RETROFIT" if retrofit_hits else "MARINE_INFRA" if infrastructure_hits and not vessel_hits else
            "DESIGN_EARLY" if early_hits and not newbuild_hits else "NEWBUILD"
        )
        timing = "EARLY"
        base_score = 55
        recommended_action = "발주처·설계사·조선소와 기본설계/장비선정위원회 일정을 확인하고 추진·전력변환 사양을 선점"
        reason = "직접 드라이브 품목은 아직 명시되지 않았지만, 놓치면 안 되는 선박 건조·개조·설계 초기 신호입니다."
    elif non_core_hits:
        category = "REFERENCE"
        opportunity_type = "NON_DRIVE_EQUIPMENT"
        timing = "MONITOR"
        base_score = 18
        recommended_action = "드라이브·모터·전력변환 범위와 연계되는지 확인할 때만 영업 프로젝트로 승격"
        reason = "선박 관련 공고는 맞지만 현재 내용은 계측·통신·안전·소모품 등 드라이브 비핵심 범위입니다."
    else:
        category = "WATCH"
        opportunity_type = "MARINE_MONITOR"
        timing = "MONITOR"
        base_score = 35
        recommended_action = "건조·개조·설계 또는 추진시스템 발주로 전환되는지 정기 모니터링"
        reason = "선박 문맥은 확인되지만 현재 정보만으로는 드라이브 판매 범위나 프로젝트 단계가 불명확합니다."

    score = base_score
    score += min(18, len(solution_hits) * 5)
    score += 10 if high_value_platform else 0
    score += 8 if newbuild_hits else 0
    score += 9 if retrofit_hits else 0
    score += 8 if early_hits else 0
    score += 5 if buyer_hits else 0
    score += 4 if shipyard_hits else 0
    score -= min(18, len(non_core_hits) * 4) if not direct_fit else 0
    score = max(0, min(100, score))

    if category == "REFERENCE":
        priority = "REFERENCE"
    elif category == "WATCH":
        priority = "WATCH"
    elif score >= 78:
        priority = "HOT"
    else:
        priority = "WARM"

    drive_score = min(100, 20 + len(solution_hits) * 14 + (20 if _hits(text, ["vfd", "drive", "드라이브", "인버터", "converter", "컨버터"]) else 0) + (15 if project_signal else 0))
    motor_score = min(100, 18 + (48 if _hits(text, ["추진모터", "propulsion motor", "전동기", "전기모터", "축발전기"]) else 0) + (18 if target_hits else 0))
    power_score = min(100, 15 + len(power_hits) * 10 + (35 if _hits(text, ["dc grid", "직류배전", "ess", "pcs", "전력변환장치"]) else 0) + (15 if project_signal else 0))
    confidence = min(99, 62 + min(18, len(vessel_hits) * 4) + (8 if project_signal else 0) + (8 if direct_fit else 0))
    matched = sorted(set(vessel_hits + target_hits + infrastructure_hits + solution_hits + power_hits + newbuild_hits + retrofit_hits + early_hits))

    return {
        "classification_version": CLASSIFICATION_VERSION,
        "gate_passed": True,
        "sales_category": category,
        "opportunity_type": opportunity_type,
        "sales_timing": timing,
        "score": score,
        "priority": priority,
        "confidence": confidence,
        "reason": reason,
        "recommended_action": recommended_action,
        "matched_keywords": matched,
        "shipyard_keywords": shipyard_hits,
        "build_keywords": sorted(set(newbuild_hits + retrofit_hits)),
        "platform_keywords": sorted(set(vessel_hits + infrastructure_hits)),
        "watchlist_hits": target_hits,
        "buyer_keywords": buyer_hits,
        "equipment_keywords": sorted(set(solution_hits + power_hits)),
        "early_signal_keywords": early_hits,
        "exclude_keywords": sorted(set(non_sales_hits + hard_noise_hits)),
        "drive_score": drive_score,
        "motor_score": motor_score,
        "power_score": power_score,
    }


def project_sales_text(project: Dict[str, Any]) -> str:
    """기존 DB 행도 신규 분류기로 다시 평가할 수 있는 제한된 텍스트를 만든다."""

    raw = project.get("rawPayload") or project.get("raw_payload") or {}
    raw_values: List[str] = []
    if isinstance(raw, dict):
        for key in (
            "bidNtceNm", "cntrctNm", "orderPlanNm", "bsnsNm", "title", "subject", "description", "summary",
            "dminsttNm", "orderInsttNm", "cntrctInsttNm", "dmndInsttNm", "publisher", "shipyard", "builder",
        ):
            value = raw.get(key)
            if value not in (None, ""):
                raw_values.append(str(value))
    return " ".join([
        str(project.get("name") or ""), str(project.get("company") or ""), str(project.get("shipyard") or ""),
        str(project.get("keywordText") or project.get("keyword_text") or ""), *raw_values,
    ])[:12000]

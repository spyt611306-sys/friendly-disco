# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import os
import time
import uuid
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger("sdi.collector")

# 1) 해양/선박 필수 게이트 키워드 (ABB Drive 영업 타깃 선종 중심)
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
    "소방청": 25,
    "소방본부": 25,
    "해양수산부": 20,
    "어업관리단": 20,
    "항만공사": 18,
    "해양환경공단": 18,
    "지자체": 15,
    "수산과학원": 15,
    "KOMERI": 12,
    "한국선급": 12,
    "KR": 10
}

# 3) ABB 드라이브, 추진모터, 전력 ESS 패키지 관련 장비 키워드 및 점수 가중치
ABB_EQUIPMENT_KEYWORDS: Dict[str, int] = {
    "하이브리드": 40,
    "hybrid": 40,
    "전기추진": 35,
    "electric propulsion": 35,
    "인버터": 30,
    "inverter": 30,
    "드라이브": 30,
    "vfd": 30,
    "배터리": 25,
    "battery": 25,
    "ess": 25,
    "축발전기": 20,
    "shaft generator": 20,
    "pti": 20,
    "pto": 20,
    "dc grid": 25,
    "추진모터": 25,
    "propulsion motor": 25,
    "변속": 15,
    "배전반": 15,
    "switchboard": 15
}

# 4) 일반 자재 및 소모품 강제 차단 필터 (Deduplication & Noise Filter)
TITLE_EXCLUDE_KEYWORDS = [
    "정수장", "해수담수화", "혈액투석", "의약품", "학교", "체육관", "냉난방", "하수", "상수", "배수개선",
    "아스콘", "마네킹", "농업", "교량", "도로", "터널", "청진기", "박스", "플랜지", "파이프", "압축가스"
]

# 5) 중소형 및 중견 조선소 매핑 정보 (SHIPYARD_TERMS 대응)
SHIPYARD_WATCHLIST = [
    "대선조선", "HJ중공업", "한진중공업", "강남조선", "동성조선", "극동조선", "삼강엠앤티", "대한조선", "케이조선",
    "HSG성동조선", "금하네이벌텍", "동남중공업", "삼원중공업", "유일", "대양", "코리아월드써비스", "신진조선", "부원", "세진중공업"
]

# 6) 선박 건조 및 성능 개량 문맥 매핑 정보 (BUILD_TERMS 대응)
VESSEL_BUILD_WATCHLIST = [
    "건조", "대체건조", "신조", "제작구매", "제조구매", "개조", "성능개량", "전기추진", "하이브리드 전기추진", "친환경선박"
]


def is_cctv_noise(title: str) -> bool:
    """
    [CCTV 오인 차단 핵심 가드레일]
    - G2B의 'CCTV 설치', '폐쇄회로 카메라' 공고가 풍력지원선(CTV)으로 잘못 인식되는 현상을 원천 방지합니다.
    """
    title_lower = title.lower()
    cctv_excludes = ["cctv", "폐쇄회로", "감시카메라", "영상정보처리기기", "영상감시", "영상감시장치"]
    if any(k in title_lower for k in cctv_excludes):
        # 만약 'CCTV' 가 들어있음에도 명시적으로 '선박', '함정' 건조 관련 수주 건이 아니라면 노이즈로 간주하고 차단
        if not any(k in title_lower for k in ["선박", "함정", "경비정", "병원선"]):
            return True
    return False


def now_iso() -> str:
    return datetime.now().isoformat()


class BaseCollector:
    def __init__(self, name: str, source_type: str):
        self.name = name
        self.source_type = source_type
        self.operations: List[str] = []

    def evaluate_relevance(self, title: str) -> Dict[str, Any]:
        """
        ABB Ability™ 특화 스코어링 분석 엔진
        - 선명, 발주처, 장비 키워드를 교차 매핑하여 인버터/드라이브 세일즈 가치를 점수화합니다.
        """
        title_lower = title.lower()

        # CCTV 및 명시적 제외 키워드 감지 시 강제 드롭 처리
        if is_cctv_noise(title_lower) or any(exc in title_lower for exc in TITLE_EXCLUDE_KEYWORDS):
            return {
                "score": 0,
                "priority": "DROP",
                "matched_keywords": [],
                "shipyard_keywords": [],
                "build_keywords": [],
                "platform_keywords": [],
                "watchlist_hits": [],
                "drive_score": 0,
                "motor_score": 0,
                "power_score": 0
            }

        # 매칭된 카테고리별 키워드 리스트
        matched_kws = []
        shipyard_kws = []
        build_kws = []
        platform_kws = []
        watchlist_hits = []

        # 조선소 감지
        for sy in SHIPYARD_WATCHLIST:
            if sy.lower() in title_lower:
                shipyard_kws.append(sy)

        # 건조 공정 문맥 감지
        for bld in VESSEL_BUILD_WATCHLIST:
            if bld.lower() in title_lower:
                build_kws.append(bld)

        # 필수 선박 게이트 키워드 매칭
        for gate in REQUIRED_MARINE_GATE_KEYWORDS:
            if gate.lower() in title_lower:
                platform_kws.append(gate)
                matched_kws.append(gate)

        # 관심 선박(Watchlist) 키워드 매칭
        for term in WATCHLIST_TERMS := ["실습선", "어업지도선", "경비함", "소방정", "차도선", "병원선", "청항선", "하이브리드", "전기추진"]:
            if term.lower() in title_lower:
                watchlist_hits.append(term)

        # ABB 장비군 세부 정밀 스코어 연산
        drive_score = 0
        motor_score = 0
        power_score = 0

        # 드라이브 관련 단어 매칭
        if any(w in title_lower for w in ["하이브리드", "전기추진", "인버터", "드라이브", "vfd"]):
            drive_score = 80
            matched_kws.append("Drive")
        # 추진 모터 관련 단어 매칭
        if any(w in title_lower for w in ["모터", "추진", "축발전기", "motor"]):
            motor_score = 75
            matched_kws.append("Motor")
        # 배터리 및 전력 시스템 매칭
        if any(w in title_lower for w in ["배터리", "ess", "dc grid", "dcgrid"]):
            power_score = 70
            matched_kws.append("Power/ESS")

        # 가중치 결합 종합 점수 연산
        score = 0
        # 1) 발주처 가중치 반영
        for b_kw, weight in ABB_BUYER_KEYWORDS.items():
            if b_kw.lower() in title_lower:
                score += weight
                matched_kws.append(b_kw)

        # 2) 장비 가중치 반영
        for eq_kw, weight in ABB_EQUIPMENT_KEYWORDS.items():
            if eq_kw.lower() in title_lower:
                score += weight
                matched_kws.append(eq_kw)

        # 조선소 및 건조 컨텍스트 셋트 보유 시 비즈니스 가산점 20점 가산
        if len(shipyard_kws) > 0 and len(build_kws) > 0:
            score += 20

        # 기본 최소점 방어 및 백한도 설정
        if len(platform_kws) > 0 and score < 45:
            score = 45
        score = min(score, 100)

        # 우선순위 판정
        if score >= 85:
            priority = "VERIFIED"
        elif score >= 55:
            priority = "REVIEW"
        else:
            priority = "RECHECK"

        return {
            "score": score,
            "priority": priority,
            "matched_keywords": list(set(matched_kws)),
            "shipyard_keywords": list(set(shipyard_kws)),
            "build_keywords": list(set(build_kws)),
            "platform_keywords": list(set(platform_kws)),
            "watchlist_hits": list(set(watchlist_hits)),
            "drive_score": drive_score,
            "motor_score": motor_score,
            "power_score": power_score
        }

    def clean_item(self, operation_name: str, raw_payload: Dict[str, Any], title: str, publisher: str, source_url: str,
                   announcement_no: Optional[str] = None, contract_no: Optional[str] = None, project_no: Optional[str] = None,
                   region: Optional[str] = None, order_value: Optional[str] = None, currency: str = "KRW",
                   registered_at: Optional[str] = None, contract_date: Optional[str] = None, delivery_date: Optional[str] = None,
                   shipyard: Optional[str] = None) -> Dict[str, Any]:
        """
        수집된 다중 원천 규격을 프론트엔드가 요구하는 포맷으로 정밀 매핑하여 반환합니다.
        """
        relevance = self.evaluate_relevance(title)
        
        # UI 키워드 검색을 위해 텍스트 데이터 토큰 통합 생성
        keyword_text = " ".join(relevance["matched_keywords"]) + " " + " ".join(relevance["shipyard_keywords"]) + " " + " ".join(relevance["build_keywords"])

        # DB 인서트를 위한 1:N 이력 객체 생성
        history_id = str(uuid.uuid4())
        source_id = str(uuid.uuid4())

        return {
            "id": f"SDI-PJT-{uuid.uuid4().hex[:8].upper()}",
            "name": title,
            "status": "Under Construction" if registered_at else "On Order",
            "hullNo": f"H-{announcement_no[-5:]}" if announcement_no else f"H-SYS-{uuid.uuid4().hex[:4].upper()}",
            "shipType": "특수선 (하이브리드)" if relevance["drive_score"] > 0 else "관공선 및 특수선",
            "dwt": "150 mt",
            "gt": "250 gt",
            "size": "250",
            "unit": "GT",
            "cgt": "1,100 cgt",
            "announcementNo": announcement_no,
            "contractNo": contract_no,
            "projectNo": project_no,
            "region": region or "전국 해역",
            "orderValue": order_value or "0",
            "currency": currency,
            "registeredAt": registered_at or now_iso().split("T")[0],
            "contractDate": contract_date or now_iso().split("T")[0],
            "deliveryDate": delivery_date or (datetime.now() + timedelta(days=730)).strftime("%Y-%m-%d"),
            "shipyard": shipyard or "미정 (입찰 중)",
            "sourceType": self.source_type,
            "sourceService": self.name,
            "sourceOperation": operation_name,
            "verificationStatus": relevance["priority"],
            "matchedKeywords": relevance["matched_keywords"],
            "shipyardKeywords": relevance["shipyard_keywords"],
            "buildKeywords": relevance["build_keywords"],
            "platformKeywords": relevance["platform_keywords"],
            "watchlistHits": relevance["watchlist_hits"],
            "driveScore": relevance["drive_score"],
            "motorScore": relevance["motor_score"],
            "powerScore": relevance["power_score"],
            "keywordText": keyword_text,
            "rawPayload": raw_payload,
            "history": [
                {
                    "id": history_id,
                    "date": now_iso().split("T")[0],
                    "action": "COLLECTED",
                    "detail": f"{self.name}/{operation_name} 수집 및 분석 | ABB score={relevance['score']} priority={relevance['priority']}"
                }
            ],
            "sources": [
                {
                    "id": source_id,
                    "title": title,
                    "publisher": publisher or self.name,
                    "url": source_url,
                    "date": registered_at or now_iso().split("T")[0],
                    "type": self.source_type,
                }
            ],
        }

    async def collect(self, seed_projects: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        return []

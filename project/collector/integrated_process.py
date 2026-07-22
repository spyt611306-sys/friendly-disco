# -*- coding: utf-8 -*-
"""Link known G2B identifiers to the complete procurement process."""

import os
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseCollector, clean_text, get_env_int


INTEGRATED_PROCESS_OPERATION_NAMES = [
    "getCntrctProcssIntgOpenFrgcpt",
    "getCntrctProcssIntgOpenThng",
    "getCntrctProcssIntgOpenServc",
    "getCntrctProcssIntgOpenCnstwk",
]


class IntegratedProcessCollector(BaseCollector):
    name = "CntrctProcssIntgOpenService"
    source_type = "G2B"
    base_url = "https://apis.data.go.kr/1230000/ao/CntrctProcssIntgOpenService"
    default_type = "json"
    operations = {name: {"path": name} for name in INTEGRATED_PROCESS_OPERATION_NAMES}

    @staticmethod
    def _lookup(project: Dict[str, Any]) -> Optional[Tuple[str, str, str]]:
        raw = project.get("rawPayload") or {}
        evidence = raw.get("_evidence") or {}
        identifiers = evidence.get("identifiers") or {}
        candidates = [
            ("1", "bidNtceNo", project.get("announcementNo") or identifiers.get("announcementNo")),
            ("2", "bfSpecRgstNo", identifiers.get("prespecNo") or raw.get("bfSpecRgstNo")),
            ("3", "orderPlanNo", identifiers.get("orderPlanNo") or raw.get("orderPlanUntyNo") or raw.get("orderPlanNo")),
            ("4", "prcrmntReqNo", identifiers.get("procurementRequestNo") or raw.get("prcrmntReqNo")),
        ]
        return next(((division, field, clean_text(value)) for division, field, value in candidates if clean_text(value)), None)

    @staticmethod
    def _operations(project: Dict[str, Any]) -> List[str]:
        operation = clean_text(project.get("sourceOperation")).lower()
        raw = project.get("rawPayload") or {}
        business = clean_text(raw.get("bsnsDivNm") or raw.get("bsnsDivCd")).lower()
        if "frgcpt" in operation or "외자" in business:
            return ["getCntrctProcssIntgOpenFrgcpt"]
        if "cnstwk" in operation or "공사" in business:
            return ["getCntrctProcssIntgOpenCnstwk"]
        if "servc" in operation or "용역" in business:
            return ["getCntrctProcssIntgOpenServc"]
        if "thng" in operation or "물품" in business:
            return ["getCntrctProcssIntgOpenThng"]
        configured = [item.strip() for item in os.getenv("INTEGRATED_PROCESS_FALLBACK_OPS", "getCntrctProcssIntgOpenThng,getCntrctProcssIntgOpenServc").split(",") if item.strip()]
        return configured

    async def collect(self, seed_projects: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
        maximum = get_env_int("INTEGRATED_PROCESS_MAX_PROJECTS", 40, 1, 200)
        ranked = sorted(seed_projects or [], key=lambda row: (int(row.get("abbScore") or 0), bool(row.get("favorite"))), reverse=True)
        results: List[Dict[str, Any]] = []
        seen_queries: set[Tuple[str, str]] = set()
        failures: List[Exception] = []
        for project in ranked[:maximum]:
            lookup = self._lookup(project)
            if not lookup:
                continue
            division, field, value = lookup
            query_key = (field, value)
            if query_key in seen_queries:
                continue
            seen_queries.add(query_key)
            for operation_name in self._operations(project):
                try:
                    items = await self.request_all_pages(operation_name, {"inqryDiv": division, field: value})
                except Exception as exc:
                    failures.append(exc)
                    continue
                for item in items:
                    linked = self.build_project(operation_name, item, f"{self.base_url}/{operation_name}")
                    if linked:
                        results.append(linked)
                if items:
                    break
        if not results and failures and len(failures) >= max(1, len(seen_queries)):
            raise RuntimeError(f"계약과정 연계 조회 실패: {failures[-1]}")
        return results


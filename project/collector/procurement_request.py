# -*- coding: utf-8 -*-
"""나라장터 조달요청서비스 collector.

조달요청은 발주계획보다 구체적이고 사전규격/입찰보다 이른 경우가 많아
영업 사양 반영 시점을 포착하는 핵심 단계로 취급한다.
"""

import os
from datetime import date, timedelta
from typing import Any, Dict, List

from .base import BaseCollector, chunk_days, get_env_int


PROCUREMENT_REQUEST_OPERATION_NAMES = [
    "getPrcrmntReqInfoListThng",
    "getPrcrmntReqInfoListThngDetail",
    "getPrcrmntReqInfoListThngPPSSrch",
    "getPrcrmntReqInfoListCnstwk",
    "getPrcrmntReqInfoListCnstwkPPSSrch",
    "getPrcrmntReqInfoListGnrlServc",
    "getPrcrmntReqInfoListGnrlServcPPSSrch",
    "getPrcrmntReqInfoListTechServc",
    "getPrcrmntReqInfoListTechServcPPSSrch",
    "getPrcrmntReqInfoListFrgcpt",
    "getPrcrmntReqInfoListFrgcptDetail",
    "getPrcrmntReqInfoListFrgcptPPSSrch",
]


class ProcurementRequestCollector(BaseCollector):
    name = "PrcrmntReqInfoService"
    source_type = "G2B"
    base_url = "https://apis.data.go.kr/1230000/ao/PrcrmntReqInfoService"
    default_type = "json"
    operations = {name: {"path": name} for name in PROCUREMENT_REQUEST_OPERATION_NAMES}

    async def collect(self, seed_projects: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
        end_day = date.today()
        start_day = end_day - timedelta(days=get_env_int("PROCUREMENT_REQUEST_LOOKBACK_DAYS", 365) - 1)
        windows = chunk_days(start_day, end_day, get_env_int("G2B_WINDOW_DAYS", 30))
        target_ops = [
            item.strip()
            for item in os.getenv(
                "PROCUREMENT_REQUEST_TARGET_OPS",
                "getPrcrmntReqInfoListThng,getPrcrmntReqInfoListCnstwk,getPrcrmntReqInfoListGnrlServc,getPrcrmntReqInfoListTechServc",
            ).split(",")
            if item.strip()
        ]
        results: List[Dict[str, Any]] = []
        for operation_name in target_ops:
            for left, right in windows:
                params = {
                    "inqryDiv": "1",
                    "inqryBgnDt": left.strftime("%Y%m%d") + "0000",
                    "inqryEndDt": right.strftime("%Y%m%d") + "2359",
                }
                for item in await self.request_all_pages(operation_name, params):
                    project = self.build_project(operation_name, item, f"{self.base_url}/{operation_name}")
                    if project:
                        results.append(project)
        return results


import os
from datetime import date, timedelta
from typing import Any, Dict, List

from .base import BaseCollector, chunk_days, get_env_int


AWARD_OPERATION_NAMES = [
    "getScsbidListSttusThng",
    "getScsbidListSttusCnstwk",
    "getScsbidListSttusServc",
    "getScsbidListSttusFrgcpt",
    "getOpengResultListInfoThng",
    "getOpengResultListInfoCnstwk",
    "getOpengResultListInfoServc",
    "getOpengResultListInfoFrgcpt",
    "getOpengResultListInfoThngPreparPcDetail",
    "getOpengResultListInfoCnstwkPreparPcDetail",
    "getOpengResultListInfoServcPreparPcDetail",
    "getOpengResultListInfoFrgcptPreparPcDetail",
    "getOpengResultListInfoOpengCompt",
    "getOpengResultListInfoFailing",
    "getOpengResultListInfoRebid",
    "getScsbidListSttusThngPPSSrch",
    "getScsbidListSttusCnstwkPPSSrch",
    "getScsbidListSttusServcPPSSrch",
    "getScsbidListSttusFrgcptPPSSrch",
    "getOpengResultListInfoThngPPSSrch",
    "getOpengResultListInfoCnstwkPPSSrch",
    "getOpengResultListInfoServcPPSSrch",
    "getOpengResultListInfoFrgcptPPSSrch",
]


class AwardCollector(BaseCollector):
    name = "ScsbidInfoService"
    source_type = "G2B"
    base_url = "https://apis.data.go.kr/1230000/as/ScsbidInfoService"
    default_type = "json"
    operations = {name: {"path": name} for name in AWARD_OPERATION_NAMES}

    async def collect(self, seed_projects: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
        end_day = date.today()
        start_day = end_day - timedelta(days=get_env_int("AWARD_LOOKBACK_DAYS", 90) - 1)
        windows = chunk_days(start_day, end_day, get_env_int("G2B_WINDOW_DAYS", 30))
        target_ops = [x.strip() for x in os.getenv("AWARD_TARGET_OPS", "getScsbidListSttusThng").split(",") if x.strip()]
        results: List[Dict[str, Any]] = []
        for operation_name in target_ops:
            for left, right in windows:
                params: Dict[str, Any] = {
                    "inqryDiv": "1",
                    "inqryBgnDt": left.strftime("%Y%m%d") + "0000",
                    "inqryEndDt": right.strftime("%Y%m%d") + "2359",
                }
                items = await self.request_all_pages(operation_name, params)
                for item in items:
                    project = self.build_project(operation_name, item, f"{self.base_url}/{operation_name}")
                    if project:
                        results.append(project)
        return results

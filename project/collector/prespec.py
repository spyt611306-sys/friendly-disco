from datetime import date, timedelta
from typing import Dict, List

from .base import BaseCollector, chunk_days


PRESPEC_OPERATION_NAMES = [
    "getPublicPrcureThngInfoThng",
    "getInsttAcctoThngListInfoThng",
    "getThngDetailMetaInfoThng",
    "getPublicPrcureThngInfoFrgcpt",
    "getInsttAcctoThngListInfoFrgcpt",
    "getThngDetailMetaInfoFrgcpt",
    "getPublicPrcureThngInfoServc",
    "getInsttAcctoThngListInfoServc",
    "getThngDetailMetaInfoServc",
    "getPublicPrcureThngInfoCnstwk",
    "getInsttAcctoThngListInfoCnstwk",
    "getThngDetailMetaInfoCnstwk",
    "getPublicPrcureThngInfoThngPPSSrch",
    "getPublicPrcureThngInfoFrgcptPPSSrch",
    "getPublicPrcureThngInfoServcPPSSrch",
    "getPublicPrcureThngInfoCnstwkPPSSrch",
    "getPublicPrcureThngOpinionInfoThng",
    "getPublicPrcureThngOpinionInfoFrgcpt",
    "getPublicPrcureThngOpinionInfoServc",
    "getPublicPrcureThngOpinionInfoCnstwk",
]


class PrespecCollector(BaseCollector):
    name = "HrcspSsstndrdInfoService"
    source_type = "G2B"
    base_url = "http://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService"
    default_type = "json"
    operations = {name: {"path": name} for name in PRESPEC_OPERATION_NAMES}

    async def collect(self, seed_projects: List[Dict[str, str]] | None = None) -> List[Dict[str, str]]:
        end_day = date.today()
        start_day = end_day - timedelta(days=6)
        windows = chunk_days(start_day, end_day, 1)
        target_ops = [
            "getPublicPrcureThngInfoThng",
            "getPublicPrcureThngInfoFrgcpt",
            "getPublicPrcureThngInfoServc",
            "getPublicPrcureThngInfoCnstwk",
        ]
        results: List[Dict[str, str]] = []
        for operation_name in target_ops:
            for left, right in windows:
                params = {
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

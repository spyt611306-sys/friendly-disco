import os
from datetime import date, timedelta
from typing import Any, Dict, List

from .base import BaseCollector, chunk_days, get_env_int


BID_OPERATION_NAMES = [
    "getBidPblancListInfoCnstwk",
    "getBidPblancListInfoServc",
    "getBidPblancListInfoFrgcpt",
    "getBidPblancListInfoThng",
    "getBidPblancListInfoThngBsisAmount",
    "getBidPblancListInfoCnstwkBsisAmount",
    "getBidPblancListInfoServcBsisAmount",
    "getBidPblancListInfoChgHstryThng",
    "getBidPblancListInfoChgHstryCnstwk",
    "getBidPblancListInfoChgHstryServc",
    "getBidPblancListInfoCnstwkPPSSrch",
    "getBidPblancListInfoServcPPSSrch",
    "getBidPblancListInfoFrgcptPPSSrch",
    "getBidPblancListInfoThngPPSSrch",
    "getBidPblancListInfoLicenseLimit",
    "getBidPblancListInfoPrtcptPsblRgn",
    "getBidPblancListInfoThngPurchsObjPrdct",
    "getBidPblancListInfoServcPurchsObjPrdct",
    "getBidPblancListInfoFrgcptPurchsObjPrdct",
    "getBidPblancListInfoEorderAtchFileInfo",
    "getBidPblancListInfoEtc",
    "getBidPblancListInfoEtcPPSSrch",
    "getBidPblancListPPIFnlRfpIssAtchFileInfo",
    "getBidPblancListBidPrceCalclAInfo",
    "getBidPblancListEvaluationIndstrytyMfrcInfo",
]


class BidCollector(BaseCollector):
    name = "BidPublicInfoService"
    source_type = "G2B"
    base_url = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService"
    default_type = "json"
    operations = {name: {"path": name} for name in BID_OPERATION_NAMES}

    async def collect(self, seed_projects: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
        end_day = date.today()
        start_day = end_day - timedelta(days=get_env_int("BID_LOOKBACK_DAYS", 180) - 1)
        windows = chunk_days(start_day, end_day, 1)
        target_ops = [x.strip() for x in os.getenv("BID_TARGET_OPS", "getBidPblancListInfoThng,getBidPblancListInfoServc,getBidPblancListInfoCnstwk,getBidPblancListInfoThngPPSSrch,getBidPblancListInfoServcPPSSrch,getBidPblancListInfoCnstwkPPSSrch,getBidPblancListInfoEorderAtchFileInfo").split(",") if x.strip()]
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

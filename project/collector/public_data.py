import os
from datetime import date, timedelta
from typing import Dict, List

from .base import BaseCollector, chunk_days, get_env_int


PUBLIC_DATA_OPERATION_NAMES = [
    "getDataSetOpnStdBidPblancInfo",
    "getDataSetOpnStdScsbidInfo",
    "getDataSetOpnStdCntrctInfo",
]


class PublicDataCollector(BaseCollector):
    name = "PubDataOpnStdService"
    source_type = "PUBLIC_STD"
    base_url = "http://apis.data.go.kr/1230000/ao/PubDataOpnStdService"
    default_type = "json"
    operations = {name: {"path": name} for name in PUBLIC_DATA_OPERATION_NAMES}

    async def collect(self, seed_projects: List[Dict[str, str]] | None = None) -> List[Dict[str, str]]:
        today = date.today()
        results: List[Dict[str, str]] = []

        bid_start = today - timedelta(days=get_env_int("PUBLIC_DATA_LOOKBACK_DAYS", 2) - 1)
        bid_params = {
            "bidNtceBgnDt": bid_start.strftime("%Y%m%d") + "0000",
            "bidNtceEndDt": today.strftime("%Y%m%d") + "2359",
        }
        for item in await self.request_all_pages("getDataSetOpnStdBidPblancInfo", bid_params):
            project = self.build_project("getDataSetOpnStdBidPblancInfo", item, f"{self.base_url}/getDataSetOpnStdBidPblancInfo")
            if project:
                results.append(project)

        contract_start = today - timedelta(days=get_env_int("PUBLIC_DATA_LOOKBACK_DAYS", 2) - 1)
        contract_params = {
            "cntrctCnclsBgnDate": contract_start.strftime("%Y%m%d"),
            "cntrctCnclsEndDate": today.strftime("%Y%m%d"),
        }
        for item in await self.request_all_pages("getDataSetOpnStdCntrctInfo", contract_params):
            project = self.build_project("getDataSetOpnStdCntrctInfo", item, f"{self.base_url}/getDataSetOpnStdCntrctInfo")
            if project:
                results.append(project)

        award_windows = chunk_days(today, today, 1)
        for bsns_div_cd in ["1", "2", "3", "5"]:
            for left, right in award_windows:
                award_params = {
                    "bsnsDivCd": bsns_div_cd,
                    "opengBgnDt": left.strftime("%Y%m%d") + "0000",
                    "opengEndDt": right.strftime("%Y%m%d") + "2359",
                }
                for item in await self.request_all_pages("getDataSetOpnStdScsbidInfo", award_params):
                    project = self.build_project("getDataSetOpnStdScsbidInfo", item, f"{self.base_url}/getDataSetOpnStdScsbidInfo")
                    if project:
                        results.append(project)

        return results

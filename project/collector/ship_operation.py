import os
from datetime import date, timedelta
from typing import Dict, List, Optional

from .base import BaseCollector, chunk_days


SHIP_OPERATION_NAMES = ["Info5"]


class ShipOperationCollector(BaseCollector):
    name = "VsslEtrynd"
    source_type = "SHIP"
    base_url = "https://apis.data.go.kr/1192000/VsslEtrynd5"
    key_param_name = "serviceKey"
    default_type = ""
    default_num_rows = 50
    operations = {name: {"path": name} for name in SHIP_OPERATION_NAMES}

    def get_port_codes(self) -> List[str]:
        port_codes = os.getenv("SHIP_OPERATION_PORT_CODES", "")
        return [x.strip() for x in port_codes.split(",") if x.strip()]

    async def collect(self, seed_projects: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
        port_codes = self.get_port_codes()
        if not port_codes:
            return []
        end_day = date.today()
        start_day = end_day - timedelta(days=1)
        results: List[Dict[str, str]] = []
        for left, right in chunk_days(start_day, end_day, 1):
            for port_code in port_codes:
                params = {
                    "prtAgCd": port_code,
                    "sde": left.strftime("%Y%m%d"),
                    "ede": right.strftime("%Y%m%d"),
                    "deGb": "I",
                }
                items = await self.request_all_pages("Info5", params)
                for item in items:
                    project = self.build_project("Info5", item, f"{self.base_url}/Info5")
                    if project:
                        results.append(project)
        return results

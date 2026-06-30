import os
from typing import Dict, List, Optional, Set

from .base import BaseCollector


SHIP_SUPPORT_OPERATION_NAMES = ["Info3"]


class ShipSupportCollector(BaseCollector):
    name = "SicsVsslManp"
    source_type = "SHIP"
    base_url = "http://apis.data.go.kr/1192000/SicsVsslManp3"
    key_param_name = "serviceKey"
    default_type = ""
    default_num_rows = 50
    operations = {name: {"path": name} for name in SHIP_SUPPORT_OPERATION_NAMES}

    def extract_seed_names(self, seed_projects: Optional[List[Dict[str, str]]]) -> List[str]:
        seeds: Set[str] = set()
        env_names = os.getenv("SHIP_SUPPORT_VSSL_NAMES", "")
        for token in [x.strip() for x in env_names.split(",") if x.strip()]:
            seeds.add(token)
        for project in seed_projects or []:
            name = str(project.get("name", "")).strip()
            if name:
                seeds.add(name[:100])
        return list(seeds)[:20]

    async def collect(self, seed_projects: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
        results: List[Dict[str, str]] = []
        for seed_name in self.extract_seed_names(seed_projects):
            items = await self.request_all_pages("Info3", {"vsslNm": seed_name})
            for item in items:
                project = self.build_project("Info3", item, f"{self.base_url}/Info3")
                if project:
                    results.append(project)
        return results

from typing import Dict, List

from .base import BaseCollector


USER_INFO_OPERATION_NAMES = [
    "getDminsttInfo02",
    "getPrcrmntCorpBasicInfo02",
    "getPrcrmntCorpIndstrytyInfo02",
    "getPrcrmntCorpSplyPrdctInfo02",
    "getUnptRsttCorpInfo02",
]


class UserInfoCollector(BaseCollector):
    name = "UsrInfoService02"
    source_type = "USER_INFO"
    base_url = "https://apis.data.go.kr/1230000/ao/UsrInfoService02"
    default_type = "json"
    operations = {name: {"path": name} for name in USER_INFO_OPERATION_NAMES}

    async def collect(self, seed_projects: List[Dict[str, str]] | None = None) -> List[Dict[str, str]]:
        return []

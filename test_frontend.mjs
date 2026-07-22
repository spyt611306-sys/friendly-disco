from typing import Dict, List

from .base import BaseCollector


class IncheonPortCollector(BaseCollector):
    name = "IncheonPort"
    source_type = "DEFERRED"
    base_url = ""
    key_env_name = "INCHEON_PORT_API_KEY"
    operations = {}

    async def collect(self, seed_projects: List[Dict[str, str]] | None = None) -> List[Dict[str, str]]:
        return []

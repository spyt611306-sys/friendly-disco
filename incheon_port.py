import os
from datetime import date, timedelta
from typing import Dict, List

from .base import BaseCollector, chunk_days, get_env_int
from .document_analyzer import DocumentAnalyzer


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
    base_url = "https://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService"
    default_type = "json"
    operations = {name: {"path": name} for name in PRESPEC_OPERATION_NAMES}

    async def collect(self, seed_projects: List[Dict[str, str]] | None = None) -> List[Dict[str, str]]:
        end_day = date.today()
        start_day = end_day - timedelta(days=get_env_int("PRESPEC_LOOKBACK_DAYS", 180) - 1)
        windows = chunk_days(start_day, end_day, get_env_int("G2B_WINDOW_DAYS", 30))
        target_ops = [x.strip() for x in os.getenv("PRESPEC_TARGET_OPS", "getPublicPrcureThngInfoThng,getPublicPrcureThngInfoServc,getPublicPrcureThngInfoCnstwk,getThngDetailMetaInfoThng,getThngDetailMetaInfoServc,getThngDetailMetaInfoCnstwk").split(",") if x.strip()]
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
        analyzer = DocumentAnalyzer()
        try:
            if analyzer.enabled:
                remaining = get_env_int("DOCUMENT_MAX_PROJECTS_PER_RUN", 8, 0, 50)
                enriched: List[Dict[str, str]] = []
                for project in sorted(
                    results,
                    key=lambda row: int(((row.get("rawPayload") or {}).get("_abbTargeting") or {}).get("score") or 0),
                    reverse=True,
                ):
                    has_documents = any(
                        str(source.get("evidenceKind") or "").upper() == "OFFICIAL_ATTACHMENT"
                        for source in project.get("sources") or []
                        if isinstance(source, dict)
                    )
                    if has_documents and remaining > 0:
                        project = await analyzer.enrich_project(
                            project,
                            max_attachments=get_env_int("DOCUMENT_MAX_ATTACHMENTS_PER_PROJECT", 2, 1, 5),
                        )
                        remaining -= 1
                    enriched.append(project)
                results = enriched
        finally:
            await analyzer.aclose()
        return results

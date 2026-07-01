import os
from datetime import date
from typing import Dict, List

from .base import BaseCollector


ORDER_PLAN_OPERATION_NAMES = [
    "getOrderPlanSttusListThng",
    "getOrderPlanSttusListCnstwk",
    "getOrderPlanSttusListServc",
    "getOrderPlanSttusListFrgcpt",
    "getOrderPlanSttusListThngPPSSrch",
    "getOrderPlanSttusListCnstwkPPSSrch",
    "getOrderPlanSttusListServcPPSSrch",
    "getOrderPlanSttusListFrgcptPPSSrch",
]


class OrderPlanCollector(BaseCollector):
    name = "OrderPlanSttusService"
    source_type = "G2B"
    base_url = "http://apis.data.go.kr/1230000/ao/OrderPlanSttusService"
    default_type = "json"
    operations = {name: {"path": name} for name in ORDER_PLAN_OPERATION_NAMES}

    async def collect(self, seed_projects: List[Dict[str, str]] | None = None) -> List[Dict[str, str]]:
        today = date.today()
        month_from = (today.replace(day=1))
        params = {
            "inqryDiv": "1",
            "orderBgnYm": month_from.strftime("%Y%m"),
            "orderEndYm": today.strftime("%Y%m"),
        }
        results: List[Dict[str, str]] = []
        for operation_name in [
            "getOrderPlanSttusListThng",
            "getOrderPlanSttusListCnstwk",
            "getOrderPlanSttusListServc",
            "getOrderPlanSttusListFrgcpt",
        ]:
            items = await self.request_all_pages(operation_name, params)
            for item in items:
                project = self.build_project(operation_name, item, f"{self.base_url}/{operation_name}")
                if project:
                    results.append(project)
        return results

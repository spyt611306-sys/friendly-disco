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
    base_url = "https://apis.data.go.kr/1230000/ao/OrderPlanSttusService"
    default_type = "json"
    operations = {name: {"path": name} for name in ORDER_PLAN_OPERATION_NAMES}

    async def collect(self, seed_projects: List[Dict[str, str]] | None = None) -> List[Dict[str, str]]:
        today = date.today()
        lookback_months = max(1, int(os.getenv("ORDER_PLAN_LOOKBACK_MONTHS", "6")))
        future_months = max(0, min(60, int(os.getenv("ORDER_PLAN_FUTURE_MONTHS", "24"))))
        current_index = today.year * 12 + today.month - 1
        start_index = current_index - (lookback_months - 1)
        end_index = current_index + future_months
        start_year, start_month_zero = divmod(start_index, 12)
        end_year, end_month_zero = divmod(end_index, 12)
        params = {
            "inqryDiv": "1",
            "orderBgnYm": f"{start_year:04d}{start_month_zero + 1:02d}",
            "orderEndYm": f"{end_year:04d}{end_month_zero + 1:02d}",
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

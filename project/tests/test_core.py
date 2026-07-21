import unittest

from collector.base import BaseCollector, find_items, infer_stage, parse_xml_payload
from main import dedupe_projects, extract_abb
from sales_intelligence import classify_sales_opportunity


class CollectorCoreTests(unittest.TestCase):
    def test_xml_items_are_extracted(self):
        payload = parse_xml_payload(
            "<response><body><items><item><title>경비정 건조</title></item>"
            "<item><title>병원선 개조</title></item></items></body></response>"
        )
        self.assertEqual(len(find_items(payload)), 2)

    def test_project_uses_only_source_facts(self):
        collector = BaseCollector()
        collector.source_type = "G2B"
        project = collector.build_project(
            "getBidPblancListInfoThng",
            {
                "bidNtceNm": "해양경찰 친환경 하이브리드 경비정 건조",
                "dminsttNm": "해양경찰청",
                "bidNtceNo": "2026-001",
                "bidNtceDt": "20260721",
                "bidNtceDtlUrl": "https://www.g2b.go.kr/detail/2026-001",
            },
            "https://example.go.kr/notice/2026-001",
        )
        self.assertIsNotNone(project)
        self.assertIsNone(project["shipyard"])
        self.assertIsNone(project["deliveryDate"])
        self.assertEqual(project["verificationStatus"], "UNVERIFIED")
        self.assertEqual(project["sources"][0]["url"], "https://www.g2b.go.kr/detail/2026-001")
        self.assertEqual(project["sources"][0]["evidenceKind"], "OFFICIAL")

    def test_cctv_is_not_misread_as_ctv_vessel(self):
        project = BaseCollector().build_project(
            "getBidPblancListInfoThng",
            {"bidNtceNm": "청사 CCTV 영상감시 장비 설치", "dminsttNm": "시청"},
            "https://example.go.kr/cctv",
        )
        self.assertIsNone(project)

    def test_buyer_name_alone_does_not_create_false_project(self):
        project = BaseCollector().build_project(
            "getBidPblancListInfoThng",
            {"bidNtceNm": "방탄방패 구매", "dminsttNm": "해양경찰청"},
            "https://example.go.kr/shield",
        )
        self.assertIsNone(project)

    def test_generic_drying_project_is_not_a_shipbuilding_project(self):
        result = classify_sales_opportunity("농산물 건조기 제작구매 시청")
        self.assertEqual(result["sales_category"], "EXCLUDE")

    def test_ship_instrument_replacement_is_kept_in_reference_inbox(self):
        project = BaseCollector().build_project(
            "getBidPblancListInfoThng",
            {"bidNtceNm": "어업지도선 노후 계측기 교체", "dminsttNm": "남해어업관리단"},
            "https://example.go.kr/instrument",
        )
        self.assertIsNotNone(project)
        self.assertEqual(project["rawPayload"]["_abbTargeting"]["salesCategory"], "REFERENCE")
        self.assertEqual(project["rawPayload"]["_abbTargeting"]["priority"], "REFERENCE")

    def test_ship_instrument_replacement_work_is_still_reference(self):
        result = classify_sales_opportunity("해양경찰 경비함 노후 계측기 교체공사")
        self.assertEqual(result["sales_category"], "REFERENCE")
        self.assertEqual(result["priority"], "REFERENCE")

    def test_shipboard_dryer_is_not_misread_as_shipbuilding(self):
        result = classify_sales_opportunity("어업지도선 주방용 식품 건조기 교체")
        self.assertNotIn(result["sales_category"], {"DIRECT_SALES", "EARLY_PROJECT"})

    def test_marine_infrastructure_drive_opportunity_is_in_scope(self):
        result = classify_sales_opportunity("항만 육상전원공급설비 주파수 변환기 구축 기본설계")
        self.assertEqual(result["sales_category"], "DIRECT_SALES")
        self.assertEqual(result["opportunity_type"], "MARINE_INFRA")

    def test_vfd_retrofit_is_direct_sales(self):
        result = classify_sales_opportunity("해양경찰 경비함 추진 인버터 VFD 성능개량 retrofit")
        self.assertEqual(result["sales_category"], "DIRECT_SALES")
        self.assertEqual(result["opportunity_type"], "RETROFIT")
        self.assertGreaterEqual(result["score"], 78)

    def test_early_stage_target_vessels_are_not_missed(self):
        cases = [
            "해양경찰청 3000톤급 경비함 기본설계 및 장비선정위원회",
            "남해어업관리단 국가어업지도선 대체건조 기본계획",
            "소방본부 친환경 소방정 건조사업",
            "해상풍력 CTV 건조 기본설계",
            "전기추진 차도선 건조 발주계획",
        ]
        for text in cases:
            with self.subTest(text=text):
                result = classify_sales_opportunity(text)
                self.assertIn(result["sales_category"], {"DIRECT_SALES", "EARLY_PROJECT"})
                self.assertNotEqual(result["priority"], "DROP")

    def test_legacy_database_record_is_reclassified_on_read(self):
        old_raw = {"_abbTargeting": {"score": 65, "priority": "WARM"}}
        result = extract_abb(old_raw, {"name": "방탄방패 구매", "company": "해양경찰청"})
        self.assertEqual(result["salesCategory"], "EXCLUDE")
        self.assertEqual(result["priority"], "DROP")

    def test_stage_inference(self):
        self.assertEqual(infer_stage("getOrderPlanSttusListThng"), "PLAN")
        self.assertEqual(infer_stage("getCntrctInfoListThng"), "CONTRACT")

    def test_dedupe_merges_sources_and_advanced_stage(self):
        common = {
            "name": "친환경 관공선 건조",
            "company": "해양수산부",
            "announcementNo": "A-100",
            "matchedKeywords": ["관공선"],
            "rawPayload": {},
            "history": [],
        }
        rows = dedupe_projects([
            {**common, "id": "1", "dedupeKey": "P-1", "stage": "BID", "sources": [{"url": "https://a", "title": "입찰"}]},
            {**common, "id": "2", "dedupeKey": "P-2", "stage": "CONTRACT", "sources": [{"url": "https://b", "title": "계약"}]},
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["stage"], "CONTRACT")
        self.assertEqual(len(rows[0]["sources"]), 2)


if __name__ == "__main__":
    unittest.main()

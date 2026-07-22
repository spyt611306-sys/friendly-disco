import unittest

from collector.base import BaseCollector, find_items, infer_stage, parse_xml_payload
from collector.document_analyzer import DocumentAnalyzer
from main import dedupe_projects


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

    def test_stage_inference(self):
        self.assertEqual(infer_stage("getOrderPlanSttusListThng"), "PLAN")
        self.assertEqual(infer_stage("getPrcrmntReqInfoListThng"), "REQUEST")
        self.assertEqual(infer_stage("getCntrctInfoListThng"), "CONTRACT")

    def test_order_plan_business_name_is_recognized(self):
        project = BaseCollector().build_project(
            "getOrderPlanSttusListThng",
            {
                "bizNm": "국가어업지도선 하이브리드 대체건조",
                "orderInsttNm": "해양수산부",
                "orderPlanUntyNo": "OP-2027-001",
                "specCntnts": "전기추진모터 및 DC Grid 적용 검토",
            },
            "https://apis.data.go.kr/example",
        )
        self.assertIsNotNone(project)
        self.assertEqual(project["stage"], "PLAN")
        self.assertEqual(project["rawPayload"]["_salesIntelligence"]["opportunityClass"], "P0")

    def test_unrelated_inverter_purchase_is_filtered(self):
        project = BaseCollector().build_project(
            "getBidPblancListInfoThng",
            {"bidNtceNm": "학교 태양광 인버터 교체 구매", "dminsttNm": "교육청"},
            "https://apis.data.go.kr/example",
        )
        self.assertIsNone(project)

    def test_prespec_attachment_is_exposed_as_clickable_evidence(self):
        project = BaseCollector().build_project(
            "getPublicPrcureThngInfoThng",
            {
                "prdctClsfcNoNm": "친환경 경비정 건조",
                "dminsttNm": "해양경찰청",
                "bfSpecRgstNo": "123456",
                "specDocFileUrl1": "https://www.g2b.go.kr:8082/ep/co/fileDownload.do?fileTask=PS&fileSeq=123456::1",
            },
            "https://apis.data.go.kr/example",
        )
        self.assertEqual(project["rawPayload"]["_evidence"]["attachmentCount"], 1)
        self.assertEqual(project["sources"][1]["evidenceKind"], "OFFICIAL_ATTACHMENT")
        self.assertTrue(project["sources"][1]["isDirectLink"])

    def test_document_summary_finds_drive_components(self):
        analyzer = DocumentAnalyzer()
        summary = analyzer._summarize("선박 전기추진 시스템에 DC/DC 컨버터와 VFD, 추진모터를 적용한다.")
        self.assertIn("전력변환", summary["solutionAreas"])
        self.assertTrue(any(keyword.lower() == "vfd" for keyword in summary["matchedKeywords"]))

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

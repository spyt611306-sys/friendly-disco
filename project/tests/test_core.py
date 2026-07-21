import unittest

from collector.base import BaseCollector, find_items, infer_stage, parse_xml_payload
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

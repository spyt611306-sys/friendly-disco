import io
import os
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import httpx

from collector.base import BaseCollector
from collector.document_analyzer import DocumentAnalyzer
from collector.integrated_process import IntegratedProcessCollector


class ProcurementServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_attached_specs_use_capital_service_key(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.params.get("ServiceKey"), "TEST-KEY")
            self.assertIsNone(request.url.params.get("serviceKey"))
            return httpx.Response(200, json={"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": []}, "totalCount": 0}}})

        collector = BaseCollector()
        collector.base_url = "https://api.example.test/service"
        collector.operations = {"operation": {"path": "operation"}}
        collector._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)
        with patch.dict(os.environ, {"DATA_GO_KR_API_KEY": "TEST-KEY"}, clear=False):
            result = await collector.request_operation("operation")
        self.assertEqual(result["items"], [])
        await collector.aclose()

    async def test_hwpx_xml_text_can_be_extracted(self):
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("Contents/section0.xml", "<p><t>선박 DC/DC 컨버터와 추진모터 사양</t></p>")
        analyzer = DocumentAnalyzer()
        text = analyzer._extract_zip_xml(buffer.getvalue(), "hwpx")
        self.assertIn("DC/DC", text)
        await analyzer.aclose()

    def test_integrated_process_prefers_known_bid_number(self):
        lookup = IntegratedProcessCollector._lookup({
            "announcementNo": "20260123456",
            "rawPayload": {"bfSpecRgstNo": "99999", "prcrmntReqNo": "R26ABC"},
        })
        self.assertEqual(lookup, ("1", "bidNtceNo", "20260123456"))


if __name__ == "__main__":
    unittest.main()


import asyncio
import os
import unittest

import httpx

from collector.market_signal import MarketSignalCollector


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss><channel><title>Google News</title>
  <item><title>해양경찰 3000톤 경비함 기본설계 장비선정 착수</title>
    <link>https://news.example.com/coastguard-3000</link>
    <description>친환경 추진체계와 전기추진 장비를 검토한다.</description>
    <pubDate>Tue, 21 Jul 2026 01:00:00 GMT</pubDate><source>Marine News</source></item>
  <item><title>시청 방탄방패 구매</title>
    <link>https://news.example.com/shield</link>
    <description>청사 보안 물품을 구매한다.</description>
    <pubDate>Tue, 21 Jul 2026 01:00:00 GMT</pubDate><source>Local News</source></item>
</channel></rss>"""


class MarketSignalCollectorTests(unittest.TestCase):
    def test_google_news_discovery_keeps_only_sales_relevant_vessel_signal(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=RSS, headers={"content-type": "application/rss+xml"})

        previous = {name: os.environ.get(name) for name in (
            "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET", "GOOGLE_NEWS_VERIFY_ENABLED",
            "SALES_SIGNAL_QUERIES", "SALES_SIGNAL_MAX_QUERIES",
        )}
        os.environ.pop("NAVER_CLIENT_ID", None)
        os.environ.pop("NAVER_CLIENT_SECRET", None)
        os.environ["GOOGLE_NEWS_VERIFY_ENABLED"] = "true"
        os.environ["SALES_SIGNAL_QUERIES"] = "해양경찰 3000톤 경비함"
        os.environ["SALES_SIGNAL_MAX_QUERIES"] = "1"
        collector = MarketSignalCollector()
        collector._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            projects = asyncio.run(collector.collect())
        finally:
            asyncio.run(collector.aclose())
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["rawPayload"]["_abbTargeting"]["salesCategory"], "DIRECT_SALES")
        self.assertEqual(projects[0]["sources"][0]["evidenceKind"], "INDEPENDENT_NEWS")
        self.assertEqual(projects[0]["rawPayload"]["_marketSignal"]["provider"], "GOOGLE_NEWS_RSS")


if __name__ == "__main__":
    unittest.main()


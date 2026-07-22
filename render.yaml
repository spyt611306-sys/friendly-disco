import unittest

import httpx

from verifier import ProjectVerifier


def sample_project():
    return {
        "id": "SDI-VERIFY-1",
        "dedupeKey": "ANN:2026-001",
        "name": "해양경찰청 친환경 하이브리드 경비정 건조",
        "company": "해양경찰청",
        "announcementNo": "2026-001",
        "sourceType": "G2B",
        "rawPayload": {},
        "history": [],
        "sources": [{
            "id": "OFFICIAL-1",
            "title": "친환경 경비정 건조 입찰공고",
            "publisher": "조달청 나라장터",
            "url": "https://www.g2b.go.kr/detail/2026-001",
            "type": "G2B",
            "evidenceKind": "OFFICIAL",
        }],
    }


class VerifierTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})))
        self.verifier = ProjectVerifier(client=self.client)

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_official_source_is_not_overclaimed_as_cross_verified(self):
        result = await self.verifier.verify(sample_project(), search_external=False)
        self.assertEqual(result["verificationStatus"], "OFFICIAL_CONFIRMED")
        self.assertGreaterEqual(result["verificationConfidence"], 70)
        self.assertEqual(result["rawPayload"]["_verification"]["newsEvidenceCount"], 0)

    async def test_independent_news_creates_cross_verification(self):
        async def fake_search(_project):
            return ([{
                "id": "NEWS-1",
                "title": "해양경찰청, 친환경 경비정 건조 착수",
                "publisher": "테스트뉴스",
                "url": "https://news.example.com/article/1",
                "date": "2026-07-21",
                "type": "NEWS",
                "evidenceKind": "INDEPENDENT_NEWS",
                "matchScore": 88,
            }], "TEST_NEWS", [])

        self.verifier.search_news = fake_search
        result = await self.verifier.verify(sample_project(), search_external=True)
        self.assertEqual(result["verificationStatus"], "CROSS_VERIFIED")
        self.assertEqual(result["rawPayload"]["_verification"]["officialEvidenceCount"], 1)
        self.assertEqual(result["rawPayload"]["_verification"]["newsEvidenceCount"], 1)
        self.assertEqual(len(result["sources"]), 2)

    def test_unrelated_article_scores_low(self):
        score = self.verifier.match_score(sample_project(), {
            "title": "서울시 여름 축제 교통 통제 안내",
            "description": "도심 행사 일정과 대중교통 정보",
        })
        self.assertLess(score, self.verifier.minimum_match)


if __name__ == "__main__":
    unittest.main()

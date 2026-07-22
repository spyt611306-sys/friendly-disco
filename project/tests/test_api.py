import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import main


PROJECT = {
    "id": "SDI-API-1",
    "dedupeKey": "ANN:API-1",
    "name": "친환경 경비정 건조",
    "company": "해양경찰청",
    "stage": "BID",
    "sourceType": "G2B",
    "verificationStatus": "OFFICIAL_CONFIRMED",
    "verificationConfidence": 77,
    "rawPayload": {},
    "sources": [],
    "history": [],
}


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_key = main.ADMIN_API_KEY
        main.ADMIN_API_KEY = "test-admin-key"
        cls.client_context = TestClient(main.app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        main.ADMIN_API_KEY = cls.previous_key

    def test_static_frontend_and_meta_are_available(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        meta = self.client.get("/api/meta/apis")
        self.assertEqual(meta.status_code, 200)
        self.assertIn("verification", meta.json())

    def test_mutation_is_protected(self):
        response = self.client.post("/api/projects/SDI-API-1/verify")
        self.assertEqual(response.status_code, 401)

    def test_partial_followup_does_not_send_unset_fields(self):
        with patch("main.save_followup", return_value={**PROJECT, "favorite": True}) as mocked:
            response = self.client.put(
                "/api/projects/SDI-API-1/followup",
                json={"favorite": True},
                headers={"X-Admin-Token": "test-admin-key"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked.call_args.args[1], {"favorite": True})

    def test_manual_verification_route_returns_refreshed_project(self):
        verified = {**PROJECT, "verificationStatus": "CROSS_VERIFIED", "verificationConfidence": 93}
        verifier = MagicMock()
        verifier.verify = AsyncMock(return_value=verified)
        verifier.aclose = AsyncMock()
        with (
            patch("main.fetch_project_by_id", side_effect=[PROJECT, verified]),
            patch("main.save_projects", return_value=1),
            patch("main.ProjectVerifier", return_value=verifier),
        ):
            response = self.client.post(
                "/api/projects/SDI-API-1/verify",
                headers={"X-Admin-Token": "test-admin-key"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["project"]["verificationStatus"], "CROSS_VERIFIED")


if __name__ == "__main__":
    unittest.main()

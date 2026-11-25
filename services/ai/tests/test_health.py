import unittest

from app.main import app


class HealthEndpointTests(unittest.TestCase):
    def test_health_reports_service_status(self) -> None:
        route = next(route for route in app.routes if route.path == "/health")
        response = route.endpoint()

        self.assertEqual(response, {"status": "ok", "service": "ai"})


if __name__ == "__main__":
    unittest.main()

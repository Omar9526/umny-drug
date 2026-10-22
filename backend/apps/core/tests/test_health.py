"""Health endpoint: honest status for load balancers."""

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_health_reports_database_and_cache():
    response = APIClient().get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": True, "cache": True}

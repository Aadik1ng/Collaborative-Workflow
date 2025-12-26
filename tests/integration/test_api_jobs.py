"""Integration tests for jobs API."""

import pytest
import asyncio
from httpx import AsyncClient
from app.models.sql.user import User

@pytest.mark.asyncio
class TestJobsAPI:
    """Integration tests for async job processing."""

    async def test_submit_code_execution(self, client: AsyncClient, auth_headers: dict):
        """Test submitting a code execution job."""
        response = await client.post(
            "/api/v1/jobs/code-execution",
            headers=auth_headers,
            json={
                "code": "print('Test Job')",
                "language": "python",
                "timeout_seconds": 10
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["task_type"] == "code_execution"
        assert data["status"] == "pending"
        return data["id"]

    async def test_get_job_status(self, client: AsyncClient, auth_headers: dict):
        """Test polling job status."""
        # 1. Submit job
        job_id = await self.test_submit_code_execution(client, auth_headers)

        # 2. Get status
        response = await client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == job_id

    async def test_list_user_jobs(self, client: AsyncClient, auth_headers: dict):
        """Test listing user's jobs."""
        # Submit a job
        await self.test_submit_code_execution(client, auth_headers)

        response = await client.get("/api/v1/jobs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert "items" in data

    async def test_job_cancel(self, client: AsyncClient, auth_headers: dict):
        """Test job cancellation."""
        job_id = await self.test_submit_code_execution(client, auth_headers)

        response = await client.post(f"/api/v1/jobs/{job_id}/cancel", headers=auth_headers)
        # Note: If worker picks it up instantly, might already be completed.
        # But for testing the API endpoint:
        assert response.status_code in [200, 400] # 400 if already finished
        if response.status_code == 200:
            assert response.json()["status"] == "cancelled"

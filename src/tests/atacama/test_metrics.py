"""Tests for Prometheus metrics blueprint."""

import unittest
from unittest.mock import patch

from atacama.server import create_app
from models.database import db


class MetricsEndpointTests(unittest.TestCase):
    """Test cases for the /metrics endpoint."""

    def setUp(self):
        """Set up test application with in-memory database."""
        self.app = create_app(testing=True)
        self.app.config.update({
            'TESTING': True,
            'SERVER_NAME': 'test.local',
        })
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after tests."""
        db.cleanup()

    def test_metrics_endpoint_returns_200(self):
        """Test that /metrics endpoint returns 200 OK."""
        response = self.client.get('/metrics')
        self.assertEqual(response.status_code, 200)

    def test_metrics_endpoint_content_type(self):
        """Test that /metrics returns Prometheus text format."""
        response = self.client.get('/metrics')
        self.assertIn('text/plain', response.content_type)

    def test_metrics_contains_uptime(self):
        """Test that metrics include uptime gauge."""
        response = self.client.get('/metrics')
        self.assertIn(b'atacama_uptime_seconds', response.data)

    def test_metrics_contains_cpu_usage(self):
        """Test that metrics include CPU usage gauge."""
        response = self.client.get('/metrics')
        self.assertIn(b'atacama_cpu_usage_percent', response.data)

    def test_metrics_contains_memory_usage(self):
        """Test that metrics include memory usage gauge."""
        response = self.client.get('/metrics')
        self.assertIn(b'atacama_memory_usage_percent', response.data)

    def test_metrics_contains_disk_usage(self):
        """Test that metrics include disk usage gauge."""
        response = self.client.get('/metrics')
        self.assertIn(b'atacama_disk_usage_percent', response.data)

    def test_metrics_contains_database_status(self):
        """Test that metrics include database connection status."""
        response = self.client.get('/metrics')
        self.assertIn(b'atacama_database_connected', response.data)

    def test_metrics_contains_http_request_counter(self):
        """Test that metrics include HTTP request counter."""
        # Make a request to generate some metrics
        self.client.get('/')

        response = self.client.get('/metrics')
        self.assertIn(b'atacama_http_requests_total', response.data)

    def test_metrics_contains_http_request_duration(self):
        """Test that metrics include HTTP request duration histogram."""
        # Make a request to generate some metrics
        self.client.get('/')

        response = self.client.get('/metrics')
        self.assertIn(b'atacama_http_request_duration_seconds', response.data)

    def test_metrics_endpoint_is_unauthenticated(self):
        """Test that /metrics endpoint does not require authentication."""
        # Clear any session data
        with self.client.session_transaction() as sess:
            sess.clear()

        response = self.client.get('/metrics')
        self.assertEqual(response.status_code, 200)

    def test_metrics_contains_process_metrics(self):
        """Test that default process metrics are included."""
        response = self.client.get('/metrics')
        # prometheus_client includes process metrics by default
        self.assertIn(b'process_', response.data)


class MetricsWithContentTests(unittest.TestCase):
    """Test cases for content metrics in BLOG mode."""

    def setUp(self):
        """Set up test application in BLOG mode."""
        self.app = create_app(testing=True, blueprint_set='BLOG')
        self.app.config.update({
            'TESTING': True,
            'SERVER_NAME': 'test.local',
        })
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after tests."""
        db.cleanup()

    def test_metrics_contains_content_count(self):
        """Test that BLOG mode includes content count metrics."""
        response = self.client.get('/metrics')
        self.assertIn(b'atacama_content_count', response.data)


class TrakaidoMetricsTests(unittest.TestCase):
    """Test cases for metrics in TRAKAIDO mode."""

    def setUp(self):
        """Set up test application in TRAKAIDO mode."""
        self.app = create_app(testing=True, blueprint_set='TRAKAIDO')
        self.app.config.update({
            'TESTING': True,
            'SERVER_NAME': 'test.local',
        })
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after tests."""
        db.cleanup()

    def test_trakaido_metrics_endpoint_returns_200(self):
        """Test that /metrics endpoint works in TRAKAIDO mode."""
        response = self.client.get('/metrics')
        self.assertEqual(response.status_code, 200)

    def test_trakaido_metrics_contains_uptime(self):
        """Test that TRAKAIDO mode includes uptime metric."""
        response = self.client.get('/metrics')
        self.assertIn(b'atacama_uptime_seconds', response.data)


if __name__ == '__main__':
    unittest.main()

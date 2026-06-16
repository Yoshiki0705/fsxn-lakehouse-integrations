"""Unit tests for generate_events.py — validates event schema, uniqueness, and format."""

import json
import sys
import unittest.mock
import uuid
from pathlib import Path

import pytest

# Mock confluent_kafka before importing generate_events (not needed for unit tests)
sys.modules["confluent_kafka"] = unittest.mock.MagicMock()
sys.modules["confluent_kafka.admin"] = unittest.mock.MagicMock()

# Add parent to path for import
sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_events import (  # noqa: E402  (import after sys.path/mock setup)
    FACTORIES,
    LINES,
    SENSOR_TYPES,
    SENSOR_UNITS,
    generate_device_ids,
    generate_quality_event,
    generate_sensor_event,
    generate_status_event,
)


class TestGenerateDeviceIds:
    """Tests for device ID generation."""

    def test_generates_correct_count(self):
        ids = generate_device_ids("factory-alpha", "line-A1", count=5)
        assert len(ids) == 5

    def test_device_id_format(self):
        ids = generate_device_ids("factory-alpha", "line-A1", count=3)
        for device_id in ids:
            assert device_id.startswith("factory-alpha-line-A1-sensor-")

    def test_device_ids_unique(self):
        ids = generate_device_ids("factory-alpha", "line-A1", count=10)
        assert len(set(ids)) == 10

    def test_different_factories_different_ids(self):
        ids_a = set(generate_device_ids("factory-alpha", "line-A1", count=5))
        ids_b = set(generate_device_ids("factory-beta", "line-B1", count=5))
        assert ids_a.isdisjoint(ids_b)


class TestGenerateSensorEvent:
    """Tests for sensor event generation."""

    def test_required_fields_present(self):
        event = generate_sensor_event("factory-alpha", "line-A1", "device-001")
        required_fields = [
            "event_id",
            "timestamp",
            "factory_id",
            "device_id",
            "line_id",
            "event_type",
            "sensor_type",
            "value",
            "unit",
            "payload_reference",
            "content_type",
            "payload_size_bytes",
            "checksum_sha256",
        ]
        for field in required_fields:
            assert field in event, f"Missing field: {field}"

    def test_event_id_is_valid_uuid(self):
        event = generate_sensor_event("factory-alpha", "line-A1", "device-001")
        uuid.UUID(event["event_id"])  # Raises if invalid

    def test_event_type_is_sensor_reading(self):
        event = generate_sensor_event("factory-alpha", "line-A1", "device-001")
        assert event["event_type"] == "SENSOR_READING"

    def test_sensor_type_is_valid(self):
        event = generate_sensor_event("factory-alpha", "line-A1", "device-001")
        assert event["sensor_type"] in SENSOR_TYPES

    def test_unit_matches_sensor_type(self):
        for _ in range(50):  # Run multiple times due to randomness
            event = generate_sensor_event("factory-alpha", "line-A1", "device-001")
            assert event["unit"] == SENSOR_UNITS[event["sensor_type"]]

    def test_value_is_numeric(self):
        event = generate_sensor_event("factory-alpha", "line-A1", "device-001")
        assert isinstance(event["value"], float)

    def test_timestamp_is_positive_integer(self):
        event = generate_sensor_event("factory-alpha", "line-A1", "device-001")
        assert isinstance(event["timestamp"], int)
        assert event["timestamp"] > 0

    def test_no_payload_for_sensor_events(self):
        event = generate_sensor_event("factory-alpha", "line-A1", "device-001")
        assert event["payload_reference"] is None
        assert event["content_type"] is None
        assert event["payload_size_bytes"] is None
        assert event["checksum_sha256"] is None

    def test_json_serializable(self):
        event = generate_sensor_event("factory-alpha", "line-A1", "device-001")
        json_str = json.dumps(event)
        assert isinstance(json_str, str)

    def test_unique_event_ids(self):
        events = [
            generate_sensor_event("factory-alpha", "line-A1", "device-001")
            for _ in range(100)
        ]
        event_ids = [e["event_id"] for e in events]
        assert len(set(event_ids)) == 100


class TestGenerateQualityEvent:
    """Tests for quality event generation."""

    def test_required_fields_present(self):
        event = generate_quality_event("factory-alpha", "line-A1", "device-001")
        required_fields = [
            "event_id",
            "timestamp",
            "factory_id",
            "device_id",
            "line_id",
            "event_type",
            "pass_fail",
            "payload_reference",
            "content_type",
            "payload_size_bytes",
            "checksum_sha256",
        ]
        for field in required_fields:
            assert field in event, f"Missing field: {field}"

    def test_event_type_is_quality_type(self):
        event = generate_quality_event("factory-alpha", "line-A1", "device-001")
        assert event["event_type"] in [
            "INSPECTION",
            "MEASUREMENT",
            "DEFECT",
            "PASS",
        ]

    def test_payload_reference_format_when_present(self):
        # Generate many events to find one with payload
        for _ in range(100):
            event = generate_quality_event("factory-alpha", "line-A1", "device-001")
            if event["payload_reference"] is not None:
                assert event["payload_reference"].endswith(".jpg")
                assert "factory-alpha" in event["payload_reference"]
                assert event["content_type"] == "image/jpeg"
                assert event["payload_size_bytes"] > 0
                assert event["checksum_sha256"] is not None
                assert len(event["checksum_sha256"]) == 64  # SHA-256 hex
                return
        pytest.skip(
            "No payload reference generated in 100 attempts (statistically unlikely)"
        )

    def test_payload_size_within_range(self):
        for _ in range(100):
            event = generate_quality_event("factory-alpha", "line-A1", "device-001")
            if event["payload_size_bytes"] is not None:
                assert 5_000_000 <= event["payload_size_bytes"] <= 50_000_000
                return
        pytest.skip("No payload generated")


class TestGenerateStatusEvent:
    """Tests for equipment status event generation."""

    def test_required_fields_present(self):
        event = generate_status_event("factory-alpha", "line-A1", "device-001")
        assert "event_id" in event
        assert "timestamp" in event
        assert "equipment_state" in event

    def test_event_type_is_equipment_status(self):
        event = generate_status_event("factory-alpha", "line-A1", "device-001")
        assert event["event_type"] == "EQUIPMENT_STATUS"

    def test_equipment_state_is_valid(self):
        event = generate_status_event("factory-alpha", "line-A1", "device-001")
        assert event["equipment_state"] in [
            "running",
            "stopped",
            "maintenance",
            "warming_up",
        ]

    def test_no_payload_for_status_events(self):
        event = generate_status_event("factory-alpha", "line-A1", "device-001")
        assert event["payload_reference"] is None


class TestFactoryConfiguration:
    """Tests for factory/line configuration constants."""

    def test_factories_exist(self):
        assert len(FACTORIES) >= 2

    def test_all_factories_have_lines(self):
        for factory in FACTORIES:
            assert factory in LINES
            assert len(LINES[factory]) >= 1

    def test_all_sensor_types_have_units(self):
        for sensor in SENSOR_TYPES:
            assert sensor in SENSOR_UNITS


class TestEventSerialization:
    """Tests for JSON serialization compatibility."""

    def test_sensor_event_round_trip(self):
        event = generate_sensor_event("factory-alpha", "line-A1", "device-001")
        serialized = json.dumps(event)
        deserialized = json.loads(serialized)
        assert deserialized == event

    def test_quality_event_round_trip(self):
        event = generate_quality_event("factory-alpha", "line-A1", "device-001")
        serialized = json.dumps(event)
        deserialized = json.loads(serialized)
        assert deserialized == event

    def test_event_size_within_kafka_limit(self):
        """Events should be well under Kafka's 1MB message size limit."""
        event = generate_sensor_event("factory-alpha", "line-A1", "device-001")
        size = len(json.dumps(event).encode("utf-8"))
        assert size < 10_000  # Should be ~500 bytes; well under 1MB

from dataclasses import replace
import json
import unittest

from src.platform.audit import AuditEvent, AuditEventValidationError


class AuditEventContractTests(unittest.TestCase):
    def make_event(self, **overrides):
        values = {
            "event_id": "evt-001",
            "occurred_at": "2026-08-12T10:00:00+00:00",
            "event_type": "alert_suppressed",
            "request_id": "req-001",
            "actor": "operator:verified",
            "tenant": "tenant-a",
            "environment": "production",
            "outcome": "accepted",
            "details": {
                "comment": "approved by operator",
                "api_key": "api_key=do-not-store",
            },
        }
        values.update(overrides)
        return AuditEvent.create(**values)

    def test_event_is_redacted_deterministic_and_verifiable(self):
        event = self.make_event()

        self.assertTrue(event.verify())
        serialized = json.loads(event.serialize())
        digest = serialized.pop("digest")
        self.assertEqual(digest, event.digest)
        self.assertEqual(event, AuditEvent.create(**serialized))
        self.assertEqual(event.details["api_key"], "api_key=[REDACTED]")
        self.assertEqual(event.serialize(), event.serialize())

    def test_event_can_link_to_previous_digest(self):
        first = self.make_event()
        second = self.make_event(
            event_id="evt-002",
            request_id="req-002",
            previous_digest=first.digest,
        )

        self.assertTrue(second.verify())
        self.assertEqual(second.previous_digest, first.digest)

    def test_tampering_invalidates_event(self):
        event = self.make_event()
        tampered = replace(event, outcome="rejected")

        self.assertFalse(tampered.verify())
        with self.assertRaises(AuditEventValidationError):
            tampered.serialize()

    def test_timestamp_requires_timezone(self):
        with self.assertRaises(AuditEventValidationError):
            self.make_event(occurred_at="2026-08-12T10:00:00")

    def test_required_context_cannot_be_empty(self):
        with self.assertRaises(AuditEventValidationError):
            self.make_event(tenant="")

    def test_unsupported_detail_type_is_rejected(self):
        with self.assertRaises(AuditEventValidationError):
            self.make_event(details={"object": object()})


if __name__ == "__main__":
    unittest.main()

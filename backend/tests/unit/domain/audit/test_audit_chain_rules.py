from datetime import UTC, datetime

import pytest
from app.domain.audit.chain.rules import AuditChainRules, AuditEventPayload


def _payload() -> AuditEventPayload:
    return AuditEventPayload(
        organization_id="org-1",
        sequence_number=1,
        occurred_at=datetime(2026, 8, 14, 0, 0, 0, tzinfo=UTC),
        actor_user_id="user-1",
        action="JOURNAL_ENTRY_CREATED",
        resource_type="JournalEntry",
        resource_id="entry-1",
        previous_value=None,
        new_value={"status": "DRAFT", "entry_number": "OD-001"},
        context={"source": "api"},
        transaction_id="entry-1",
        request_id="request-1",
        previous_hash="0" * 64,
    )


def test_hash_is_deterministic_for_equivalent_structured_values() -> None:
    first = _payload()
    second = AuditEventPayload(
        **{
            **first.__dict__,
            "new_value": {"entry_number": "OD-001", "status": "DRAFT"},
        }
    )

    assert AuditChainRules.compute_hash(first) == AuditChainRules.compute_hash(second)


def test_canonical_json_is_sorted() -> None:
    assert AuditChainRules.canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


@pytest.mark.parametrize(
    ("action", "resource_type", "resource_id", "previous_hash"),
    [
        ("", "JournalEntry", "entry-1", "0" * 64),
        ("ACTION", "", "entry-1", "0" * 64),
        ("ACTION", "JournalEntry", "", "0" * 64),
        ("ACTION", "JournalEntry", "entry-1", "invalid"),
    ],
)
def test_append_validation_rejects_incomplete_or_invalid_chain_predecessor(
    action: str, resource_type: str, resource_id: str, previous_hash: str
) -> None:
    with pytest.raises(ValueError):
        AuditChainRules.validate_append(
            action, resource_type, resource_id, previous_hash
        )

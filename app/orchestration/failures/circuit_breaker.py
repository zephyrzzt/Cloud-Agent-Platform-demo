from __future__ import annotations

from dataclasses import dataclass

from app.orchestration.failures.ledger import FailureLedger
from app.orchestration.failures.models import FailureRecord


@dataclass(frozen=True)
class CircuitBreakerDecision:
    open: bool
    reason: str = ""


class FailureCircuitBreaker:
    def __init__(self, ledger: FailureLedger, threshold: int = 3) -> None:
        self.ledger = ledger
        self.threshold = threshold

    def record_and_check(self, record: FailureRecord) -> CircuitBreakerDecision:
        self.ledger.add(record)
        count = self.ledger.count_fingerprint(record.task_id, record.fingerprint)
        if count >= self.threshold:
            return CircuitBreakerDecision(
                open=True,
                reason=(
                    f"Failure fingerprint {record.fingerprint} repeated "
                    f"{count} times"
                ),
            )
        return CircuitBreakerDecision(open=False)

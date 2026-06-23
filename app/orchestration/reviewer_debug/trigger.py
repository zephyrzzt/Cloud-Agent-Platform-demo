from __future__ import annotations

from app.orchestration.failures.ledger import FailureLedger


class ReviewerDebugTrigger:
    def __init__(self, ledger: FailureLedger, threshold: int = 3) -> None:
        self.ledger = ledger
        self.threshold = threshold

    def should_trigger(self, task_id: str) -> tuple[bool, str]:
        repeated = self.ledger.repeated_failures(task_id, threshold=self.threshold)
        if repeated:
            return True, f"Repeated failure fingerprint: {repeated[0]}"
        return False, ""

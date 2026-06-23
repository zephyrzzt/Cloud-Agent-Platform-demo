from __future__ import annotations

from collections import Counter, defaultdict

from app.orchestration.failures.models import FailureRecord


class FailureLedger:
    def __init__(self) -> None:
        self._records: dict[str, list[FailureRecord]] = defaultdict(list)

    def add(self, record: FailureRecord) -> FailureRecord:
        self._records[record.task_id].append(record)
        return record

    def list_for_task(self, task_id: str) -> list[FailureRecord]:
        return list(self._records.get(task_id, []))

    def count_fingerprint(self, task_id: str, fingerprint: str) -> int:
        return sum(
            1
            for record in self._records.get(task_id, [])
            if record.fingerprint == fingerprint
        )

    def repeated_failures(
        self,
        task_id: str,
        *,
        threshold: int = 3,
    ) -> list[str]:
        counts = Counter(record.fingerprint for record in self._records.get(task_id, []))
        return [fingerprint for fingerprint, count in counts.items() if count >= threshold]

from __future__ import annotations

from dataclasses import dataclass

from app.context.file_buffer import FileBuffer
from app.context.lane import ContextLane


@dataclass(frozen=True)
class RecallResult:
    source: str
    content: str
    score: int


class RecallService:
    def search(
        self,
        query: str,
        *,
        lanes: list[ContextLane],
        file_buffer: FileBuffer | None = None,
        limit: int = 5,
    ) -> list[RecallResult]:
        terms = [term.lower() for term in query.split() if term.strip()]
        results: list[RecallResult] = []

        for lane in lanes:
            for entry in lane.entries:
                score = self._score(entry.content, terms)
                if score:
                    results.append(
                        RecallResult(source=f"lane:{lane.role}", content=entry.content, score=score)
                    )

        if file_buffer is not None:
            for item in file_buffer.list():
                content = file_buffer.read(item.id)
                score = self._score(content, terms)
                if score:
                    results.append(
                        RecallResult(source=f"file:{item.id}", content=content, score=score)
                    )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:limit]

    def _score(self, content: str, terms: list[str]) -> int:
        lower = content.lower()
        return sum(lower.count(term) for term in terms)

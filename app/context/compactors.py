from __future__ import annotations

from app.context.models import CompactionLevel, ContextEntry


class ContextCompactor:
    def compact(
        self,
        entries: list[ContextEntry],
        level: CompactionLevel,
    ) -> list[ContextEntry]:
        if level == CompactionLevel.NORMAL:
            return entries

        if level == CompactionLevel.LIGHT:
            return entries[-20:]

        if level == CompactionLevel.MEDIUM:
            return self._summarize(entries[:-10], keep=entries[-10:])

        return self._summarize(entries[:-5], keep=entries[-5:], max_summary_chars=1_000)

    def _summarize(
        self,
        old_entries: list[ContextEntry],
        *,
        keep: list[ContextEntry],
        max_summary_chars: int = 2_000,
    ) -> list[ContextEntry]:
        if not old_entries:
            return keep
        summary = "\n".join(f"- {entry.content[:200]}" for entry in old_entries)
        if len(summary) > max_summary_chars:
            summary = summary[:max_summary_chars] + "\n..."
        return [
            ContextEntry(
                role="summary",
                content=f"Compacted {len(old_entries)} entries:\n{summary}",
                metadata={"compacted_count": len(old_entries)},
            ),
            *keep,
        ]

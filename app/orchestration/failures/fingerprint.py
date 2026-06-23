from __future__ import annotations

import hashlib
import re


class FailureFingerprinter:
    def fingerprint(self, *, kind: str, message: str, source: str | None = None) -> str:
        normalized = self._normalize(message)
        raw = f"{kind}:{source or ''}:{normalized}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _normalize(self, value: str) -> str:
        value = re.sub(r"\b0x[0-9a-fA-F]+\b", "0xADDR", value)
        value = re.sub(r"\b\d+\b", "N", value)
        value = re.sub(r"\s+", " ", value).strip().lower()
        return value

# Failures

The failure package implements the first error feedback loop.

- `detectors.py`: converts failed tool results or text errors into failure records.
- `fingerprint.py`: creates stable fingerprints by normalizing volatile text.
- `ledger.py`: records failures per task.
- `circuit_breaker.py`: opens when the same fingerprint repeats too many times.

This gives later Developer and Reviewer stages structured feedback instead of raw logs only.

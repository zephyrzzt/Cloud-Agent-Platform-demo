from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse


class RepositoryPreparerError(RuntimeError):
    pass


class RepositoryValidationError(RepositoryPreparerError):
    pass


class RepositoryCloneError(RepositoryPreparerError):
    pass


REF_PATTERN = re.compile(r"^[A-Za-z0-9._/\-]+$")


@dataclass(frozen=True)
class RepositorySpec:
    url: str
    ref: str | None = None
    depth: int | None = 1
    access_token: str | None = None
    timeout_seconds: int = 120


@dataclass(frozen=True)
class PreparedRepository:
    repository_path: Path
    requested_url: str
    requested_ref: str | None
    resolved_commit: str | None


class RepositoryPreparer:
    def prepare(
        self,
        spec: RepositorySpec,
        destination: str | Path,
    ) -> PreparedRepository:
        destination_path = Path(destination).resolve()
        self.validate(spec)

        if destination_path.exists() and any(destination_path.iterdir()):
            raise RepositoryCloneError(
                f"Repository destination is not empty: {destination_path}"
            )

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        clone_url = self._url_with_token(spec.url, spec.access_token)
        command = ["git", "clone"]
        if spec.depth is not None:
            command.extend(["--depth", str(spec.depth)])
        command.extend([clone_url, str(destination_path)])

        self._run_git(command, timeout=spec.timeout_seconds)

        if spec.ref:
            self._run_git(
                ["git", "checkout", "--detach", spec.ref],
                cwd=destination_path,
                timeout=spec.timeout_seconds,
            )

        commit = self._current_commit(destination_path, spec.timeout_seconds)
        return PreparedRepository(
            repository_path=destination_path,
            requested_url=self._redact_url(spec.url),
            requested_ref=spec.ref,
            resolved_commit=commit,
        )

    def validate(self, spec: RepositorySpec) -> None:
        if not spec.url:
            raise RepositoryValidationError("Repository URL is required")

        parsed = urlparse(spec.url)
        is_local = Path(spec.url).expanduser().exists()
        is_supported_remote = parsed.scheme in {"https", "http", "ssh", "git", "file"}
        is_scp_like = re.match(r"^[^@\s]+@[^:\s]+:.+$", spec.url) is not None

        if not (is_local or is_supported_remote or is_scp_like):
            raise RepositoryValidationError(
                f"Unsupported repository URL: {self._redact_url(spec.url)}"
            )

        if spec.ref and not REF_PATTERN.fullmatch(spec.ref):
            raise RepositoryValidationError(
                "Repository ref contains unsupported characters"
            )

        if spec.depth is not None and spec.depth <= 0:
            raise RepositoryValidationError("Repository depth must be positive")

        if spec.timeout_seconds <= 0:
            raise RepositoryValidationError("Git timeout must be positive")

    def _run_git(
        self,
        command: list[str],
        *,
        cwd: str | Path | None = None,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_ASKPASS": "echo",
            }
        )
        try:
            return subprocess.run(
                command,
                cwd=cwd,
                env=env,
                timeout=timeout,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RepositoryCloneError("git executable was not found") from exc
        except subprocess.CalledProcessError as exc:
            stderr = self._redact_url(exc.stderr or "")
            raise RepositoryCloneError(stderr or "git command failed") from exc
        except subprocess.TimeoutExpired as exc:
            raise RepositoryCloneError("git command timed out") from exc

    def _current_commit(self, repository_path: Path, timeout: int) -> str | None:
        result = self._run_git(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_path,
            timeout=timeout,
        )
        commit = result.stdout.strip()
        return commit or None

    def _url_with_token(self, url: str, token: str | None) -> str:
        if not token:
            return url

        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"}:
            return url

        netloc = f"x-access-token:{token}@{parsed.netloc}"
        return urlunparse(parsed._replace(netloc=netloc))

    def _redact_url(self, value: str) -> str:
        return re.sub(r"(https?://)([^/@:\s]+):([^/@\s]+)@", r"\1***:***@", value)

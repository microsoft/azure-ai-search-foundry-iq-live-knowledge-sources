"""Azure AI Search data-plane operations for existing LiveKS lifecycles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

from ..config import ResolvedConfig


class SearchRequest(Protocol):
    def __call__(
        self,
        config: ResolvedConfig,
        token: str,
        *,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        api_version: str | None = None,
        headers: dict[str, str] | None = None,
        attempts: int = 3,
        timeout: int = 120,
        retry_mode: str = "auto",
    ) -> tuple[int, Any]: ...


@dataclass(frozen=True)
class SearchObjectSpec:
    resource_kind: str
    name: str
    api_version: str
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProviderResult:
    status_code: int
    payload: Any
    etag: str = ""
    reconciled: bool = False


def search_object_etag(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("@odata.etag") or payload.get("etag") or "")


def payload_is_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and payload_is_subset(value, actual[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(
                payload_is_subset(left, right)
                for left, right in zip(expected, actual)
            )
        )
    return expected == actual


def search_object_path(resource_kind: str, name: str) -> str:
    return f"/{resource_kind}/{quote(name, safe='')}"


class SearchDataPlaneOperations:
    """Execute Search object operations without lifecycle or ownership policy."""

    def __init__(
        self,
        config: ResolvedConfig,
        token: str,
        request: SearchRequest,
    ) -> None:
        self.config = config
        self.token = token
        self.request = request

    def _path(self, spec: SearchObjectSpec) -> str:
        return search_object_path(spec.resource_kind, spec.name)

    def read(self, spec: SearchObjectSpec, *, timeout: int = 30) -> ProviderResult:
        try:
            status_code, payload = self.request(
                self.config,
                self.token,
                method="GET",
                path=self._path(spec),
                api_version=spec.api_version,
                timeout=timeout,
            )
        except Exception:
            return ProviderResult(0, {})
        return ProviderResult(
            status_code,
            payload,
            etag=search_object_etag(payload),
        )

    def create(self, spec: SearchObjectSpec) -> ProviderResult:
        if spec.payload is None:
            raise ValueError("A create operation requires a payload.")
        try:
            status_code, payload = self.request(
                self.config,
                self.token,
                method="PUT",
                path=self._path(spec),
                api_version=spec.api_version,
                body=spec.payload,
                headers={
                    "If-None-Match": "*",
                    "Prefer": "return=representation",
                },
            )
        except Exception:
            status_code, payload = 0, {}

        ambiguous = status_code == 0 or status_code >= 500
        if ambiguous:
            reconciled = self.read(spec)
            if (
                reconciled.status_code == 200
                and payload_is_subset(spec.payload, reconciled.payload)
            ):
                return ProviderResult(
                    200,
                    reconciled.payload,
                    etag=reconciled.etag,
                    reconciled=True,
                )
            return ProviderResult(status_code, payload)

        etag = search_object_etag(payload)
        if status_code in {200, 201} and not etag:
            reconciled = self.read(spec)
            if (
                reconciled.status_code == 200
                and payload_is_subset(spec.payload, reconciled.payload)
            ):
                return ProviderResult(
                    status_code,
                    reconciled.payload,
                    etag=reconciled.etag,
                )
        return ProviderResult(status_code, payload, etag=etag)

    def retrieve(
        self,
        knowledge_base: SearchObjectSpec,
        body: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> ProviderResult:
        try:
            status_code, payload = self.request(
                self.config,
                self.token,
                method="POST",
                path=f"{self._path(knowledge_base)}/retrieve",
                api_version=knowledge_base.api_version,
                body=body,
                headers=headers,
                attempts=3,
                retry_mode="read",
            )
        except Exception:
            return ProviderResult(0, {})
        return ProviderResult(status_code, payload)

    def delete(self, spec: SearchObjectSpec, *, etag: str) -> ProviderResult:
        if not etag:
            raise ValueError("A delete operation requires an authorized ETag.")
        try:
            status_code, payload = self.request(
                self.config,
                self.token,
                method="DELETE",
                path=self._path(spec),
                api_version=spec.api_version,
                headers={"If-Match": etag},
                attempts=3,
                retry_mode="conditional-write",
                timeout=60,
            )
        except Exception:
            return ProviderResult(0, {})
        return ProviderResult(status_code, payload)

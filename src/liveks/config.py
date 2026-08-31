"""Canonical YAML configuration loading and validation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "config/schema.yaml"
PROFILES_DIR = ROOT / "profiles"
ZERO_GUID_RE = re.compile(r"^0{8}-0{4}-0{4}-0{4}-0{11}[0-9a-fA-F]$")
GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigError(ValueError):
    """Raised when authored configuration is unsafe or invalid."""


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigError(f"Invalid YAML in {path}: {error}") from error
    if not isinstance(data, dict):
        raise ConfigError(f"Expected a YAML mapping in {path}.")
    return data


def flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict) and not (set(value) == {"env"}):
            result.update(flatten(value, path))
        else:
            result[path] = value
    return result


def unflatten(values: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path, value in sorted(values.items()):
        current = result
        parts = path.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return result


def is_placeholder(value: Any) -> bool:
    if value is None or value == "":
        return True
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return (
        not stripped
        or (stripped.startswith("<") and stripped.endswith(">"))
        or bool(ZERO_GUID_RE.fullmatch(stripped))
    )


def parse_legacy_env(path: Path) -> dict[str, str]:
    """Parse dotenv-style values without evaluating shell syntax."""
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigError(f"Invalid env assignment at {path}:{line_number}.")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not KEY_RE.fullmatch(key):
            raise ConfigError(f"Invalid env key at {path}:{line_number}: {key}")
        try:
            parts = shlex.split(raw_value, comments=True, posix=True)
        except ValueError as error:
            raise ConfigError(f"Invalid quoted env value at {path}:{line_number}: {error}") from error
        if len(parts) > 1:
            raise ConfigError(f"Env values containing spaces must be quoted at {path}:{line_number}.")
        values[key] = parts[0] if parts else ""
    return values


def _validate_field(path: str, value: Any, spec: dict[str, Any]) -> Any:
    field_type = spec.get("type", "string")
    if is_placeholder(value):
        if spec.get("optional"):
            return ""
        return value
    if field_type in {"string", "path"}:
        if not isinstance(value, str):
            raise ConfigError(f"{path} must be a string.")
        return value
    if field_type == "string_list":
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ConfigError(f"{path} must be a list of non-empty strings.")
        if len(value) != len(set(value)):
            raise ConfigError(f"{path} must not contain duplicate values.")
        return value
    if field_type == "guid":
        if not isinstance(value, str) or not GUID_RE.fullmatch(value):
            raise ConfigError(f"{path} must be a GUID.")
        return value
    if field_type == "https_url":
        if not isinstance(value, str):
            raise ConfigError(f"{path} must be an HTTPS URL.")
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ConfigError(f"{path} must be an absolute HTTPS URL.")
        return value.rstrip("/")
    if field_type == "azure_search_url":
        if not isinstance(value, str):
            raise ConfigError(f"{path} must be an Azure AI Search HTTPS endpoint.")
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower()
        trusted_suffix = ".search.windows.net"
        try:
            port = parsed.port
        except ValueError as error:
            raise ConfigError(f"{path} must be a trusted Azure AI Search service endpoint.") from error
        if (
            parsed.scheme != "https"
            or not hostname.endswith(trusted_suffix)
            or parsed.username
            or parsed.password
            or port not in {None, 443}
            or parsed.path not in {"", "/"}
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise ConfigError(f"{path} must be a trusted Azure AI Search service endpoint.")
        return value.rstrip("/")
    if field_type == "azure_openai_url":
        if not isinstance(value, str):
            raise ConfigError(f"{path} must be an Azure OpenAI HTTPS endpoint.")
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower()
        try:
            port = parsed.port
        except ValueError as error:
            raise ConfigError(f"{path} must be a trusted Azure OpenAI endpoint.") from error
        if (
            parsed.scheme != "https"
            or not hostname.endswith(".openai.azure.com")
            or parsed.username
            or parsed.password
            or port not in {None, 443}
            or parsed.path not in {"", "/"}
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise ConfigError(f"{path} must be a trusted Azure OpenAI endpoint.")
        return value.rstrip("/")
    if field_type == "enum":
        if value not in spec.get("values", []):
            allowed = ", ".join(map(str, spec.get("values", [])))
            raise ConfigError(f"{path} must be one of: {allowed}.")
        return value
    if field_type == "integer":
        if isinstance(value, bool):
            raise ConfigError(f"{path} must be an integer.")
        try:
            converted = int(value)
        except (TypeError, ValueError) as error:
            raise ConfigError(f"{path} must be an integer.") from error
        if converted < int(spec.get("minimum", converted)):
            raise ConfigError(f"{path} must be at least {spec['minimum']}.")
        return converted
    if field_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false", "1", "0"}:
            return value.lower() in {"true", "1"}
        raise ConfigError(f"{path} must be a boolean.")
    if field_type == "secret_ref":
        if not isinstance(value, dict) or set(value) != {"env"} or not KEY_RE.fullmatch(str(value.get("env", ""))):
            raise ConfigError(f"{path} must use an environment reference such as {{env: SECRET_NAME}}.")
        return {"env": str(value["env"])}
    raise ConfigError(f"Unsupported schema type for {path}: {field_type}")


def _serialize_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


@dataclass
class ResolvedConfig:
    profile: str
    environment: str
    values: dict[str, Any]
    sources: dict[str, str]
    schema: dict[str, Any]
    manifest: dict[str, Any]
    config_path: Path | None = None
    secret_values: dict[str, str] = field(default_factory=dict)

    def get(self, path: str, default: Any = "") -> Any:
        return self.values.get(path, default)

    @property
    def root(self) -> Path:
        return ROOT

    @property
    def config_digest(self) -> str:
        payload = {
            "schemaVersion": 2,
            "profile": self.profile,
            "environment": self.environment,
            "values": self.redacted_flat(),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    @property
    def lock_path(self) -> Path:
        return ROOT / ".liveks" / f"{self.environment}.lock.json"

    def redacted_flat(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        fields = self.schema["fields"]
        for path, value in self.values.items():
            result[path] = {"env": value["env"], "resolved": False} if fields[path].get("secret") else value
        return result

    def nested(self, *, redact: bool = True) -> dict[str, Any]:
        return unflatten(self.redacted_flat() if redact else self.values)

    def azd_values(self) -> dict[str, str]:
        result = {
            "AZURE_ENV_NAME": self.environment,
            "AZURE_RESOURCE_GROUP": str(self.get("azure.resource_group")),
            "AZURE_NAME_SALT": str(self.get("azure.name_salt")),
        }
        for path, spec in self.schema["fields"].items():
            azd_name = spec.get("azd")
            value = self.values.get(path)
            if not azd_name or spec.get("secret") or is_placeholder(value):
                continue
            result[azd_name] = _serialize_value(value)
        return result

    def child_env(self, *, include_secrets: bool = True) -> dict[str, str]:
        result = dict(os.environ)
        result.update(self.azd_values())
        cli_dir = str(self.get("azure.cli_config_dir", ""))
        if cli_dir:
            result["AZURE_CONFIG_DIR"] = str(Path(cli_dir).expanduser())
        if include_secrets:
            for path, value in self.secret_values.items():
                env_name = self.schema["fields"][path].get("env")
                if env_name and value:
                    result[env_name] = value
            for path, value in self.values.items():
                if self.schema["fields"][path].get("secret") and isinstance(value, dict):
                    env_name = value["env"]
                    if os.environ.get(env_name):
                        result[env_name] = os.environ[env_name]
        return result

    def ownership(self) -> dict[str, str]:
        fabric_mode = self.get("fabric.mode")
        ownership = {
            "azure": "none" if self.profile == "offline" else "create",
            "fabricCapacity": "create" if fabric_mode == "create" else "reuse" if fabric_mode == "byo" else "none",
            "fabricWorkspace": "create" if fabric_mode == "create" else "reuse" if fabric_mode == "byo" else "none",
            "fabricOntology": "create" if fabric_mode == "create" else "reuse" if fabric_mode == "byo" else "none",
        }
        if self.profile in {"search-index", "mcp-search-index"}:
            ownership.update(
                {
                    "azure": "reuse",
                    "searchService": "reuse",
                    "searchIndex": "reuse",
                    "azureOpenAI": "reuse" if self.profile == "mcp-search-index" else "none",
                    "knowledgeSources": "create",
                    "knowledgeBases": "create",
                }
            )
        return ownership


def available_profiles() -> list[str]:
    names: list[str] = []
    for path in sorted(PROFILES_DIR.glob("*.yaml")):
        data = load_yaml(path)
        if data.get("kind", "deployment") == "deployment":
            names.append(str(data.get("profile", path.stem)))
    preferred = ["offline", "search-index", "mcp-search-index", "mcp-only", "byo-fabric", "full"]
    return [name for name in preferred if name in names] + sorted(set(names) - set(preferred))


def resolve_config(
    *,
    profile: str | None,
    environment: str | None,
    config_path: Path | None = None,
    legacy_env_path: Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> ResolvedConfig:
    schema = load_yaml(SCHEMA_PATH)
    authored: dict[str, Any] = {}
    if config_path:
        if not config_path.exists():
            raise ConfigError(f"Config file not found: {config_path}")
        authored = load_yaml(config_path)
        if authored.get("version") != 2:
            raise ConfigError(f"{config_path} must declare version: 2.")
        profile = profile or str(authored.get("profile", ""))
        environment = environment or str(authored.get("environment", ""))
        if profile and authored.get("profile") and profile != authored["profile"]:
            raise ConfigError("CLI profile does not match the YAML profile.")
        if environment and authored.get("environment") and environment != authored["environment"]:
            raise ConfigError("CLI environment does not match the YAML environment.")
    if not profile:
        profile = "offline"
    if profile not in available_profiles():
        raise ConfigError(f"Unknown deployment profile: {profile}")
    if not environment:
        environment = "offline" if profile == "offline" else ""
    env_pattern = re.compile(str(schema["environment_pattern"]))
    if not environment or not env_pattern.fullmatch(environment):
        raise ConfigError("Environment must start with a letter and contain 3-63 letters, numbers, or hyphens.")

    manifest_path = PROFILES_DIR / f"{profile}.yaml"
    manifest = load_yaml(manifest_path)
    if manifest.get("kind") != "deployment" or manifest.get("schema_version") != 2:
        raise ConfigError(f"Profile is not an executable v2 deployment profile: {manifest_path}")

    fields: dict[str, dict[str, Any]] = schema["fields"]
    values = flatten(manifest.get("defaults", {}))
    sources = {path: f"profile:{profile}" for path in values}
    secret_values: dict[str, str] = {}

    if legacy_env_path:
        if not legacy_env_path.exists():
            raise ConfigError(f"Legacy env file not found: {legacy_env_path}")
        for env_name, raw_value in parse_legacy_env(legacy_env_path).items():
            path = schema.get("legacy_env", {}).get(env_name)
            if not path:
                continue
            if fields[path].get("secret"):
                if raw_value and not is_placeholder(raw_value):
                    secret_values[path] = raw_value
                    values[path] = {"env": env_name}
            else:
                values[path] = raw_value
            sources[path] = f"legacy-env:{legacy_env_path.name}"

    if authored:
        payload = {key: value for key, value in authored.items() if key not in {"version", "profile", "environment"}}
        for path, value in flatten(payload).items():
            values[path] = value
            sources[path] = f"config:{config_path.name if config_path else 'inline'}"

    for path, value in (overrides or {}).items():
        values[path] = value
        sources[path] = "cli-compatibility-override"

    values.setdefault("azure.resource_group", f"rg-{environment}")
    sources.setdefault("azure.resource_group", "derived")
    values.setdefault("azure.name_salt", environment)
    sources.setdefault("azure.name_salt", "derived")
    if profile == "full":
        compact = re.sub(r"[^a-z0-9]", "", environment.lower())
        values.setdefault("fabric.capacity_name", f"fab{compact}"[:63])
        values.setdefault("fabric.capacity_resource_group", f"rg-{environment}-fabric")
        sources.setdefault("fabric.capacity_name", "derived")
        sources.setdefault("fabric.capacity_resource_group", "derived")
    if profile in {"search-index", "mcp-search-index"}:
        if is_placeholder(values.get("search.index_knowledge_source_name")):
            values["search.index_knowledge_source_name"] = f"{environment.lower()}-search-index-ks"
            sources["search.index_knowledge_source_name"] = "derived"
    if profile == "search-index":
        if is_placeholder(values.get("search.index_knowledge_base_name")):
            values["search.index_knowledge_base_name"] = f"{environment.lower()}-search-index-kb"
            sources["search.index_knowledge_base_name"] = "derived"
    if profile == "mcp-search-index":
        if is_placeholder(values.get("search.mcp_knowledge_source_name")):
            values["search.mcp_knowledge_source_name"] = f"{environment.lower()}-mcp-server-ks"
            sources["search.mcp_knowledge_source_name"] = "derived"
        if is_placeholder(values.get("search.combined_knowledge_base_name")):
            values["search.combined_knowledge_base_name"] = f"{environment.lower()}-combined-kb"
            sources["search.combined_knowledge_base_name"] = "derived"

    unknown = sorted(set(values) - set(fields))
    if unknown:
        raise ConfigError("Unknown configuration fields: " + ", ".join(unknown))
    for path in list(values):
        values[path] = _validate_field(path, values[path], fields[path])
    missing = [path for path in manifest.get("required", []) if is_placeholder(values.get(path))]
    if missing:
        raise ConfigError("Missing required configuration: " + ", ".join(missing))
    mode = values.get("deployment.mode")
    if mode != profile:
        raise ConfigError(f"deployment.mode={mode!r} does not match profile={profile!r}.")
    api_version = values.get("search.api_version")
    if profile == "search-index" and api_version != "2026-04-01":
        raise ConfigError("search-index profile requires the generally available 2026-04-01 API contract.")
    if profile in {"mcp-only", "byo-fabric", "full"} and api_version != "2026-05-01-preview":
        raise ConfigError(f"{profile} profile requires the 2026-05-01-preview API contract.")
    if profile == "mcp-search-index":
        if values.get("search.index_api_version") != "2026-04-01":
            raise ConfigError("mcp-search-index requires Search Index KS API version 2026-04-01.")
        if values.get("search.preview_api_version") != "2026-05-01-preview":
            raise ConfigError("mcp-search-index requires MCP Server KS and Knowledge Base API version 2026-05-01-preview.")
        managed_names = [
            str(values.get("search.index_knowledge_source_name")),
            str(values.get("search.mcp_knowledge_source_name")),
            str(values.get("search.combined_knowledge_base_name")),
        ]
        if len(set(managed_names)) != len(managed_names):
            raise ConfigError("mcp-search-index generated Knowledge Source and Knowledge Base names must be distinct.")
    if profile == "full" and (values.get("fabric.workspace_id") or values.get("fabric.ontology_id")):
        raise ConfigError("full profile must not include BYO Fabric IDs; use byo-fabric instead.")

    return ResolvedConfig(
        profile=profile,
        environment=environment,
        values=values,
        sources=sources,
        schema=schema,
        manifest=manifest,
        config_path=config_path,
        secret_values=secret_values,
    )


def write_user_config(path: Path, *, profile: str, environment: str) -> None:
    if path.exists():
        raise ConfigError(f"Config already exists: {path}")
    data: dict[str, Any] = {"version": 2, "profile": profile, "environment": environment}
    if profile == "byo-fabric":
        data["fabric"] = {"workspace_id": "", "ontology_id": "", "user_search_token": {"env": "FABRIC_USER_SEARCH_TOKEN"}}
    elif profile == "full":
        data["fabric"] = {"mode": "create", "location": "westus3"}
    elif profile == "mcp-only":
        data["azure"] = {"location": "eastus"}
    elif profile == "search-index":
        data["search"] = {
            "endpoint": "",
            "index_name": "",
            "semantic_configuration_name": "",
            "search_fields": [],
            "source_data_fields": [],
        }
    elif profile == "mcp-search-index":
        data["search"] = {
            "endpoint": "",
            "index_name": "",
            "semantic_configuration_name": "",
            "search_fields": [],
            "source_data_fields": [],
        }
        data["openai"] = {
            "endpoint": "",
            "deployment_name": "",
            "model_name": "",
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    path.chmod(0o600)


def write_lock(config: ResolvedConfig, *, status: str, extra: dict[str, Any] | None = None) -> Path:
    payload: dict[str, Any] = {
        "schemaVersion": 2,
        "status": status,
        "profile": config.profile,
        "environment": config.environment,
        "configDigest": config.config_digest,
        "configPath": str(config.config_path) if config.config_path else None,
        "resolvedConfig": config.nested(),
        "sources": config.sources,
        "ownership": config.ownership(),
    }
    if extra:
        payload.update(extra)
    config.lock_path.parent.mkdir(parents=True, exist_ok=True)
    config.lock_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    config.lock_path.chmod(0o600)
    return config.lock_path


def find_config(environment: str | None, explicit: Path | None) -> Path | None:
    if explicit:
        return explicit
    if environment:
        candidate = ROOT / ".liveks" / f"{environment}.yaml"
        if candidate.exists():
            return candidate
    return None


def profile_table(profiles: Iterable[str] | None = None) -> list[dict[str, Any]]:
    rows = []
    for name in profiles or available_profiles():
        manifest = load_yaml(PROFILES_DIR / f"{name}.yaml")
        rows.append(
            {
                "profile": name,
                "purpose": manifest.get("purpose", ""),
                "estimatedDuration": manifest.get("estimated_duration", ""),
                "cost": manifest.get("cost", ""),
            }
        )
    return rows

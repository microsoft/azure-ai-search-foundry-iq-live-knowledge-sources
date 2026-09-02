"""Strict, credential-free scenario pack loading and replay evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from .evidence import generated_at, repository_revision, runtime_summary, write_json


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "config/scenario-pack-schema.json"
PACKS_DIR = ROOT / "scenario-packs"
CATALOG_PATH = ROOT / "docs/18-scenario-packs.md"
CATALOG_START = "<!-- scenario-catalog:start -->"
CATALOG_END = "<!-- scenario-catalog:end -->"
GUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
SENSITIVE_KEY_RE = re.compile(
    r"(?:^|_)(?:api_?key|bearer|connection_?string|credential|endpoint|password|"
    r"secret|subscription_?id|tenant_?id|token|workspace_?id|ontology_?id)(?:$|_)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_RE = re.compile(
    r"(?:\bBearer\s+[A-Za-z0-9._~-]+|AccountKey=|SharedAccessSignature=|"
    r"https://[^/\s]+(?:\.search\.windows\.net|\.openai\.azure\.com))",
    re.IGNORECASE,
)


class ScenarioError(ValueError):
    """Raised when a scenario pack or replay violates its contract."""


def scenario_file_sha256(path: Path) -> str:
    """Hash structured text with canonical LF endings across Git platforms."""
    payload = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ScenarioError(f"{label} not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ScenarioError(f"Invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise ScenarioError(f"{path} must contain a JSON object.")
    return value


def load_schema(root: Path = ROOT) -> dict[str, Any]:
    schema = _load_json(root / "config/scenario-pack-schema.json", "Scenario schema")
    if schema.get("schemaVersion") != 1:
        raise ScenarioError("config/scenario-pack-schema.json must declare schemaVersion 1.")
    return schema


def _check_fields(
    value: Any,
    section: str,
    schema: dict[str, Any],
    location: str,
) -> list[str]:
    if not isinstance(value, dict):
        return [f"{location} must be an object"]
    allowed = set(schema["fields"][section])
    required = set(schema["required"][section])
    unknown = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    failures = []
    if unknown:
        failures.append(f"{location} has unknown fields: {', '.join(unknown)}")
    if missing:
        failures.append(f"{location} is missing fields: {', '.join(missing)}")
    return failures


def _safe_path(
    root: Path,
    raw_path: str,
    *,
    location: str,
    prefixes: tuple[str, ...],
    require_file: bool = True,
) -> Path:
    pure = PurePosixPath(raw_path)
    if (
        not raw_path
        or pure.is_absolute()
        or ".." in pure.parts
        or "\\" in raw_path
        or not raw_path.startswith(prefixes)
    ):
        raise ScenarioError(
            f"{location} must be a repository-relative path under {', '.join(prefixes)}."
        )
    candidate = root / raw_path
    try:
        resolved = candidate.resolve(strict=True)
        resolved_relative = resolved.relative_to(root.resolve()).as_posix()
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        raise ScenarioError(f"{location} escapes the repository or is missing: {raw_path}") from error
    if not resolved_relative.startswith(prefixes):
        raise ScenarioError(
            f"{location} resolves outside the allowed path prefixes: {raw_path}"
        )
    if require_file and not resolved.is_file():
        raise ScenarioError(f"{location} must reference a file: {raw_path}")
    if not require_file and not resolved.is_dir():
        raise ScenarioError(f"{location} must reference a directory: {raw_path}")
    return resolved


def _scan_public_values(value: Any, location: str, failures: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                failures.append(f"{location}.{key} uses a sensitive or tenant-specific field name")
            _scan_public_values(child, f"{location}.{key}", failures)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _scan_public_values(child, f"{location}[{index}]", failures)
        return
    if isinstance(value, str):
        if GUID_RE.search(value):
            failures.append(f"{location} contains a tenant-shaped identifier")
        if SENSITIVE_VALUE_RE.search(value):
            failures.append(f"{location} contains a credential or private-service-shaped value")


def _manifest_paths(root: Path) -> list[Path]:
    pack_root = root / "scenario-packs"
    paths = sorted(pack_root.glob("*/manifest.json"))
    for path in paths:
        try:
            path.resolve(strict=True).relative_to(pack_root.resolve())
        except (FileNotFoundError, RuntimeError, ValueError) as error:
            raise ScenarioError(
                f"Scenario manifest escapes scenario-packs through a symlink: {path}"
            ) from error
    return paths


def _validate_manifest_shape(
    manifest: dict[str, Any],
    schema: dict[str, Any],
    relative_path: str,
) -> list[str]:
    failures = _check_fields(manifest, "root", schema, relative_path)
    if failures:
        return failures
    if manifest.get("schemaVersion") != schema["manifestSchemaVersion"]:
        failures.append(
            f"{relative_path} schemaVersion must be {schema['manifestSchemaVersion']}"
        )
    pack = manifest.get("pack")
    failures.extend(_check_fields(pack, "pack", schema, f"{relative_path}.pack"))
    if not isinstance(pack, dict):
        return failures
    optional_contract = pack.get("domainContract")
    if optional_contract is not None:
        failures.extend(
            _check_fields(
                optional_contract,
                "domainContract",
                schema,
                f"{relative_path}.pack.domainContract",
            )
        )
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        failures.append(f"{relative_path}.cases must be a non-empty list")
        return failures
    for index, case in enumerate(cases):
        case_location = f"{relative_path}.cases[{index}]"
        failures.extend(_check_fields(case, "case", schema, case_location))
        if not isinstance(case, dict):
            continue
        failures.extend(
            _check_fields(case.get("fixture"), "fixture", schema, f"{case_location}.fixture")
        )
        sources = case.get("expectedSources")
        if not isinstance(sources, list) or not sources:
            failures.append(f"{case_location}.expectedSources must be a non-empty list")
        else:
            for source_index, source in enumerate(sources):
                failures.extend(
                    _check_fields(
                        source,
                        "source",
                        schema,
                        f"{case_location}.expectedSources[{source_index}]",
                    )
                )
        failures.extend(
            _check_fields(
                case.get("protectedLive"),
                "protectedLive",
                schema,
                f"{case_location}.protectedLive",
            )
        )
        assertions = case.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            failures.append(f"{case_location}.assertions must be a non-empty list")
        else:
            for assertion_index, assertion in enumerate(assertions):
                failures.extend(
                    _check_fields(
                        assertion,
                        "assertion",
                        schema,
                        f"{case_location}.assertions[{assertion_index}]",
                    )
                )
    return failures


def _profile_ownership_class(ownership: dict[str, str]) -> tuple[str, str]:
    azure = ownership.get("azure")
    fabric = ownership.get("fabricWorkspace")
    if azure == "none":
        return "no-resources", "none"
    if azure == "reuse":
        return (
            "reused-azure-generated-search-objects",
            "delete-generated-search-objects-preserve-reused-assets",
        )
    if fabric == "reuse":
        return (
            "generated-azure-reused-fabric",
            "delete-generated-azure-preserve-reused-fabric",
        )
    if fabric == "create":
        return "generated-azure-and-fabric", "delete-generated-azure-and-fabric"
    return "generated-azure", "delete-generated-azure"


def _camel_to_plural_snake(value: str) -> str:
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()
    return snake[:-1] + "ies" if snake.endswith("y") else snake + "s"


def _data_digest(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(folder.glob("*.csv")):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def _validate_domain_contract(
    root: Path,
    pack: dict[str, Any],
    cases: list[dict[str, Any]],
) -> list[str]:
    contract = pack.get("domainContract")
    if contract is None:
        return []
    failures: list[str] = []
    path = _safe_path(
        root,
        str(contract["path"]),
        location=f"pack {pack['id']} domainContract.path",
        prefixes=("samples/ontology/",),
    )
    actual_digest = scenario_file_sha256(path)
    if actual_digest != contract["sha256"]:
        failures.append(
            f"pack {pack['id']} ontology digest is stale: expected "
            f"{contract['sha256']}, found {actual_digest}"
        )
        return failures
    try:
        import yaml
    except ModuleNotFoundError as error:
        raise ScenarioError(
            "PyYAML is required for deep scenario validation; run ./liveks bootstrap."
        ) from error
    ontology = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(ontology, dict):
        return [f"{contract['path']} must contain a YAML object"]
    source_folder = _safe_path(
        root,
        str(ontology.get("source_data", {}).get("folder", "")),
        location=f"pack {pack['id']} ontology source_data.folder",
        prefixes=("samples/data/",),
        require_file=False,
    )
    actual_data_digest = _data_digest(source_folder)
    if actual_data_digest != contract["dataDigest"]:
        failures.append(
            f"pack {pack['id']} data digest is stale: expected "
            f"{contract['dataDigest']}, found {actual_data_digest}"
        )
    expected_counts = ontology.get("source_data", {}).get("expected_counts", {})
    entities = ontology.get("entities", {})
    for entity_name, entity in entities.items() if isinstance(entities, dict) else []:
        if not isinstance(entity, dict):
            continue
        source = source_folder / str(entity.get("source", ""))
        count_key = _camel_to_plural_snake(str(entity_name))
        if count_key not in expected_counts or not source.is_file():
            failures.append(
                f"{contract['path']} must bind entity {entity_name} to an expected CSV count"
            )
            continue
        with source.open(encoding="utf-8", newline="") as handle:
            actual_count = sum(1 for _ in csv.DictReader(handle))
        if actual_count != expected_counts[count_key]:
            failures.append(
                f"{source.relative_to(root).as_posix()} row count must be "
                f"{expected_counts[count_key]}, found {actual_count}"
            )
    validation_queries = ontology.get("validation_queries", [])
    for case in cases:
        matching = [
            item
            for item in validation_queries
            if isinstance(item, dict) and item.get("query") == case["syntheticQuery"]
        ]
        if not matching:
            failures.append(
                f"scenario {case['id']} syntheticQuery is not declared by {contract['path']}"
            )
            continue
        expected_top = matching[0].get("expected_top_entity")
        if expected_top and expected_top not in case["expectedTerms"]:
            failures.append(
                f"scenario {case['id']} expectedTerms must include ontology top entity"
            )
    return failures


def _profile_source_contract(
    profile: str,
    manifest: dict[str, Any],
) -> tuple[set[str], set[str], set[str], dict[str, str]]:
    defaults = manifest.get("defaults", {})
    search = defaults.get("search", {})
    fabric = defaults.get("fabric", {})
    source_types: set[str] = set()
    source_names: set[str] = set()
    if profile in {"search-index", "mcp-search-index", "three-source"}:
        source_types.add("searchIndex")
    if search.get("mcp_knowledge_source_name") is not None or profile in {"mcp-search-index", "three-source"}:
        source_types.add("mcpServer")
        if search.get("mcp_knowledge_source_name"):
            source_names.add(str(search["mcp_knowledge_source_name"]))
    if fabric.get("mode") in {"byo", "create"}:
        source_types.add("fabricOntology")
        if search.get("fabric_knowledge_source_name"):
            source_names.add(str(search["fabric_knowledge_source_name"]))
    api_versions = {
        str(value)
        for key, value in search.items()
        if key in {"api_version", "index_api_version", "preview_api_version"} and value
    }
    from .config import ownership_for_profile

    ownership = ownership_for_profile(profile, str(fabric.get("mode", "skip")))
    return source_types, source_names, api_versions, ownership


def _validate_case_bindings(
    root: Path,
    case: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    try:
        import yaml
    except ModuleNotFoundError as error:
        raise ScenarioError(
            "PyYAML is required for deep scenario validation; run ./liveks bootstrap."
        ) from error
    failures: list[str] = []
    profile_path = root / "profiles" / f"{case['profile']}.yaml"
    if not profile_path.is_file():
        return [f"scenario {case['id']} references unknown deployment profile {case['profile']}"]
    profile_manifest = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(profile_manifest, dict) or profile_manifest.get("kind") != "deployment":
        return [f"scenario {case['id']} profile {case['profile']} is not a deployment profile"]
    source_types, source_names, api_versions, ownership = _profile_source_contract(
        case["profile"],
        profile_manifest,
    )
    expected_types = {source["type"] for source in case["expectedSources"]}
    if not expected_types.issubset(source_types):
        failures.append(
            f"scenario {case['id']} sources {sorted(expected_types - source_types)} "
            f"are incompatible with profile {case['profile']}"
        )
    expected_names = {source["identity"] for source in case["expectedSources"]}
    if source_names and not expected_names.issubset(source_names):
        failures.append(
            f"scenario {case['id']} source identities must match profile defaults"
        )
    if set(case["apiVersions"]) != api_versions:
        failures.append(
            f"scenario {case['id']} apiVersions must match profile pins "
            f"{sorted(api_versions)}"
        )
    compatibility = yaml.safe_load(
        (root / "config/compatibility.yaml").read_text(encoding="utf-8")
    )
    pinned_versions = {
        str(item["version"])
        for item in compatibility.get("api_contracts", {}).values()
    }
    if not set(case["apiVersions"]).issubset(pinned_versions):
        failures.append(
            f"scenario {case['id']} uses an API version outside config/compatibility.yaml"
        )
    actual_class, actual_cleanup = _profile_ownership_class(ownership)
    if case["ownershipClass"] != actual_class:
        failures.append(
            f"scenario {case['id']} ownershipClass must be {actual_class} "
            f"for profile {case['profile']}"
        )
    if case["cleanupExpectation"] != actual_cleanup:
        failures.append(
            f"scenario {case['id']} cleanupExpectation must be {actual_cleanup} "
            f"for ownership class {actual_class}"
        )
    protected = case["protectedLive"]
    if protected["supported"] is not False or protected["adapter"] != "none":
        failures.append(
            f"scenario {case['id']} protected live adapter is not implemented; "
            "declare supported=false and adapter=none"
        )
    return failures


def _validate_expected_routes(
    root: Path,
    cases: dict[str, dict[str, Any]],
) -> list[str]:
    try:
        import yaml
    except ModuleNotFoundError as error:
        raise ScenarioError(
            "PyYAML is required for deep scenario validation; run ./liveks bootstrap."
        ) from error
    path = root / "evals/expected_routes.yaml"
    try:
        routes = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as error:
        raise ScenarioError(f"Expected-route authority could not be read: {error}") from error
    if not isinstance(routes, list):
        return ["evals/expected_routes.yaml must contain a route list"]
    by_query = {
        route.get("query"): route
        for route in routes
        if isinstance(route, dict) and isinstance(route.get("query"), str)
    }
    failures: list[str] = []
    for case in cases.values():
        route = by_query.get(case["syntheticQuery"])
        if not isinstance(route, dict):
            failures.append(
                f"scenario {case['id']} syntheticQuery is missing from evals/expected_routes.yaml"
            )
            continue
        route_sources = set(route.get("expected_knowledge_sources", []))
        if route.get("expected_knowledge_source"):
            route_sources.add(str(route["expected_knowledge_source"]))
        manifest_sources = {source["identity"] for source in case["expectedSources"]}
        if route_sources != manifest_sources:
            failures.append(
                f"scenario {case['id']} source identities drifted from evals/expected_routes.yaml"
            )
    return failures


def load_registry(root: Path = ROOT, *, deep: bool = False) -> dict[str, Any]:
    schema = load_schema(root)
    failures: list[str] = []
    packs: list[dict[str, Any]] = []
    cases: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    id_re = re.compile(schema["patterns"]["id"])
    version_re = re.compile(schema["patterns"]["version"])
    sha_re = re.compile(schema["patterns"]["sha256"])
    allowed_source_types = set(schema["values"]["sourceTypes"])
    allowed_assertion_kinds = set(schema["values"]["assertionKinds"])
    required_assertion_kinds = set(schema["values"]["requiredAssertionKinds"])
    allowed_ownership_classes = set(schema["values"]["ownershipClasses"])
    allowed_cleanup_expectations = set(schema["values"]["cleanupExpectations"])
    allowed_protected_adapters = set(schema["values"]["protectedLiveAdapters"])

    paths = _manifest_paths(root)
    if not paths:
        raise ScenarioError("No scenario pack manifests found under scenario-packs/*/manifest.json.")
    for path in paths:
        relative_path = path.relative_to(root).as_posix()
        manifest = _load_json(path, "Scenario manifest")
        shape_failures = _validate_manifest_shape(manifest, schema, relative_path)
        failures.extend(shape_failures)
        if shape_failures:
            continue
        public_failures: list[str] = []
        _scan_public_values(manifest, relative_path, public_failures)
        failures.extend(public_failures)
        pack = manifest["pack"]
        if not id_re.fullmatch(str(pack["id"])):
            failures.append(f"{relative_path}.pack.id is not a stable lowercase identifier")
        if not version_re.fullmatch(str(pack["version"])):
            failures.append(f"{relative_path}.pack.version must be semantic MAJOR.MINOR.PATCH")
        if pack["synthetic"] is not True:
            failures.append(f"{relative_path}.pack.synthetic must be true")
        contract = pack.get("domainContract")
        if contract:
            if not sha_re.fullmatch(str(contract["sha256"])):
                failures.append(f"{relative_path}.pack.domainContract.sha256 is invalid")
            if not sha_re.fullmatch(str(contract["dataDigest"])):
                failures.append(f"{relative_path}.pack.domainContract.dataDigest is invalid")
        enriched_pack = {
            **pack,
            "manifestPath": relative_path,
            "manifestSha256": scenario_file_sha256(path),
        }
        if any(existing["id"] == pack["id"] for existing in packs):
            failures.append(f"duplicate scenario pack id: {pack['id']}")
        packs.append(enriched_pack)
        pack_cases: list[dict[str, Any]] = []
        for case in manifest["cases"]:
            case_id = str(case["id"])
            if not id_re.fullmatch(case_id) or not case_id.startswith(f"{pack['id']}."):
                failures.append(
                    f"scenario id {case_id!r} must be stable and start with {pack['id']}."
                )
            if case_id in cases:
                failures.append(f"duplicate scenario id: {case_id}")
            fixture = case["fixture"]
            fixture_path = _safe_path(
                root,
                str(fixture["path"]),
                location=f"scenario {case_id} fixture.path",
                prefixes=("samples/responses/",),
            )
            actual_fixture_digest = scenario_file_sha256(fixture_path)
            if not sha_re.fullmatch(str(fixture["sha256"])):
                failures.append(f"scenario {case_id} fixture.sha256 is invalid")
            elif actual_fixture_digest != fixture["sha256"]:
                failures.append(
                    f"scenario {case_id} fixture digest is stale: expected "
                    f"{fixture['sha256']}, found {actual_fixture_digest}"
                )
            expected_terms = case["expectedTerms"]
            if (
                not isinstance(expected_terms, list)
                or not expected_terms
                or any(not isinstance(term, str) or not term.strip() for term in expected_terms)
            ):
                failures.append(f"scenario {case_id} expectedTerms must be non-empty public strings")
            sources = case["expectedSources"]
            source_keys: set[tuple[str, str]] = set()
            for source in sources:
                source_type = source.get("type")
                identity = source.get("identity")
                if source_type not in allowed_source_types:
                    failures.append(f"scenario {case_id} has unknown source type {source_type!r}")
                key = (str(source_type), str(identity))
                if key in source_keys:
                    failures.append(f"scenario {case_id} has duplicate expected source {key!r}")
                source_keys.add(key)
                if not id_re.fullmatch(str(identity)):
                    failures.append(f"scenario {case_id} source identity {identity!r} is invalid")
                if any(source.get(field) is not True for field in ("activity", "references", "sourceData")):
                    failures.append(
                        f"scenario {case_id} source {source_type} must require activity, references, and sourceData"
                    )
            assertions = case["assertions"]
            assertion_ids = [str(assertion["id"]) for assertion in assertions]
            assertion_kinds = [str(assertion["kind"]) for assertion in assertions]
            if len(assertion_ids) != len(set(assertion_ids)):
                failures.append(f"scenario {case_id} has duplicate assertion ids")
            if any(not id_re.fullmatch(value) for value in assertion_ids):
                failures.append(f"scenario {case_id} assertion ids must be stable identifiers")
            if set(assertion_kinds) != required_assertion_kinds or any(
                kind not in allowed_assertion_kinds for kind in assertion_kinds
            ):
                failures.append(
                    f"scenario {case_id} assertions must contain exactly "
                    f"{sorted(required_assertion_kinds)}"
                )
            if case["ownershipClass"] not in allowed_ownership_classes:
                failures.append(
                    f"scenario {case_id} has unknown ownershipClass "
                    f"{case['ownershipClass']!r}"
                )
            if case["cleanupExpectation"] not in allowed_cleanup_expectations:
                failures.append(
                    f"scenario {case_id} has unknown cleanupExpectation "
                    f"{case['cleanupExpectation']!r}"
                )
            if case["protectedLive"]["adapter"] not in allowed_protected_adapters:
                failures.append(
                    f"scenario {case_id} has unknown protectedLive adapter "
                    f"{case['protectedLive']['adapter']!r}"
                )
            case_aliases = case["aliases"]
            if (
                not isinstance(case_aliases, list)
                or not case_aliases
                or any(not id_re.fullmatch(str(alias)) for alias in case_aliases)
            ):
                failures.append(f"scenario {case_id} aliases must be stable identifiers")
            enriched_case = {
                **case,
                "packId": pack["id"],
                "packVersion": pack["version"],
                "manifestPath": relative_path,
                "manifestSha256": scenario_file_sha256(path),
                "fixturePath": fixture_path,
            }
            cases[case_id] = enriched_case
            pack_cases.append(enriched_case)
            for alias in case_aliases:
                alias_value = str(alias)
                if alias_value in aliases or alias_value in cases:
                    failures.append(f"duplicate scenario alias: {alias_value}")
                else:
                    aliases[alias_value] = case_id
            if deep:
                failures.extend(_validate_case_bindings(root, case, schema))
        if deep:
            failures.extend(_validate_domain_contract(root, pack, pack_cases))

    alias_id_collisions = sorted(set(cases) & set(aliases))
    if alias_id_collisions:
        failures.append(
            "scenario aliases must not duplicate scenario IDs: "
            + ", ".join(alias_id_collisions)
        )
    if failures:
        raise ScenarioError("Scenario pack validation failed:\n- " + "\n- ".join(failures))
    if deep:
        route_failures = _validate_expected_routes(root, cases)
        if route_failures:
            raise ScenarioError(
                "Scenario pack validation failed:\n- " + "\n- ".join(route_failures)
            )
    return {
        "schemaVersion": schema["manifestSchemaVersion"],
        "packs": sorted(packs, key=lambda item: item["id"]),
        "cases": dict(sorted(cases.items())),
        "aliases": dict(sorted(aliases.items())),
    }


def resolve_case(selector: str, registry: dict[str, Any]) -> dict[str, Any]:
    case_id = registry["aliases"].get(selector, selector)
    case = registry["cases"].get(case_id)
    if case is None:
        choices = sorted(set(registry["cases"]) | set(registry["aliases"]))
        raise ScenarioError(
            f"Unknown scenario {selector!r}. Use one of: {', '.join(choices)}."
        )
    return case


def _answer_text(response: dict[str, Any]) -> str:
    for message in response.get("response", []):
        if not isinstance(message, dict):
            continue
        for content in message.get("content", []):
            if isinstance(content, dict) and content.get("type") == "text" and content.get("text"):
                return str(content["text"])
    return ""


def _typed_items(response: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = response.get(field)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _assertion_message(kind: str, passed: bool) -> str:
    messages = {
        "answerTerms": "Known non-sensitive facts matched the replay contract.",
        "activityTypes": "Activity contains every declared source type.",
        "referenceTypes": "References contain every declared source type.",
        "sourceContract": "Source identity and sourceData evidence satisfy the declared contract.",
    }
    if passed:
        return messages[kind]
    return {
        "answerTerms": "Known-fact evidence did not satisfy the replay contract.",
        "activityTypes": "Activity source-type evidence did not satisfy the replay contract.",
        "referenceTypes": "Reference source-type evidence did not satisfy the replay contract.",
        "sourceContract": "Source identity or sourceData evidence did not satisfy the replay contract.",
    }[kind]


def run_case(
    selector: str,
    *,
    root: Path = ROOT,
    fixture_override: Path | None = None,
) -> dict[str, Any]:
    registry = load_registry(root, deep=False)
    case = resolve_case(selector, registry)
    fixture_path = fixture_override or case["fixturePath"]
    try:
        response = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ScenarioError(f"Scenario fixture could not be read: {error}") from error
    if not isinstance(response, dict):
        raise ScenarioError("Scenario fixture must contain a JSON object.")
    answer = _answer_text(response)
    activity = _typed_items(response, "activity")
    references = _typed_items(response, "references")
    activity_types = {str(item.get("type")) for item in activity if item.get("type")}
    reference_types = {str(item.get("type")) for item in references if item.get("type")}
    expected_types = {source["type"] for source in case["expectedSources"]}
    expected_pairs = {
        (source["type"], source["identity"])
        for source in case["expectedSources"]
    }
    observed_pairs = {
        (str(item.get("type")), str(item.get("knowledgeSourceName")))
        for item in activity + references
        if item.get("type") and item.get("knowledgeSourceName")
    }
    source_data_pairs = {
        (str(item.get("type")), str(item.get("knowledgeSourceName")))
        for item in references
        if item.get("type")
        and item.get("knowledgeSourceName")
        and isinstance(item.get("sourceData"), dict)
        and bool(item["sourceData"])
    }
    matched_terms = sum(
        1 for term in case["expectedTerms"] if term.casefold() in answer.casefold()
    )
    outcomes = {
        "answerTerms": matched_terms == len(case["expectedTerms"]),
        "activityTypes": expected_types.issubset(activity_types),
        "referenceTypes": expected_types.issubset(reference_types),
        "sourceContract": expected_pairs.issubset(observed_pairs)
        and expected_pairs.issubset(source_data_pairs),
    }
    checks = [
        {
            "id": assertion["id"],
            "kind": assertion["kind"],
            "status": "pass" if outcomes[assertion["kind"]] else "fail",
            "message": _assertion_message(
                assertion["kind"],
                outcomes[assertion["kind"]],
            ),
        }
        for assertion in case["assertions"]
    ]
    status = "fail" if any(check["status"] == "fail" for check in checks) else "pass"
    source_names = sorted(
        {
            str(item["knowledgeSourceName"])
            for item in activity + references
            if item.get("knowledgeSourceName")
        }
    )
    return {
        "schemaVersion": 1,
        "command": "scenario-run",
        "status": status,
        "mode": "offline-replay",
        "selector": selector,
        "scenarioId": case["id"],
        "scenarioVersion": case["packVersion"],
        "packId": case["packId"],
        "packVersion": case["packVersion"],
        "profile": case["profile"],
        "manifestPath": case["manifestPath"],
        "manifestSha256": case["manifestSha256"],
        "fixturePath": case["fixture"]["path"],
        "fixtureSha256": scenario_file_sha256(fixture_path),
        "sourceTypes": sorted(activity_types | reference_types),
        "sourceNames": source_names,
        "activityCount": len(activity),
        "referenceCount": len(references),
        "sourceDataCount": len(source_data_pairs),
        "expectedTermCount": len(case["expectedTerms"]),
        "matchedExpectedTermCount": matched_terms,
        "checks": checks,
        "ownershipClass": case["ownershipClass"],
        "cleanupExpectation": case["cleanupExpectation"],
        "protectedLive": case["protectedLive"],
        "answer": answer,
        "response": response,
    }


def safe_run_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "command": "scenarios run",
        "status": report["status"],
        "mode": report["mode"],
        "scenario": {
            "id": report["scenarioId"],
            "version": report["scenarioVersion"],
            "packId": report["packId"],
            "packVersion": report["packVersion"],
        },
        "profile": report["profile"],
        "evidence": {
            "sourceTypes": report["sourceTypes"],
            "activityCount": report["activityCount"],
            "referenceCount": report["referenceCount"],
            "sourceDataCount": report["sourceDataCount"],
        },
        "assertions": [
            {
                "id": check["id"],
                "kind": check["kind"],
                "status": check["status"],
                "message": check["message"],
            }
            for check in report["checks"]
        ],
        "ownershipClass": report["ownershipClass"],
        "cleanupExpectation": report["cleanupExpectation"],
        "protectedLive": {
            "supported": report["protectedLive"]["supported"],
            "status": "not-run",
        },
        "privacy": {
            "answerIncluded": False,
            "queryIncluded": False,
            "expectedTermsIncluded": False,
            "sourceDataIncluded": False,
            "sourceIdentitiesIncluded": False,
            "endpointsIncluded": False,
            "tenantValuesIncluded": False,
            "credentialsIncluded": False,
        },
    }


def build_evidence_capsule(report: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    return {
        "schemaVersion": 2,
        "kind": "liveks-evidence-capsule",
        "scope": "offline-scenario-replay",
        "status": report["status"],
        "generatedAt": generated_at(),
        "repositoryRevision": repository_revision(root),
        "scenario": {
            "id": report["scenarioId"],
            "version": report["scenarioVersion"],
            "packId": report["packId"],
            "packVersion": report["packVersion"],
        },
        "manifest": {
            "path": report["manifestPath"],
            "sha256": report["manifestSha256"],
        },
        "fixture": {
            "path": report["fixturePath"],
            "sha256": report["fixtureSha256"],
        },
        "profile": report["profile"],
        "mode": report["mode"],
        "networkCalls": 0,
        "runtime": runtime_summary(),
        "evidence": {
            "sourceTypes": report["sourceTypes"],
            "activityCount": report["activityCount"],
            "referenceCount": report["referenceCount"],
            "sourceDataCount": report["sourceDataCount"],
        },
        "assertions": [
            {"id": check["id"], "status": check["status"]}
            for check in report["checks"]
        ],
        "ownershipClass": report["ownershipClass"],
        "cleanupExpectation": report["cleanupExpectation"],
        "protectedLive": {
            "supported": report["protectedLive"]["supported"],
            "status": "not-run",
        },
        "privacy": {
            "answerIncluded": False,
            "queryIncluded": False,
            "expectedTermsIncluded": False,
            "rawResponseIncluded": False,
            "sourceDataIncluded": False,
            "sourceIdentitiesIncluded": False,
            "resourceIdentifiersIncluded": False,
            "serviceEndpointsIncluded": False,
            "tenantValuesIncluded": False,
            "credentialsIncluded": False,
        },
    }


def list_report(registry: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "id": case["id"],
            "version": case["packVersion"],
            "packId": case["packId"],
            "aliases": case["aliases"],
            "title": case["title"],
            "profile": case["profile"],
            "sourceTypes": sorted(source["type"] for source in case["expectedSources"]),
        }
        for case in registry["cases"].values()
    ]
    return {
        "schemaVersion": 1,
        "command": "scenarios list",
        "status": "pass",
        "scenarios": rows,
    }


def inspect_report(selector: str, registry: dict[str, Any]) -> dict[str, Any]:
    case = resolve_case(selector, registry)
    return {
        "schemaVersion": 1,
        "command": "scenarios inspect",
        "status": "pass",
        "scenario": {
            "id": case["id"],
            "version": case["packVersion"],
            "packId": case["packId"],
            "aliases": case["aliases"],
            "title": case["title"],
            "description": case["description"],
            "profile": case["profile"],
            "fixture": {
                "path": case["fixture"]["path"],
                "sha256": case["fixture"]["sha256"],
            },
            "sourceTypes": sorted(source["type"] for source in case["expectedSources"]),
            "apiVersions": case["apiVersions"],
            "assertionIds": [item["id"] for item in case["assertions"]],
            "ownershipClass": case["ownershipClass"],
            "cleanupExpectation": case["cleanupExpectation"],
            "protectedLive": case["protectedLive"],
        },
        "privacy": {
            "queryIncluded": False,
            "expectedTermsIncluded": False,
            "sourceIdentitiesIncluded": False,
        },
    }


def validate_all(root: Path = ROOT, *, run_all: bool = False) -> dict[str, Any]:
    registry = load_registry(root, deep=True)
    results = []
    if run_all:
        for case_id in registry["cases"]:
            report = run_case(case_id, root=root)
            results.append(
                {
                    "scenarioId": case_id,
                    "status": report["status"],
                    "assertions": [
                        {"id": item["id"], "status": item["status"]}
                        for item in report["checks"]
                    ],
                }
            )
    status = "fail" if any(item["status"] == "fail" for item in results) else "pass"
    return {
        "schemaVersion": 1,
        "command": "scenarios validate",
        "status": status,
        "packCount": len(registry["packs"]),
        "scenarioCount": len(registry["cases"]),
        "networkCalls": 0,
        "runs": results,
    }


def render_catalog(registry: dict[str, Any]) -> str:
    lines = [
        "## Checked-In Catalog",
        "",
        "| Scenario ID | Version | Legacy aliases | Profile | Expected source types | Protected live |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in registry["cases"].values():
        source_types = ", ".join(
            f"`{source}`"
            for source in sorted(item["type"] for item in case["expectedSources"])
        )
        aliases = ", ".join(f"`{alias}`" for alias in case["aliases"])
        protected = "supported" if case["protectedLive"]["supported"] else "not implemented"
        lines.append(
            f"| `{case['id']}` | `{case['packVersion']}` | {aliases} | "
            f"`{case['profile']}` | {source_types} | {protected} |"
        )
    lines.extend(
        [
            "",
            "All checked-in cases are synthetic. Ordinary validation runs every case with zero network calls.",
        ]
    )
    return "\n".join(lines)


def catalog_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.count(CATALOG_START) != 1 or text.count(CATALOG_END) != 1:
        raise ScenarioError(
            f"{path.relative_to(ROOT)} must contain one scenario catalog marker pair."
        )
    return text.split(CATALOG_START, 1)[1].split(CATALOG_END, 1)[0].strip()


def write_catalog(registry: dict[str, Any], path: Path = CATALOG_PATH) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(CATALOG_START) != 1 or text.count(CATALOG_END) != 1:
        raise ScenarioError(
            f"{path.relative_to(ROOT)} must contain one scenario catalog marker pair."
        )
    before, remainder = text.split(CATALOG_START, 1)
    _, after = remainder.split(CATALOG_END, 1)
    path.write_text(
        f"{before}{CATALOG_START}\n{render_catalog(registry)}\n{CATALOG_END}{after}",
        encoding="utf-8",
    )


def check_catalog(registry: dict[str, Any], path: Path = CATALOG_PATH) -> None:
    if catalog_text(path) != render_catalog(registry):
        raise ScenarioError(
            "docs/18-scenario-packs.md catalog is stale; "
            "run ./liveks scenarios catalog --write."
        )


def _emit_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _emit_text(value: dict[str, Any]) -> None:
    command = value["command"]
    print(f"LiveKS {command}: {str(value['status']).upper()}")
    if value["status"] == "fail" and "checks" in value:
        for check in value["checks"]:
            print(f"[FAIL] {check['id']}: {check['message']}")
        return
    if command == "scenarios list":
        for item in value["scenarios"]:
            print(
                f"{item['id']} ({item['version']}): {item['title']} "
                f"[aliases: {', '.join(item['aliases'])}]"
            )
    elif command == "scenarios inspect":
        scenario = value["scenario"]
        print(f"Scenario: {scenario['id']} ({scenario['version']})")
        print(f"Profile: {scenario['profile']}")
        print(f"Sources: {', '.join(scenario['sourceTypes'])}")
        print(f"Cleanup: {scenario['cleanupExpectation']}")
        print("Protected live: NOT RUN")
    elif command == "scenarios validate":
        print(f"Packs: {value['packCount']}; scenarios: {value['scenarioCount']}")
        for run in value["runs"]:
            print(f"[{run['status'].upper()}] {run['scenarioId']}")
    elif command == "scenarios run":
        scenario = value["scenario"]
        print(f"Scenario: {scenario['id']} ({scenario['version']})")
        for assertion in value["assertions"]:
            print(
                f"[{assertion['status'].upper()}] {assertion['id']}: "
                f"{assertion['message']}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List, inspect, validate, and replay scenario packs.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("list", "validate"):
        child = subparsers.add_parser(command)
        child.add_argument("--format", choices=["text", "json"], default="text")
        if command == "validate":
            child.add_argument("--run-all", action="store_true")
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("scenario")
    inspect_parser.add_argument("--format", choices=["text", "json"], default="text")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("scenario")
    run_parser.add_argument("--format", choices=["text", "json"], default="text")
    run_parser.add_argument("--evidence-out", type=Path)
    catalog_parser = subparsers.add_parser("catalog")
    catalog_mode = catalog_parser.add_mutually_exclusive_group(required=True)
    catalog_mode.add_argument("--check", action="store_true")
    catalog_mode.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    try:
        registry = load_registry(ROOT, deep=args.command in {"validate", "catalog"})
        if args.command == "list":
            report = list_report(registry)
        elif args.command == "inspect":
            report = inspect_report(args.scenario, registry)
        elif args.command == "validate":
            report = validate_all(ROOT, run_all=args.run_all)
        elif args.command == "run":
            internal = run_case(args.scenario, root=ROOT)
            if args.evidence_out:
                write_json(args.evidence_out, build_evidence_capsule(internal))
            report = safe_run_report(internal)
        elif args.command == "catalog":
            if args.write:
                write_catalog(registry)
            else:
                check_catalog(registry)
            print("Scenario catalog: PASS")
            return 0
        else:
            raise ScenarioError(f"Unsupported scenario command: {args.command}")
        if args.format == "json":
            _emit_json(report)
        else:
            _emit_text(report)
        return 0 if report["status"] == "pass" else 1
    except (KeyError, OSError, ScenarioError, TypeError, ValueError) as error:
        report = {
            "schemaVersion": 1,
            "command": f"scenarios {getattr(args, 'command', 'unknown')}",
            "status": "fail",
            "checks": [
                {
                    "id": "scenario-configuration",
                    "status": "fail",
                    "message": str(error),
                }
            ],
        }
        if getattr(args, "format", "text") == "json":
            _emit_json(report)
        else:
            _emit_text(report)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

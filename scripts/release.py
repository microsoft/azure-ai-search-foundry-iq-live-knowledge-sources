#!/usr/bin/env python3
"""Validate and build the deterministic, non-publishing product release contract."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "config/release.json"
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
ACTION_RE = re.compile(
    r"^\s*uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-f]{40})\s+#\s+(v[0-9][A-Za-z0-9_.-]*)\s*$"
)


class ReleaseError(ValueError):
    """Raised when release inputs or generated artifacts violate the contract."""


def load_release(path: Path = RELEASE_PATH) -> dict[str, Any]:
    try:
        release = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ReleaseError(f"Release authority not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ReleaseError(f"Invalid release authority JSON in {path}: {error}") from error
    if not isinstance(release, dict) or release.get("schemaVersion") != 1:
        raise ReleaseError(f"{path} must be a schemaVersion 1 JSON object.")
    return release


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ReleaseError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def artifact_names(release: dict[str, Any]) -> dict[str, str]:
    product = release["product"]
    values = {"slug": product["slug"], "version": product["version"]}
    return {
        key: str(template).format(**values)
        for key, template in release["artifacts"].items()
    }


def workflow_on(workflow: dict[str, Any]) -> Any:
    return workflow.get("on", workflow.get(True))


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ReleaseError(f"Invalid workflow YAML in {path}: {error}") from error
    if not isinstance(value, dict):
        raise ReleaseError(f"{path} must contain a YAML mapping.")
    return value


def validate_action_pins(path: Path, policy: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    allowed_owners = {str(owner).casefold() for owner in policy["allowedActionOwners"]}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if "uses:" not in raw_line:
            continue
        match = ACTION_RE.fullmatch(raw_line)
        if not match:
            failures.append(
                f"{path.as_posix()}:{line_number} action must use a verified 40-character commit SHA "
                "and a version comment, for example owner/action@<sha> # v1"
            )
            continue
        action, commit_sha, _ = match.groups()
        owner = action.split("/", 1)[0].casefold()
        if owner not in allowed_owners:
            failures.append(f"{path.as_posix()}:{line_number} action owner {owner!r} is not allowlisted")
        if not SHA40_RE.fullmatch(commit_sha):
            failures.append(f"{path.as_posix()}:{line_number} action commit is not lowercase hexadecimal")
    return failures


def validate_workflow_policy(root: Path, release: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    policy = release["workflowPolicy"]
    declared = policy["workflows"]
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in (root / ".github/workflows").glob("*.yml")
    } | {
        path.relative_to(root).as_posix()
        for path in (root / ".github/workflows").glob("*.yaml")
    }
    if actual_paths != set(declared):
        failures.append(
            "workflow policy must declare every workflow; "
            f"missing={sorted(actual_paths - set(declared))}, stale={sorted(set(declared) - actual_paths)}"
        )

    oidc_jobs: set[str] = set()
    for relative_path, expected in declared.items():
        path = root / relative_path
        if not path.is_file():
            failures.append(f"declared workflow is missing: {relative_path}")
            continue
        workflow = load_yaml(path)
        if workflow.get("permissions") != expected["permissions"]:
            failures.append(
                f"{relative_path} top-level permissions must be {expected['permissions']!r}"
            )
        concurrency = workflow.get("concurrency")
        if not isinstance(concurrency, dict):
            failures.append(f"{relative_path} must define concurrency")
        else:
            if concurrency.get("group") != expected["concurrencyGroup"]:
                failures.append(
                    f"{relative_path} concurrency group must be {expected['concurrencyGroup']!r}"
                )
            if concurrency.get("cancel-in-progress") != expected["cancelInProgress"]:
                failures.append(
                    f"{relative_path} cancel-in-progress must be {expected['cancelInProgress']!r}"
                )

        jobs = workflow.get("jobs", {})
        expected_job_permissions = expected.get("jobPermissions", {})
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            actual_permissions = job.get("permissions")
            expected_permissions = expected_job_permissions.get(job_name)
            if expected_permissions is not None and actual_permissions != expected_permissions:
                failures.append(
                    f"{relative_path} job {job_name} permissions must be {expected_permissions!r}"
                )
            if expected_permissions is None and actual_permissions is not None:
                failures.append(
                    f"{relative_path} job {job_name} has undeclared permission override {actual_permissions!r}"
                )
            effective_permissions = actual_permissions or workflow.get("permissions", {})
            if effective_permissions.get("id-token") == "write":
                oidc_jobs.add(f"{relative_path}:{job_name}")

            for step in job.get("steps", []):
                if not isinstance(step, dict):
                    continue
                uses = str(step.get("uses", ""))
                if uses.startswith(("actions/upload-artifact@", "actions/upload-pages-artifact@")):
                    retention = step.get("with", {}).get("retention-days")
                    maximum = int(policy["maximumArtifactRetentionDays"])
                    if not isinstance(retention, int) or retention < 1 or retention > maximum:
                        failures.append(
                            f"{relative_path} job {job_name} artifact retention-days "
                            f"must be an integer from 1 to {maximum}"
                        )

        failures.extend(validate_action_pins(path, policy))

    if oidc_jobs != set(policy["oidcJobs"]):
        failures.append(
            "id-token: write must be limited to declared jobs; "
            f"expected={sorted(policy['oidcJobs'])}, actual={sorted(oidc_jobs)}"
        )

    protected_path = root / ".github/workflows/protected-mcp-search-index.yml"
    protected_text = protected_path.read_text(encoding="utf-8")
    if "cancel-in-progress: false" not in protected_text:
        failures.append("protected canary concurrency must remain non-cancelling for cleanup safety")
    repository = release["product"]["repository"]
    if f"github.repository == '{repository}'" not in protected_text:
        failures.append("protected canary must guard the exact microsoft repository")
    if "azure/login@" not in protected_text:
        failures.append("protected canary must retain its Azure OIDC login")

    pages = load_yaml(root / ".github/workflows/pages.yml")
    build_permissions = pages["jobs"]["build"].get("permissions", pages["permissions"])
    if build_permissions != {"contents": "read"}:
        failures.append("Pages build job must have contents: read only")
    if any(
        str(step.get("uses", "")).startswith("actions/configure-pages@")
        for step in pages["jobs"]["build"].get("steps", [])
        if isinstance(step, dict)
    ):
        failures.append("Pages configuration must run only in the permission-scoped deploy job")

    release_path = root / ".github/workflows/release.yml"
    if release_path.is_file():
        release_text = release_path.read_text(encoding="utf-8")
        release_workflow = load_yaml(release_path)
        triggers = workflow_on(release_workflow)
        if not isinstance(triggers, dict) or "pull_request" not in triggers or "push" not in triggers:
            failures.append("release workflow must dry-run on pull_request and publish only from a tag push")
        guard = release["workflowPolicy"]["releaseGuard"]
        required_fragments = (
            f"github.repository == '{guard['repository']}'",
            f"github.event_name == '{guard['event']}'",
            f"startsWith(github.ref, '{guard['refPrefix']}')",
            "python scripts/release.py verify-tag",
            "actions/attest-build-provenance@",
            "gh release create",
        )
        for fragment in required_fragments:
            if fragment not in release_text:
                failures.append(f".github/workflows/release.yml missing trusted publish guard: {fragment}")
        if "pull_request_target" in release_text:
            failures.append("release workflow must not use pull_request_target")
        if "secrets." in release_text:
            failures.append("release workflow must use GITHUB_TOKEN/OIDC and no long-lived release secret")

    for path in actual_paths:
        text = (root / path).read_text(encoding="utf-8")
        if "azure/login@" in text and path != ".github/workflows/protected-mcp-search-index.yml":
            failures.append(f"Azure OIDC login is allowed only in the protected canary, found in {path}")
    return failures


def path_is_forbidden(path: str, archive: dict[str, Any]) -> bool:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or "\\" in path:
        return True
    if path in archive["forbiddenNames"] or pure.name in archive["forbiddenNames"]:
        return True
    if any(path.startswith(prefix) for prefix in archive["forbiddenPrefixes"]):
        return True
    if any(segment in archive["forbiddenSegments"] for segment in pure.parts):
        return True
    if any(pure.name.endswith(suffix) for suffix in archive["forbiddenSuffixes"]):
        return True
    if "raw-response" in pure.name or "/raw/" in f"/{path}/":
        return True
    if "responses" in pure.parts and not path.startswith(archive["allowedSyntheticResponsePrefix"]):
        return True
    return False


def validate_archive_policy(release: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    archive = release["archive"]
    for key in ("includeExact", "includePrefixes", "excludeExact", "excludePrefixes"):
        values = archive.get(key)
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            failures.append(f"archive.{key} must be a list of paths")
    for path in archive.get("includeExact", []):
        if path_is_forbidden(path, archive):
            failures.append(f"archive includeExact contains forbidden path: {path}")
    for prefix in archive.get("includePrefixes", []):
        if not prefix.endswith("/") or path_is_forbidden(prefix + "placeholder", archive):
            failures.append(f"archive includePrefixes contains unsafe prefix: {prefix}")
    return failures


def validate_release_contract(root: Path, release: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    product = release.get("product", {})
    version = str(product.get("version", ""))
    if not SEMVER_RE.fullmatch(version):
        failures.append(f"product.version must be a conservative MAJOR.MINOR.PATCH value, found {version!r}")
    if product.get("tag") != f"v{version}":
        failures.append(f"product.tag must be v{version}")
    if product.get("status") not in {"unreleased", "ready"}:
        failures.append("product.status must be unreleased or ready")
    if product.get("status") == "ready" and not product.get("releaseDate"):
        failures.append("a ready product release must set product.releaseDate")

    names = artifact_names(release)
    if len(set(names.values())) != len(names):
        failures.append("release artifact names must be distinct")
    for key, name in names.items():
        if key == "archiveRoot":
            continue
        if "/" in name or "\\" in name or name.startswith("."):
            failures.append(f"artifacts.{key} must be a safe filename, found {name!r}")

    bindings = release["bindings"]
    changelog = root / bindings["changelog"]["path"]
    notes = root / bindings["releaseNotes"]["path"]
    if not changelog.is_file():
        failures.append(f"release changelog is missing: {changelog.relative_to(root).as_posix()}")
    elif bindings["changelog"]["heading"] not in changelog.read_text(encoding="utf-8"):
        failures.append(
            f"{bindings['changelog']['path']} must contain heading "
            f"{bindings['changelog']['heading']!r}"
        )
    if not notes.is_file():
        failures.append(f"release notes are missing: {bindings['releaseNotes']['path']}")
    else:
        notes_text = notes.read_text(encoding="utf-8")
        if not notes_text.startswith(bindings["releaseNotes"]["heading"] + "\n"):
            failures.append(
                f"{bindings['releaseNotes']['path']} must start with "
                f"{bindings['releaseNotes']['heading']!r}"
            )
        for required in (product["tag"], *(name for key, name in names.items() if key != "archiveRoot")):
            if required not in notes_text:
                failures.append(
                    f"{bindings['releaseNotes']['path']} must name release value {required!r}"
                )

    azure_yaml = load_yaml(root / bindings["azdTemplate"]["path"])
    actual_template = azure_yaml.get("metadata", {}).get("template")
    expected_template = bindings["azdTemplate"]["valueTemplate"].format(version=version)
    if actual_template != expected_template:
        failures.append(
            f"{bindings['azdTemplate']['path']} metadata.template must be "
            f"{expected_template!r}"
        )
    if not str(actual_template).endswith(f"@{version}"):
        failures.append("azd template metadata must end with the product version")

    init_text = (root / "src/liveks/__init__.py").read_text(encoding="utf-8")
    if "config/release.json" not in init_text or re.search(r'__version__\s*=\s*["\']', init_text):
        failures.append("src/liveks/__init__.py must read product version only from config/release.json")

    for component in release["independentComponents"]:
        path = root / component["path"]
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as error:
            failures.append(f"independent component metadata is invalid at {component['path']}: {error}")
            continue
        if component.get("private") is True and package.get("private") is not True:
            failures.append(f"{component['path']} must remain private component metadata")

    requirement = release["sbom"]["validator"]
    requirements_path = root / "requirements-release.txt"
    requirements = {
        line.strip()
        for line in requirements_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    } if requirements_path.is_file() else set()
    if requirement not in requirements:
        failures.append(f"requirements-release.txt must pin the SBOM validator {requirement}")

    compatibility_path = root / bindings["compatibility"]["path"]
    if not compatibility_path.is_file():
        failures.append(f"compatibility authority is missing: {bindings['compatibility']['path']}")

    walkthrough = release["history"]["walkthroughRelease"]
    if walkthrough != {
        "tag": "walkthrough-v1",
        "kind": "media-documentation",
        "preserve": True,
    }:
        failures.append("walkthrough-v1 must remain classified as a preserved media/documentation release")

    failures.extend(validate_archive_policy(release))
    failures.extend(validate_workflow_policy(root, release))
    return failures


def tracked_files(root: Path) -> dict[str, str]:
    raw = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    result: dict[str, str] = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        mode = metadata.split(b" ", 1)[0].decode("ascii")
        path = path_bytes.decode("utf-8")
        result[path] = mode
    return result


def select_release_files(root: Path, release: dict[str, Any]) -> list[dict[str, Any]]:
    archive = release["archive"]
    include_exact = set(archive["includeExact"])
    exclude_exact = set(archive["excludeExact"])
    include_prefixes = tuple(archive["includePrefixes"])
    exclude_prefixes = tuple(archive["excludePrefixes"])
    selected: list[dict[str, Any]] = []
    for relative_path, git_mode in sorted(tracked_files(root).items()):
        included = relative_path in include_exact or relative_path.startswith(include_prefixes)
        excluded = relative_path in exclude_exact or relative_path.startswith(exclude_prefixes)
        if not included or excluded:
            continue
        if path_is_forbidden(relative_path, archive):
            raise ReleaseError(f"allowlisted release path violates the artifact policy: {relative_path}")
        if git_mode == "120000":
            raise ReleaseError(f"release archives do not permit symbolic links: {relative_path}")
        path = root / relative_path
        if not path.is_file():
            raise ReleaseError(f"tracked release file is missing from the worktree: {relative_path}")
        payload = path.read_bytes()
        selected.append(
            {
                "path": relative_path,
                "mode": "0755" if git_mode == "100755" else "0644",
                "size": len(payload),
                "sha256": sha256_bytes(payload),
            }
        )
    required = {
        "config/release.json",
        release["bindings"]["changelog"]["path"],
        release["bindings"]["releaseNotes"]["path"],
        release["bindings"]["compatibility"]["path"],
    }
    missing = sorted(required - {item["path"] for item in selected})
    if missing:
        raise ReleaseError("release archive allowlist omits required files: " + ", ".join(missing))
    return selected


def create_archive(root: Path, output: Path, archive_root: str, files: list[dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.GNU_FORMAT) as tar:
                for item in files:
                    data = (root / item["path"]).read_bytes()
                    info = tarfile.TarInfo(name=f"{archive_root}/{item['path']}")
                    info.size = len(data)
                    info.mode = int(item["mode"], 8)
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    tar.addfile(info, io.BytesIO(data))


def source_timestamp(root: Path) -> str:
    value = git(root, "show", "-s", "--format=%cI", "HEAD")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_spdx(
    release: dict[str, Any],
    *,
    archive_name: str,
    archive_sha256: str,
    source_revision: str,
    created: str,
) -> dict[str, Any]:
    product = release["product"]
    package_id = "SPDXRef-Package"
    return {
        "SPDXID": "SPDXRef-DOCUMENT",
        "creationInfo": {
            "created": created,
            "creators": ["Tool: liveks-release-builder/1"],
        },
        "dataLicense": "CC0-1.0",
        "documentNamespace": (
            f"https://github.com/{product['repository']}/releases/tag/{product['tag']}"
            f"/spdx-{source_revision}"
        ),
        "name": archive_name,
        "packages": [
            {
                "SPDXID": package_id,
                "checksums": [
                    {
                        "algorithm": "SHA256",
                        "checksumValue": archive_sha256,
                    }
                ],
                "copyrightText": "NOASSERTION",
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "MIT",
                "name": product["name"],
                "packageFileName": archive_name,
                "supplier": "Organization: Microsoft",
                "versionInfo": product["version"],
            }
        ],
        "relationships": [
            {
                "relatedSpdxElement": package_id,
                "relationshipType": "DESCRIBES",
                "spdxElementId": "SPDXRef-DOCUMENT",
            }
        ],
        "spdxVersion": release["sbom"]["format"],
    }


def validate_spdx(path: Path, release: dict[str, Any]) -> None:
    command = str(release["sbom"]["command"])
    executable = shutil.which(command)
    if not executable:
        raise ReleaseError(
            f"{command} is required to validate the SPDX SBOM; "
            "install requirements-release.txt"
        )
    result = subprocess.run(
        [executable, "-i", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ReleaseError(f"SPDX validation failed for {path.name}: {detail}")


def inspect_archive(path: Path, archive_root: str, files: list[dict[str, Any]]) -> None:
    expected = [f"{archive_root}/{item['path']}" for item in files]
    with tarfile.open(path, mode="r:gz") as archive:
        members = archive.getmembers()
        actual = [member.name for member in members]
        if actual != expected:
            raise ReleaseError("archive contents differ from the sorted allowlisted file manifest")
        for member in members:
            pure = PurePosixPath(member.name)
            if pure.is_absolute() or ".." in pure.parts or not member.isfile():
                raise ReleaseError(f"archive contains an unsafe member: {member.name}")
            if member.uid != 0 or member.gid != 0 or member.mtime != 0:
                raise ReleaseError(f"archive metadata is not normalized: {member.name}")


def write_checksums(output_dir: Path, filename: str, artifact_paths: list[Path]) -> None:
    lines = [
        f"{sha256_file(path)}  {path.name}"
        for path in sorted(artifact_paths, key=lambda item: item.name)
    ]
    (output_dir / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_checksums(output_dir: Path, checksums_name: str, expected_names: set[str]) -> None:
    path = output_dir / checksums_name
    if not path.is_file():
        raise ReleaseError(f"checksum file is missing: {checksums_name}")
    observed: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if not match:
            raise ReleaseError(f"{checksums_name}:{line_number} is not a valid SHA-256 entry")
        expected_digest, filename = match.groups()
        artifact = output_dir / filename
        if not artifact.is_file():
            raise ReleaseError(f"{checksums_name} references missing artifact {filename}")
        actual_digest = sha256_file(artifact)
        if actual_digest != expected_digest:
            raise ReleaseError(
                f"checksum mismatch for {filename}: expected {expected_digest}, found {actual_digest}"
            )
        observed.add(filename)
    if observed != expected_names:
        raise ReleaseError(
            f"{checksums_name} entries differ from release artifacts: "
            f"expected={sorted(expected_names)}, found={sorted(observed)}"
        )


def build_once(root: Path, release: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    names = artifact_names(release)
    files = select_release_files(root, release)
    source_revision = git(root, "rev-parse", "HEAD")
    source_tree_digest = sha256_bytes(canonical_json(files))
    archive_path = output_dir / names["archive"]
    create_archive(root, archive_path, names["archiveRoot"], files)
    archive_sha = sha256_file(archive_path)
    inspect_archive(archive_path, names["archiveRoot"], files)

    sbom = build_spdx(
        release,
        archive_name=names["archive"],
        archive_sha256=archive_sha,
        source_revision=source_revision,
        created=source_timestamp(root),
    )
    sbom_path = output_dir / names["sbom"]
    sbom_path.write_bytes(canonical_json(sbom))
    validate_spdx(sbom_path, release)

    notes_path = root / release["bindings"]["releaseNotes"]["path"]
    compatibility_path = root / release["bindings"]["compatibility"]["path"]
    manifest = {
        "schemaVersion": 1,
        "kind": "liveks-release-dry-run-manifest",
        "product": {
            "name": release["product"]["name"],
            "slug": release["product"]["slug"],
            "version": release["product"]["version"],
            "expectedTag": release["product"]["tag"],
            "status": release["product"]["status"],
        },
        "source": {
            "repository": release["product"]["repository"],
            "revision": source_revision,
            "treeDigest": source_tree_digest,
        },
        "archive": {
            "file": names["archive"],
            "root": names["archiveRoot"],
            "sha256": archive_sha,
            "size": archive_path.stat().st_size,
            "fileCount": len(files),
            "files": files,
        },
        "sbom": {
            "file": names["sbom"],
            "format": release["sbom"]["format"],
            "sha256": sha256_file(sbom_path),
            "validatedBy": release["sbom"]["validator"],
        },
        "releaseNotes": {
            "path": release["bindings"]["releaseNotes"]["path"],
            "sha256": sha256_file(notes_path),
        },
        "compatibilityContract": {
            "path": release["bindings"]["compatibility"]["path"],
            "sha256": sha256_file(compatibility_path),
        },
        "publication": {
            "performed": False,
            "registry": False,
            "installer": False,
            "productionAttestation": False,
        },
    }
    manifest_path = output_dir / names["manifest"]
    manifest_path.write_bytes(canonical_json(manifest))
    checksum_targets = [archive_path, manifest_path, sbom_path]
    write_checksums(output_dir, names["checksums"], checksum_targets)
    verify_checksums(
        output_dir,
        names["checksums"],
        {path.name for path in checksum_targets},
    )
    return manifest


def compare_output_dirs(first: Path, second: Path) -> None:
    first_files = {path.name: path.read_bytes() for path in first.iterdir() if path.is_file()}
    second_files = {path.name: path.read_bytes() for path in second.iterdir() if path.is_file()}
    if first_files.keys() != second_files.keys():
        raise ReleaseError(
            "release dry-run outputs are nondeterministic: artifact name sets differ"
        )
    changed = sorted(name for name in first_files if first_files[name] != second_files[name])
    if changed:
        raise ReleaseError(
            "release dry-run outputs are nondeterministic: bytes differ for " + ", ".join(changed)
        )


def ensure_clean_tracked_worktree(root: Path) -> None:
    dirty = git(root, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise ReleaseError(
            "release dry run requires a clean tracked worktree; commit or restore tracked changes first"
        )


def run_no_secret_scan(root: Path) -> None:
    result = subprocess.run(
        ["bash", "scripts/no-secret-scan.sh"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ReleaseError(f"existing no-secret scan failed before release packaging: {detail}")


def dry_run(root: Path, release: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    failures = validate_release_contract(root, release)
    if failures:
        raise ReleaseError("release contract validation failed:\n- " + "\n- ".join(failures))
    ensure_clean_tracked_worktree(root)
    run_no_secret_scan(root)
    try:
        output_dir.resolve().relative_to((root / ".release").resolve())
    except ValueError as error:
        raise ReleaseError("release dry-run output must stay under the ignored .release/ directory") from error
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir.parent) as temp_dir:
        temp_root = Path(temp_dir)
        first = temp_root / "first"
        second = temp_root / "second"
        first.mkdir()
        second.mkdir()
        manifest = build_once(root, release, first)
        build_once(root, release, second)
        compare_output_dirs(first, second)
        shutil.copytree(first, output_dir)
    return manifest


def verify_tag(root: Path, release: dict[str, Any]) -> None:
    failures = validate_release_contract(root, release)
    if failures:
        raise ReleaseError("release contract validation failed:\n- " + "\n- ".join(failures))
    product = release["product"]
    guard = release["workflowPolicy"]["releaseGuard"]
    if product["status"] != "ready":
        raise ReleaseError("tag publication is blocked until product.status is ready")
    if not product.get("releaseDate"):
        raise ReleaseError("tag publication is blocked until product.releaseDate is set")
    expected = {
        "GITHUB_REPOSITORY": guard["repository"],
        "GITHUB_EVENT_NAME": guard["event"],
        "GITHUB_REF": f"refs/tags/{product['tag']}",
        "GITHUB_REF_NAME": product["tag"],
    }
    for variable, value in expected.items():
        if os.environ.get(variable) != value:
            raise ReleaseError(f"{variable} must be {value!r} for trusted publication")
    head = git(root, "rev-parse", "HEAD")
    event_sha = os.environ.get("GITHUB_SHA", "")
    tag_commit = git(root, "rev-parse", f"refs/tags/{product['tag']}^{{commit}}")
    if not event_sha or head != event_sha or tag_commit != event_sha:
        raise ReleaseError("release tag, checked-out commit, and GITHUB_SHA must be identical")
    if guard.get("requireTagOnMain"):
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", event_sha, "origin/main"],
            cwd=root,
            check=False,
        )
        if result.returncode != 0:
            raise ReleaseError("release tag commit must be reachable from origin/main")


def report_failure(error: Exception) -> int:
    print(f"Release contract: FAIL\n- {error}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="Validate release and workflow policy without building.")
    dry_parser = subparsers.add_parser("dry-run", help="Build and verify deterministic artifacts without publishing.")
    dry_parser.add_argument("--output-dir", type=Path, default=Path(".release/dry-run"))
    subparsers.add_parser("verify-tag", help="Verify trusted repository, tag, commit, and release readiness.")
    args = parser.parse_args()
    try:
        release = load_release()
        if args.command == "check":
            failures = validate_release_contract(ROOT, release)
            if failures:
                raise ReleaseError("\n- ".join(failures))
            print("Release contract: PASS")
            return 0
        if args.command == "dry-run":
            manifest = dry_run(ROOT, release, (ROOT / args.output_dir).resolve())
            names = artifact_names(release)
            summary = {
                "status": "pass",
                "publicationPerformed": False,
                "reproducible": True,
                "sourceRevision": manifest["source"]["revision"],
                "artifacts": {
                    name: {
                        "sha256": sha256_file((ROOT / args.output_dir).resolve() / filename),
                    }
                    for name, filename in names.items()
                    if name != "archiveRoot"
                },
            }
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0
        verify_tag(ROOT, release)
        print("Release tag guard: PASS")
        return 0
    except (OSError, ReleaseError, subprocess.SubprocessError) as error:
        return report_failure(error)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate, generate, and execute the compatibility command contract."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from liveks.compatibility import (  # noqa: E402
    AZD_MINIMUM,
    NODE_MINIMUM,
    PREVIEW_SEARCH_API_VERSION,
    PYTHON_MINIMUM,
    STABLE_SEARCH_API_VERSION,
    load_compatibility_contract,
)


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


def nested_value(data: Any, selector: str) -> Any:
    current = data
    for part in selector.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(selector)
        current = current[part]
    return current


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def workflow_step(job: dict[str, Any], uses_prefix: str) -> dict[str, Any] | None:
    for step in job.get("steps", []):
        if isinstance(step, dict) and str(step.get("uses", "")).startswith(uses_prefix):
            return step
    return None


def workflow_runs(job: dict[str, Any], command: str) -> bool:
    return any(
        isinstance(step, dict) and command in str(step.get("run", ""))
        for step in job.get("steps", [])
    )


def validate_contract(root: Path, contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    stable = str(contract["api_contracts"]["search_index"]["version"])
    preview = str(contract["api_contracts"]["preview"]["version"])

    if stable != STABLE_SEARCH_API_VERSION or preview != PREVIEW_SEARCH_API_VERSION:
        failures.append("config/compatibility.yaml API constants were not loaded consistently; restart the check after editing the contract")

    schema = load_yaml(root / "config/schema.yaml")
    expected_schema_values = [stable, preview]
    fields = schema["fields"]
    if fields["search.api_version"]["values"] != expected_schema_values:
        failures.append(
            f"config/schema.yaml fields.search.api_version.values must be {expected_schema_values!r}; "
            "update the schema or config/compatibility.yaml"
        )
    if fields["search.index_api_version"]["values"] != [stable]:
        failures.append(f"config/schema.yaml search.index_api_version must allow only {stable}")
    if fields["search.preview_api_version"]["values"] != [preview]:
        failures.append(f"config/schema.yaml search.preview_api_version must allow only {preview}")

    for contract_name, api in contract["api_contracts"].items():
        version = str(api["version"])
        for profile, selector in api["profile_fields"].items():
            profile_path = root / "profiles" / f"{profile}.yaml"
            actual = nested_value(load_yaml(profile_path), f"defaults.{selector}")
            if str(actual) != version:
                failures.append(
                    f"{profile_path.relative_to(root).as_posix()} defaults.{selector} must be {version} "
                    f"for api_contracts.{contract_name}"
                )
        for relative_path, key in api.get("generated_env", {}).items():
            path = root / relative_path
            actual = parse_env(path).get(str(key))
            if actual != version:
                failures.append(
                    f"{relative_path} {key} must be {version}; run "
                    "python scripts/generate_env_examples.py and re-run the compatibility check"
                )
        for relative_path in api.get("text_bindings", []):
            path = root / relative_path
            text = path.read_text(encoding="utf-8")
            if version not in text:
                failures.append(f"{relative_path} must contain the pinned API version {version}")
            other_version = preview if version == stable else stable
            if other_version in text:
                failures.append(
                    f"{relative_path} is bound to {version} but also contains cross-lane API version {other_version}"
                )
        for relative_path, selector in api.get("json_bindings", {}).items():
            path = root / relative_path
            actual = nested_value(json.loads(path.read_text(encoding="utf-8")), str(selector))
            if actual != version:
                failures.append(f"{relative_path} {selector} must be {version}, found {actual!r}")

    profile_manifests = {
        path.stem: load_yaml(path)
        for path in sorted((root / "profiles").glob("*.yaml"))
        if load_yaml(path).get("kind") == "deployment"
    }
    for section_name in ("runtimes", "tools"):
        for item_name, item in contract[section_name].items():
            command = item.get("command")
            for profile in item.get("required_profiles", []):
                required_tools = profile_manifests[profile].get("required_tools", [])
                expected_tool = (
                    "python3"
                    if item_name == "python"
                    else "az"
                    if item_name == "bicep"
                    else command
                )
                if expected_tool and expected_tool not in required_tools:
                    failures.append(
                        f"profiles/{profile}.yaml required_tools must include {expected_tool} "
                        f"for {section_name}.{item_name}"
                    )

    devcontainer = json.loads((root / ".devcontainer/devcontainer.json").read_text(encoding="utf-8"))
    features = devcontainer.get("features", {})
    azure_cli = features.get("ghcr.io/devcontainers/features/azure-cli:1.3.0", {})
    azd = features.get("ghcr.io/azure/azure-dev/azd:0.2.0", {})
    node = features.get("ghcr.io/devcontainers/features/node:2.1.0", {})
    expected_pins = {
        "Azure CLI": (azure_cli.get("version"), contract["tools"]["azure_cli"]["pinned_environment"]),
        "Bicep": (str(azure_cli.get("bicepVersion", "")).lstrip("v"), contract["tools"]["bicep"]["pinned_environment"]),
        "azd": (azd.get("version"), contract["tools"]["azd"]["pinned_environment"]),
        "Node.js": (node.get("version"), contract["tools"]["node"]["pinned_environment"]),
    }
    for label, (actual, expected) in expected_pins.items():
        if str(actual) != str(expected):
            failures.append(f".devcontainer/devcontainer.json {label} pin must be {expected}, found {actual!r}")

    api_package = json.loads((root / "static-app/api/package.json").read_text(encoding="utf-8"))
    if nested_value(api_package, "engines.node") != f">={contract['tools']['node']['minimum']}":
        failures.append("static-app/api/package.json engines.node must match tools.node.minimum")

    expected_dependencies = contract["dependencies"]
    for relative_path, expected_lines in expected_dependencies.items():
        actual_lines = {
            line.strip()
            for line in (root / relative_path).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        for expected in expected_lines:
            if expected not in actual_lines:
                failures.append(f"{relative_path} must pin {expected}")

    source_bindings = {
        "src/liveks/config.py": ("STABLE_SEARCH_API_VERSION", "PREVIEW_SEARCH_API_VERSION"),
        "src/liveks/cli.py": (
            "STABLE_SEARCH_API_VERSION",
            "PREVIEW_SEARCH_API_VERSION",
            "PYTHON_MINIMUM",
            "AZD_MINIMUM",
            "NODE_MINIMUM",
        ),
    }
    for relative_path, names in source_bindings.items():
        text = (root / relative_path).read_text(encoding="utf-8")
        for name in names:
            if name not in text:
                failures.append(f"{relative_path} must consume {name} from config/compatibility.yaml")

    wrapper = (root / "liveks").read_text(encoding="utf-8")
    powershell_wrapper = (root / "liveks.ps1").read_text(encoding="utf-8")
    python_minor = str(PYTHON_MINIMUM[1])
    if f"python3.{python_minor}" not in wrapper or f"(3, {python_minor})" not in wrapper:
        failures.append(f"liveks must enforce Python {contract['runtimes']['python']['minimum']} or newer")
    if f'"3.{python_minor}"' not in powershell_wrapper or f"(3, {python_minor})" not in powershell_wrapper:
        failures.append(f"liveks.ps1 must enforce Python {contract['runtimes']['python']['minimum']} or newer")
    if "--no-input" not in wrapper or "--no-input" not in powershell_wrapper:
        failures.append("liveks bootstrap must keep pip noninteractive with --no-input on both launchers")
    if "for candidate in python3 python python3.14" not in wrapper:
        failures.append("liveks must prefer the workflow-selected Python from PATH before versioned fallbacks")
    generic_python = powershell_wrapper.find('foreach ($candidate in @("python3", "python"))')
    py_launcher = powershell_wrapper.find("if (Get-Command py")
    if generic_python < 0 or py_launcher < 0 or generic_python > py_launcher:
        failures.append("liveks.ps1 must prefer the workflow-selected Python from PATH before py launcher fallbacks")

    validate_workflow = load_yaml(root / ".github/workflows/validate.yml")
    if validate_workflow.get("permissions") != {"contents": "read"}:
        failures.append(".github/workflows/validate.yml permissions must remain contents: read")
    pages_workflow = load_yaml(root / ".github/workflows/pages.yml")
    protected_workflow = load_yaml(root / ".github/workflows/protected-mcp-search-index.yml")
    workflows = {
        ".github/workflows/validate.yml": validate_workflow,
        ".github/workflows/pages.yml": pages_workflow,
        ".github/workflows/protected-mcp-search-index.yml": protected_workflow,
    }
    for combination in contract["ci"]["combinations"]:
        workflow = workflows[combination["workflow"]]
        job = workflow["jobs"].get(combination["job"], {})
        if job.get("runs-on") != combination["runner"]:
            failures.append(
                f"{combination['workflow']} job {combination['job']} must run on {combination['runner']}"
            )
        python_step = workflow_step(job, "actions/setup-python@")
        python_version = nested_value(python_step or {}, "with.python-version") if python_step else None
        if str(python_version) != str(combination["python"]):
            failures.append(
                f"{combination['workflow']} job {combination['job']} must set Python {combination['python']}"
            )
        if combination.get("node"):
            node_step = workflow_step(job, "actions/setup-node@")
            node_version = nested_value(node_step or {}, "with.node-version") if node_step else None
            if str(node_version) != str(combination["node"]):
                failures.append(
                    f"{combination['workflow']} job {combination['job']} must set Node.js {combination['node']}"
                )
        command_set = combination.get("command_set")
        if command_set:
            expected_command = f"python scripts/check_compatibility.py --run-commands {command_set}"
            if not workflow_runs(job, expected_command):
                failures.append(
                    f"{combination['workflow']} job {combination['job']} must run `{expected_command}`"
                )

    protected = contract["ci"]["protected_live"]
    protected_job = protected_workflow["jobs"]["live-canary"]
    protected_python = workflow_step(protected_job, "actions/setup-python@")
    if protected_job.get("runs-on") != protected["runner"]:
        failures.append("protected workflow runner drifted from ci.protected_live")
    if str(nested_value(protected_python or {}, "with.python-version")) != str(protected["python"]):
        failures.append("protected workflow Python drifted from ci.protected_live")

    for command_set, definition in contract["command_sets"].items():
        seen_ids: set[str] = set()
        for step in definition["steps"]:
            step_id = str(step["id"])
            if step_id in seen_ids:
                failures.append(f"command_sets.{command_set} contains duplicate step id {step_id}")
            seen_ids.add(step_id)
            if step.get("cloud_mutation") is not False:
                failures.append(f"command_sets.{command_set}.{step_id} must explicitly set cloud_mutation: false")
            display = str(step["display"]).lower()
            if any(f" {command}" in f" {display} " for command in ("up", "down", "e2e")):
                failures.append(f"command_sets.{command_set}.{step_id} contains a forbidden cloud lifecycle command")
            expected_argv = (
                shlex.split(str(step["display"]))
                if command_set == "posix"
                else ["pwsh", "-NoProfile", "-File", *str(step["display"]).split()]
            )
            if [str(value) for value in step["argv"]] != expected_argv:
                failures.append(
                    f"command_sets.{command_set}.{step_id} argv must execute the documented display exactly"
                )

    for surface in contract["documentation"]["generated_surfaces"]:
        expected = render_surface(contract, str(surface["content"]))
        path = root / surface["path"]
        actual = generated_block(path, str(surface["marker"]))
        if actual != expected:
            failures.append(
                f"{surface['path']} generated compatibility block is stale; "
                "run python scripts/check_compatibility.py --generate"
            )

    if STABLE_SEARCH_API_VERSION != stable or PREVIEW_SEARCH_API_VERSION != preview:
        failures.append("loaded API compatibility constants do not match config/compatibility.yaml")
    if PYTHON_MINIMUM != tuple(int(part) for part in str(contract["runtimes"]["python"]["minimum"]).split(".")):
        failures.append("loaded Python minimum does not match config/compatibility.yaml")
    if AZD_MINIMUM != tuple(int(part) for part in str(contract["tools"]["azd"]["minimum"]).split(".")):
        failures.append("loaded azd minimum does not match config/compatibility.yaml")
    if NODE_MINIMUM != tuple(int(part) for part in str(contract["tools"]["node"]["minimum"]).split(".")):
        failures.append("loaded Node.js minimum does not match config/compatibility.yaml")
    return failures


def command_block(contract: dict[str, Any], command_set: str) -> str:
    fence = "powershell" if command_set == "windows" else "bash"
    commands = "\n".join(str(step["display"]) for step in contract["command_sets"][command_set]["steps"])
    return f"```{fence}\n{commands}\n```"


def render_full_contract(contract: dict[str, Any]) -> str:
    lines = [
        "## Continuously Checked Compatibility",
        "",
        "This table reports requirements and executed evidence separately. A launcher accepting a version is not a claim that CI exercised it.",
        "",
        "| Runtime or tool | Required or minimum | Continuously checked evidence | Not claimed |",
        "| --- | --- | --- | --- |",
    ]
    for item in list(contract["runtimes"].values()) + list(contract["tools"].values()):
        lines.append(
            f"| {item['label']} | {item['requirement']} | {item['continuous_evidence']} | {item['unverified']} |"
        )
    lines.extend(
        [
            "",
            "The exact continuously exercised combinations are:",
            "",
            "| Workflow job | Runner | Python | Node.js | Evidence |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for combination in contract["ci"]["combinations"]:
        workflow_url = f"{contract['repository_url']}/blob/main/{combination['workflow']}"
        workflow_link = f"[`{combination['job']}`]({workflow_url})"
        lines.append(
            f"| {workflow_link} | `{combination['runner']}` | `{combination['python']}` | "
            f"`{combination.get('node') or 'not used'}` | {combination['evidence']} |"
        )
    lines.extend(
        [
            "",
            "## Pinned Azure AI Search API Contracts",
            "",
            "| Lane | Version and status | Bound profiles and operations | Checked authority |",
            "| --- | --- | --- | --- |",
        ]
    )
    for api in contract["api_contracts"].values():
        profiles = ", ".join(f"`{profile}`" for profile in api["profile_fields"])
        lines.append(
            f"| {api['label']} | `{api['version']}` ({api['release_status']}) | "
            f"{profiles}: {api['operations']} | {api['evidence']} |"
        )
    lines.extend(
        [
            "",
            "MCP Server KS and Fabric Ontology KS remain public preview. Their request and response behavior can change; review the official Microsoft Learn links below before changing either pin. This accelerator is not a production-readiness claim.",
            "",
            "## Documentation Command Contract",
            "",
            "From a fresh checkout, the canonical path installs only the pinned local Python dependency, inspects checked-in data, and runs local validation. It does not authenticate, call Azure or Fabric, or run `up`, `down`, or `e2e`.",
            "",
            f"**{contract['command_sets']['posix']['label']}**",
            "",
            command_block(contract, "posix"),
            "",
            f"**{contract['command_sets']['windows']['label']}**",
            "",
            command_block(contract, "windows"),
            "",
            "Each command must exit `0`. The runner also checks replay assertions, bootstrap completion, profile output, the offline doctor JSON envelope, and the final local-validation pass signal.",
            "",
            "**Azure live validation: NOT RUN. Fabric live validation: NOT RUN.** Ordinary compatibility CI is credential-free and non-mutating.",
        ]
    )
    return "\n".join(lines)


def render_surface(contract: dict[str, Any], content: str) -> str:
    if content == "posix-commands":
        return command_block(contract, "posix")
    if content == "full-contract":
        return render_full_contract(contract)
    raise ValueError(f"Unsupported generated documentation content: {content}")


def generated_markers(marker: str) -> tuple[str, str]:
    return f"<!-- {marker}:start -->", f"<!-- {marker}:end -->"


def generated_block(path: Path, marker: str) -> str:
    text = path.read_text(encoding="utf-8")
    start, end = generated_markers(marker)
    if text.count(start) != 1 or text.count(end) != 1:
        return ""
    return text.split(start, 1)[1].split(end, 1)[0].strip()


def write_generated_block(path: Path, marker: str, content: str) -> None:
    text = path.read_text(encoding="utf-8")
    start, end = generated_markers(marker)
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"{path} must contain exactly one {start} and {end}")
    prefix, remainder = text.split(start, 1)
    _, suffix = remainder.split(end, 1)
    path.write_text(f"{prefix}{start}\n{content}\n{end}{suffix}", encoding="utf-8")


def generate_documentation(root: Path, contract: dict[str, Any]) -> None:
    for surface in contract["documentation"]["generated_surfaces"]:
        write_generated_block(
            root / surface["path"],
            str(surface["marker"]),
            render_surface(contract, str(surface["content"])),
        )


def validate_command_evidence(step: dict[str, Any], result: subprocess.CompletedProcess[str]) -> list[str]:
    failures: list[str] = []
    step_id = str(step["id"])
    expected_exit = int(step["expected_exit"])
    if result.returncode != expected_exit:
        failures.append(f"{step_id} exited {result.returncode}; expected {expected_exit}")
        return failures
    for expected in step.get("stdout_contains", []):
        if str(expected) not in result.stdout:
            failures.append(f"{step_id} stdout is missing expected evidence: {expected}")
    if step.get("json_evidence"):
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            failures.append(f"{step_id} did not emit valid JSON: {error}")
        else:
            for selector, expected in step["json_evidence"].items():
                try:
                    actual = nested_value(payload, str(selector))
                except KeyError:
                    failures.append(f"{step_id} JSON is missing {selector}")
                    continue
                if actual != expected:
                    failures.append(f"{step_id} JSON {selector} must be {expected!r}, found {actual!r}")
    return failures


def run_command_set(
    root: Path,
    contract: dict[str, Any],
    command_set: str,
    *,
    run: RunCommand = subprocess.run,
) -> list[str]:
    if command_set == "windows" and os.name != "nt":
        return ["windows command contract can run only on Windows"]
    if command_set == "posix" and os.name == "nt":
        return ["posix command contract can run only on a POSIX runner"]
    failures: list[str] = []
    for step in contract["command_sets"][command_set]["steps"]:
        argv = [str(value) for value in step["argv"]]
        print(f"\n$ {step['display']}")
        try:
            result = run(
                argv,
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                timeout=1200,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            failures.append(f"{step['id']} could not run: {error}")
            break
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        step_failures = validate_command_evidence(step, result)
        failures.extend(step_failures)
        if step_failures:
            break
    return failures


def report(failures: list[str], success: str) -> int:
    if failures:
        print("Compatibility contract: FAIL", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(success)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Check compatibility bindings and generated docs.")
    mode.add_argument("--generate", action="store_true", help="Regenerate compatibility documentation blocks.")
    mode.add_argument("--run-commands", choices=["posix", "windows"], help="Run one documented command set.")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.root.resolve()
    contract = load_compatibility_contract(root / "config/compatibility.yaml")

    if args.generate:
        try:
            generate_documentation(root, contract)
        except (OSError, ValueError) as error:
            return report([str(error)], "")
    try:
        failures = validate_contract(root, contract)
    except (FileNotFoundError, KeyError, TypeError, ValueError, yaml.YAMLError) as error:
        return report([f"unable to validate a declared compatibility binding: {error}"], "")
    if failures:
        return report(failures, "")
    if args.run_commands:
        return report(
            run_command_set(root, contract, args.run_commands),
            f"Documentation command contract ({args.run_commands}): PASS",
        )
    return report([], "Compatibility contract: PASS")


if __name__ == "__main__":
    raise SystemExit(main())

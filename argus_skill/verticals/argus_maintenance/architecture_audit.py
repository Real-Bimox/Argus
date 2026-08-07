"""Evidence-first architecture audit for Argus and other Python repositories.

The scanner reports review candidates; it never equates a heuristic match with a
defect.  Security checks, integrity digests, compatibility boundaries, and
failure isolation may be correct.  A maintainer must classify each relevant
finding as keep, simplify, move, or remove from real call-path evidence.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = 1
_IGNORED_PARTS = frozenset({
    ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv",
    "__pycache__", "build", "bundle", "dist", "node_modules", "site-packages",
    "technical_report",
})
_TEXT_SUFFIXES = frozenset({".json", ".md", ".py", ".toml", ".ts", ".tsx", ".yaml", ".yml"})
_HEX_RE = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32,64}(?![0-9A-Fa-f])")
_MACHINE_PATH_RE = re.compile(
    r"(?:/home/[A-Za-z0-9._-]+|/Users/[A-Za-z0-9._-]+|"
    r"[A-Za-z]:\\Users\\[A-Za-z0-9._-]+)"
)
_HARDWARE_RE = re.compile(r"\b(?:A100|B100|B200|H100|H200|GB200|RTX\s?[0-9]{4})\b", re.I)
_ARCHITECTURE_PARTS = frozenset({
    "adapters", "agent_cli", "apps", "builtin_skills", "core", "engineer",
    "life", "manager", "planner", "reviewer", "roles", "webapi",
})
_ALLOWED_VERTICAL_MODULES = frozenset({"_base", "_data_domain", "_registry"})


@dataclass(frozen=True)
class Finding:
    category: str
    severity: str
    path: str
    line: int
    symbol: str
    evidence: str
    reason: str


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _ignored(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    return any(part in _IGNORED_PARTS or part.startswith(".argus") for part in rel.parts)


def _is_test(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    return (
        bool({"test", "tests", "__tests__"} & set(rel.parts))
        or path.name.startswith("test_")
        or ".test." in path.name
        or ".spec." in path.name
    )


def _is_vertical_owned(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return len(parts) >= 3 and parts[:2] == ("argus_skill", "verticals")


def _maintained_files(root: Path, suffixes: Iterable[str]) -> Iterable[Path]:
    wanted = set(suffixes)
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in wanted and not _ignored(path, root):
            yield path


def _line(lines: list[str], number: int) -> str:
    if 1 <= number <= len(lines):
        return lines[number - 1].strip()[:240]
    return ""


def _name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Tuple):
        return ",".join(_name(value) for value in node.elts)
    return ""


def _broad_handler(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    return _name(handler.type).split(".")[-1] in {"BaseException", "Exception"}


def _default_return(node: ast.Return) -> bool:
    value = node.value
    if value is None or isinstance(value, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return True
    return isinstance(value, ast.Constant) and value.value in {None, False, "", 0}


def _silent_handler(handler: ast.ExceptHandler) -> bool:
    if any(isinstance(node, ast.Raise) for statement in handler.body for node in ast.walk(statement)):
        return False
    for statement in handler.body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call) and _name(node.func).split(".")[-1] in {
                "critical", "debug", "error", "exception", "info", "warning",
            }:
                return False
    return bool(handler.body) and all(
        isinstance(statement, (ast.Pass, ast.Break, ast.Continue))
        or (isinstance(statement, ast.Return) and _default_return(statement))
        for statement in handler.body
    )


def _function_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            body.pop(0)
    return body


def _thin_wrapper(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if node.decorator_list or node.name.startswith("__"):
        return False
    body = _function_body(node)
    if len(body) != 1 or not isinstance(body[0], ast.Return) or not isinstance(body[0].value, ast.Call):
        return False
    params = [*node.args.posonlyargs, *node.args.args]
    names = [param.arg for param in params if param.arg not in {"self", "cls"}]
    call = body[0].value
    positional = [arg.id for arg in call.args if isinstance(arg, ast.Name)]
    if len(positional) != len(call.args):
        return False
    forwarded = positional + [
        keyword.value.id
        for keyword in call.keywords
        if keyword.arg and isinstance(keyword.value, ast.Name)
    ]
    return sorted(forwarded) == sorted(names) and bool(names)


def _vertical_names(root: Path) -> set[str]:
    selector = root / "argus_skill" / "skills" / "vertical_select.py"
    try:
        tree = ast.parse(selector.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == "VERTICALS":
                    return set(ast.literal_eval(node.value))
    except (OSError, SyntaxError, ValueError):
        pass
    stages = root / "argus_skill" / "verticals"
    return {path.parent.name for path in stages.glob("*/stages.py")}


def _python_findings(
    path: Path,
    root: Path,
    *,
    include_tests: bool,
    max_function_lines: int,
    vertical_names: set[str],
) -> list[Finding]:
    rel = _relative(path, root)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    source = "\n".join(lines)
    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as exc:
        return [Finding("syntax_error", "error", rel, int(exc.lineno or 0), "", str(exc.msg),
                        "Maintained Python source must parse before architecture review.")]
    findings: list[Finding] = []
    production = include_tests or not _is_test(path, root)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    branch_lines: set[int] = set()

    for node in ast.walk(tree):
        if production and isinstance(node, ast.Assert):
            findings.append(Finding(
                "runtime_assert", "review", rel, node.lineno, "", _line(lines, node.lineno),
                "Runtime invariants must not disappear under `python -O`; use an explicit error unless this only narrows a proven type.",
            ))
        if production and isinstance(node, ast.ExceptHandler) and _broad_handler(node) and _silent_handler(node):
            findings.append(Finding(
                "silent_broad_exception", "review", rel, node.lineno, "", _line(lines, node.lineno),
                "A broad exception is silently discarded. Narrow it, surface it, or document the boundary that intentionally isolates it.",
            ))
        if production and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            size = int(getattr(node, "end_lineno", node.lineno) - node.lineno + 1)
            if size > max_function_lines:
                findings.append(Finding(
                    "oversized_function", "info", rel, node.lineno, node.name,
                    f"{size} lines", "Review whether one function owns multiple independent responsibilities.",
                ))
            if _thin_wrapper(node):
                findings.append(Finding(
                    "thin_wrapper", "info", rel, node.lineno, node.name, _line(lines, node.lineno),
                    "This function appears to forward arguments without behavior; keep only for a real public or dependency boundary.",
                ))
        if production and isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and len(node.values) >= 3:
            parent = parents.get(node)
            boolean_guard = isinstance(parent, (ast.Assert, ast.If, ast.While)) or any(
                isinstance(value, ast.Compare)
                or (isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.Not))
                for value in node.values
            )
            if not boolean_guard and not isinstance(parent, ast.BoolOp):
                findings.append(Finding(
                    "fallback_chain", "review", rel, node.lineno, "", _line(lines, node.lineno),
                    "Three or more value alternatives can hide provenance and failure. Prefer one owner plus explicit recovery states.",
                ))
        if production and isinstance(node, (ast.Import, ast.ImportFrom)) and not _is_vertical_owned(path, root):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for module in modules:
                parts = module.split(".")
                if "verticals" not in parts:
                    continue
                index = parts.index("verticals")
                concrete = parts[index + 1] if index + 1 < len(parts) else ""
                if concrete and concrete not in _ALLOWED_VERTICAL_MODULES:
                    findings.append(Finding(
                        "concrete_vertical_import", "error", rel, node.lineno, concrete,
                        _line(lines, node.lineno),
                        "Framework orchestration may depend on the vertical contract, never a concrete vertical implementation.",
                    ))
        if production and isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in vertical_names and not _is_vertical_owned(path, root) and rel != "argus_skill/skills/vertical_select.py":
                parent = parents.get(node)
                for _ in range(3):
                    if isinstance(parent, (ast.Compare, ast.MatchValue)):
                        line = int(getattr(parent, "lineno", node.lineno))
                        branch_text = ast.get_source_segment(source, parent) or _line(lines, line)
                        if "vertical" not in branch_text.lower():
                            break
                        if line not in branch_lines:
                            branch_lines.add(line)
                            findings.append(Finding(
                                "concrete_vertical_branch", "review", rel, line, node.value,
                                _line(lines, line),
                                "A generic layer branches on a concrete vertical name; prefer provider-declared contract metadata.",
                            ))
                        break
                    parent = parents.get(parent) if parent is not None else None
    return findings


def _text_findings(path: Path, root: Path, *, include_tests: bool) -> list[Finding]:
    if not include_tests and _is_test(path, root):
        return []
    rel = _relative(path, root)
    vertical_owned = _is_vertical_owned(path, root)
    parts = set(path.relative_to(root).parts)
    architecture_owned = bool(parts & _ARCHITECTURE_PARTS)
    findings: list[Finding] = []
    for number, text in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        machine = _MACHINE_PATH_RE.search(text)
        if machine and machine.group(0).split("/")[-1] != "...":
            findings.append(Finding(
                "machine_specific_path", "error", rel, number, "", machine.group(0),
                "Repository behavior must discover or receive machine paths; personal absolute paths are not portable.",
            ))
        digest = _HEX_RE.search(text)
        if digest and path.name not in {"package-lock.json", "release.generated.ts", "release_manifest.json"}:
            findings.append(Finding(
                "hardcoded_digest", "review", rel, number, "", digest.group(0),
                "A fixed digest needs an explicit integrity/migration owner and retirement condition; otherwise remove the stale pin.",
            ))
        hardware = _HARDWARE_RE.search(text)
        if hardware and architecture_owned and not vertical_owned:
            findings.append(Finding(
                "domain_literal_outside_vertical", "review", rel, number, "", hardware.group(0),
                "Hardware/protocol facts in generic orchestration can become false inventory claims; move domain policy into its vertical.",
            ))
    return findings


def scan_repository(
    project_root: Path | str,
    *,
    include_tests: bool = False,
    max_function_lines: int = 120,
) -> dict:
    """Return a machine-readable heuristic audit of maintained source files."""
    root = Path(project_root).expanduser().resolve()
    findings: list[Finding] = []
    files = list(_maintained_files(root, _TEXT_SUFFIXES))
    vertical_names = _vertical_names(root)
    for path in files:
        if path.suffix == ".py":
            findings.extend(_python_findings(
                path,
                root,
                include_tests=include_tests,
                max_function_lines=max(20, int(max_function_lines)),
                vertical_names=vertical_names,
            ))
        findings.extend(_text_findings(path, root, include_tests=include_tests))
    unique = {
        (row.category, row.path, row.line, row.symbol, row.evidence): row
        for row in findings
    }
    ordered = sorted(unique.values(), key=lambda row: (row.category, row.path, row.line, row.symbol))
    by_category = Counter(row.category for row in ordered)
    by_severity = Counter(row.severity for row in ordered)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": ".",
        "files_scanned": len(files),
        "policy": {
            "finding_is_not_verdict": True,
            "protected_boundaries": [
                "authentication", "authorization", "sandboxing", "secret protection",
                "idempotency", "crash recovery", "data integrity", "independent review",
            ],
        },
        "counts": {
            "total": len(ordered),
            "by_category": dict(sorted(by_category.items())),
            "by_severity": dict(sorted(by_severity.items())),
        },
        "findings": [asdict(row) for row in ordered],
    }


def render_markdown(report: dict) -> str:
    counts = report["counts"]
    lines = [
        "# Architecture audit",
        "",
        "> Heuristic findings are review candidates, not automatic defects. Preserve justified security, recovery, compatibility, and integrity boundaries.",
        "",
        f"- Maintained files scanned: {report['files_scanned']}",
        f"- Findings: {counts['total']}",
        "- By category: " + ", ".join(f"{key}={value}" for key, value in counts["by_category"].items()),
        "",
    ]
    current = None
    for finding in report["findings"]:
        if finding["category"] != current:
            current = finding["category"]
            lines.extend((f"## {current}", ""))
        location = f"{finding['path']}:{finding['line']}"
        symbol = f" `{finding['symbol']}`" if finding["symbol"] else ""
        lines.append(f"- **{finding['severity']}** `{location}`{symbol}: {finding['reason']}")
        if finding["evidence"]:
            evidence = finding["evidence"].replace("`", "'")
            lines.append(f"  - Evidence: `{evidence}`")
    return "\n".join(lines).rstrip() + "\n"


def validate_report(path: Path | str) -> list[str]:
    report_path = Path(path)
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read audit report: {exc}"]
    errors: list[str] = []
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
        return errors
    if not isinstance(payload.get("findings"), list):
        errors.append("findings must be a list")
    if not isinstance(payload.get("counts"), dict):
        errors.append("counts must be an object")
    policy = payload.get("policy")
    if not isinstance(policy, dict) or policy.get("finding_is_not_verdict") is not True:
        errors.append("report must preserve the finding-is-not-verdict policy")
    return errors


def _write(path: str, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect", help="scan maintained source")
    collect.add_argument("--project-root", default=".")
    collect.add_argument("--output", default="research/ARCHITECTURE_AUDIT.json")
    collect.add_argument("--markdown", default="research/ARCHITECTURE_AUDIT.md")
    collect.add_argument("--include-tests", action="store_true")
    collect.add_argument("--max-function-lines", type=int, default=120)
    validate = commands.add_parser("validate", help="validate a collected report")
    validate.add_argument("--report", default="research/ARCHITECTURE_AUDIT.json")
    require = commands.add_parser("require", help="require non-empty evidence files")
    require.add_argument("paths", nargs="+")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "collect":
        report = scan_repository(
            args.project_root,
            include_tests=args.include_tests,
            max_function_lines=args.max_function_lines,
        )
        rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output == "-":
            sys.stdout.write(rendered)
        else:
            _write(args.output, rendered)
            if args.markdown:
                _write(args.markdown, render_markdown(report))
            print(f"architecture audit: {report['counts']['total']} review candidates across {report['files_scanned']} files")
        return 0
    if args.command == "validate":
        errors = validate_report(args.report)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        return 0
    missing = [path for path in args.paths if not Path(path).is_file() or Path(path).stat().st_size == 0]
    if missing:
        print("missing non-empty evidence: " + ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

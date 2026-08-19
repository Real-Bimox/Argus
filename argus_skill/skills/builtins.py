"""Bundled default skills for new argus-skill homes.

The files under :mod:`argus_skill.builtin_skills` are argus-native
research/paper playbooks adapted from ARIS workflow concepts. They are
seeded into ``~/.argus-skill/skills`` on initialization so the agent can
start research and paper-writing missions before it has distilled its own
local skills.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Iterable

_BUILTIN_PACKAGE = "argus_skill.builtin_skills"
DEFAULT_PROJECT_BUILTIN_SKILLS_DIR = "argus_builtin_skills"
_BUILTIN_SEED_STATE = ".argus-builtin-seeds.json"
_LEGACY_BUILTIN_SEED_HASHES = {
    "agent-md-new-project-template.md": "bfb74c52a6e440e1a3e6728c039ff39bdbed09649e7b0267a8caa303ff991ed0",
    "agent-md-optimize-project-template.md": "52fbd7e60f85042624a54b563945b26739a590120d21c830c8f2d4eda0b3db7d",
    "engineer/aaai-format-preflight.md": "51a5d0a6e035472c43bab41823ca9c651abf4f265288d50c1e4d25dc70d9df03",
    "engineer/agent-team-lead.md": "bdaf7b78b57b3fec45bc9108d0c36f2bd0d07e191657cdffd4299c25f9f98722",
    "engineer/argus-engineer-role.md": "8823e0c01e377e1be5293d1529344213e0f1326ebe94a6863dc4ee0e2730dadd",
    "engineer/auto-research-pipeline.md": "840725b6bd8df6d0e368b933c20ab6d72ebbc5d23a1bf518f2aa56c85944c7a5",
    "engineer/claims-evidence-audit.md": "08cf42f847b4b63900f3ab832ec6441f4d225cf4765ac401cd3a06514b9b403e",
    "engineer/emnlp-format-preflight.md": "f700489a6480e04c2c2147090607dcdcb01efbec8f27d1be4403a3b30a727383",
    "engineer/environment-readiness-gate.md": "f8615f2a465cbe7b2ce838179c24a575baf4fbe6370730035c85cd4dd907de9b",
    "engineer/idea-creator.md": "296bc76fe10857904811b94852d3fcbaa9018ac5bb8d4fd0a8c5f868e7a5b778",
    "engineer/idea-discovery.md": "e594fae6eadf3bfad229f53d8b78aa8456d2d1dc9b3396e2c2c3f852279743af",
    "engineer/idea-feasibility-derisk.md": "e474e85b61a08bc359fa5ce41d06655536b4e66ff88933921d022767367c3cf3",
    "engineer/mermaid-graphviz-diagrams.md": "d340f45b0aeb7ee5f239aa79f1c8f3ed94be4a56af036dd7b80a60cd72953542",
    "engineer/novelty-check.md": "d325add9836257cfc9c0832d267cac7fd5f912e39c3fe4fdfadd943894a8c421",
    "engineer/paper-infrastructure-review.md": "656dd69cf7b49e6d00e466eb7237cfce66fb96216d4ca443bc9e6063edd1717e",
    "engineer/paper-review-revision-loop.md": "adc9cf50a372bb530861f17192982b597a98593bd80fb54ed74cd9c080d05f84",
    "engineer/research-brief-to-experiment-plan.md": "9ff2e37f871d06737690af3dc60b7de8e377c63d0bef59dbe46b0dc9380f84e4",
    "engineer/research-experiment-runner.md": "e3cf568f21b9e6e0817c09d8adb730d0c636f5e54eb48b3be2060a8227928ad7",
    "engineer/research-ideation.md": "58879d7f9f388bb5f81344df906ea099b1e39d0d9809237a2b660807c746554d",
    "engineer/research-results-analysis-and-figures.md": "55e5fd08481332b2b30b0f8508689850cff7608a9af50b7c57927070d694f0f5",
    "engineer/result-to-claim.md": "f6da90fd9160c0981b84dd03f261c5c9aa21ef3a7686ca301715c0457e1d2d6f",
    "engineer/training-infrastructure-guide.md": "43d1cbc1017173a5376f2a47642ea3ba5bf007b879ba86737514f8aba28f3f39",
    "engineer/venue-format-research.md": "e49d4e270e53f919ae2e7f64d23958d231be6e6c1e52b0c30644998c8e8ba6a6",
    "manager/argus-manager-role.md": "dc193f31dca3acd3041544745d97b832725c0e37b55a44bd9a93db5f97a631be",
    "manager/evidence-based-stage-decision.md": "75347a834448d8abb92ae04ad486ab06c595d1fb53cbe3cd24e70b37368515ed",
    "planner/argus-planner-role.md": "30d16975503a9b41d97c05d622b4d36117677ff9500e65a4556dd2f8c244fb12",
    "reviewer/aaai-academic-language-review.md": "7d584d509595f49d7ebe3585987df101ca8552da6c7846afc8e6a9a736dbfc14",
    "reviewer/academic-paper-peer-review-benchmark.md": "a03717c55ad2405a3f04f8d758ac086e92d09e91b71bd7d621c799df7afdd7bc",
    "reviewer/argus-reviewer-role.md": "bc971a888bfcdc3acaca939b643410f509c328376737377ba8e898f1b4dee925",
    "reviewer/emnlp-academic-language-review.md": "3e6a28f75867b2cd3f54fe5468d709ea11e0a9441fe069b4bd67b212a0cf8218",
    "reviewer/experiment-plan-review.md": "6a1d67c2b1c663525dce2bc188576e783217ecbb53c3ca12f601ab34c44a331a",
    "reviewer/experiment-results-review.md": "cf5c2c7029e3db71a45cb7e322caa3dac19a98b0b4a96e2946371a212b9e10b5",
}
_RETIRED_BUILTIN_SEED_HASHES = {
    "engineer/experiment-audit.md": (
        "d7fa41bfefaa0aaa8156f5febc8a4c1dc98874f3e7e24e6306f075266c49074e"
    ),
    "engineer/paper-claim-audit.md": (
        "65311eb7bc317e82195f7dcc56abf7fb8caf357f144bdd16fcf7504e48904ad1"
    ),
    "engineer/singularity-amlt-gpu-ops.md": (
        "18f7020894021a6a15a68e54022c3a7758535ce7e501cea4dc408a33f79ef6dc"
    ),
    "engineer/nanochat-autoresearch-hands-on-trace.md": (
        "7df00f9f7e985143e3ca1af53bf8d16eda864b7598ff8446034c27abefce528f"
    ),
    "engineer/nanochat-autoresearch-sota-optimization.md": (
        "ef6acedaa464fb7e9e5bac60a7737ef8590f72f00c7d658f346d3a227a893ba6"
    ),
    "engineer/nanochat-pretrain-runner.md": (
        "5986a1df8ca519f1ad4a20b9c175647922711b1bad0cf1855c0fdfa30a7d3b46"
    ),
}
_VERTICAL_SKILL_INHERITANCE = {
    "digital_circuit_benchmark": ("digital_circuit",),
    "chip_design": ("digital_circuit",),
    # SOL work additionally needs general GPU-kernel priors. NanoGPT is the
    # concrete H100 speedrun represented by the speedrun playbooks. NanoChat's
    # fixed-budget quality objective must not inherit those machine-specific
    # H100 traces; it follows the current project's frozen harness instead.
    "kernelbench": ("kernel_engineering",),
    "nanogpt_speedrun": ("speedrun",),
}
def builtin_skill_source_path() -> Path:
    """Return the filesystem path for bundled skill markdown when available."""
    return Path(__file__).resolve().parents[1] / "builtin_skills"


def iter_builtin_skill_texts() -> Iterable[tuple[str, str]]:
    """Yield ``(relative_filename, markdown)`` for every bundled default skill."""
    root = resources.files(_BUILTIN_PACKAGE)
    yield from _iter_builtin_skill_resources(root)


def iter_common_builtin_skill_texts() -> Iterable[tuple[str, str]]:
    """Yield top-level common skills, excluding domain-pack subdirectories."""
    root = resources.files(_BUILTIN_PACKAGE)
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if entry.name.startswith(("_", ".")) or not entry.name.endswith(".md"):
            continue
        yield entry.name, entry.read_text(encoding="utf-8")


def vertical_skill_source_path(vertical: str) -> Path:
    """Filesystem path of a vertical's own skills: ``verticals/<v>/skills``.

    The skill-layering convention: ``builtin_skills/`` holds cross-workflow
    skills, while each vertical ships workflow-specific skills under
    ``argus_skill/verticals/<vertical>/skills/{engineer,reviewer}/``. This is the
    version-controlled read-only SOURCE for that vertical's skills.
    """
    if not vertical or "/" in vertical or "\\" in vertical or vertical.startswith("."):
        raise ValueError(f"invalid vertical name: {vertical!r}")
    return Path(__file__).resolve().parents[1] / "verticals" / vertical / "skills"


def domain_skill_source_path(domain: str) -> Path:
    """Filesystem path of a built-in domain's matchable Skills."""
    if not domain or "/" in domain or "\\" in domain or domain.startswith("."):
        raise ValueError(f"invalid domain name: {domain!r}")
    return Path(__file__).resolve().parents[1] / "domains" / domain / "skills"


def iter_vertical_skill_texts(vertical: str) -> Iterable[tuple[str, str]]:
    """Yield ``(relative_filename, markdown)`` for a vertical's own skills.

    Relative names are rooted at the vertical's ``skills/`` dir (e.g.
    ``reviewer/quant-factor-report-review.md``) so they match the
    ``<role>/<name>.md`` layout the vertical's checklist prose and
    ``role_banner`` reference verbatim, and overlay the same layout as the
    bundled builtins. Fail-open: an unknown vertical or one with no
    ``skills/`` dir yields nothing.
    """
    from ..verticals._registry import vertical_plugin

    emitted: set[str] = set()
    for source_vertical in (*_VERTICAL_SKILL_INHERITANCE.get(vertical, ()), vertical):
        plugin = vertical_plugin(source_vertical)
        root = plugin.skills_root if plugin and plugin.skills_root is not None else vertical_skill_source_path(source_vertical)
        if not root.is_dir():
            continue
        for filename, text in _iter_builtin_skill_resources(root):
            if filename in emitted:
                continue
            emitted.add(filename)
            yield filename, text


def iter_domain_skill_texts(domain: str) -> Iterable[tuple[str, str]]:
    """Yield ``(relative_filename, markdown)`` for one built-in domain."""
    root = domain_skill_source_path(domain)
    if root.is_dir():
        yield from _iter_builtin_skill_resources(root)


def iter_context_skill_texts(
    vertical: str,
    domain: str | None = None,
) -> Iterable[tuple[str, str]]:
    """Yield workflow Skills plus optional domain Skills, with domain overrides."""
    merged = dict(iter_vertical_skill_texts(vertical))
    if domain:
        merged.update(dict(iter_domain_skill_texts(domain)))
    yield from merged.items()


def _iter_builtin_skill_resources(
    root: Traversable,
    prefix: str = "",
) -> Iterable[tuple[str, str]]:
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if entry.name.startswith(("_", ".")):
            continue
        relative_name = f"{prefix}{entry.name}"
        if entry.is_dir():
            # Reference corpora are package assets consumed by their owning
            # skill, not independently matchable skills.
            if entry.name == "references":
                continue
            yield from _iter_builtin_skill_resources(entry, f"{relative_name}/")
        elif entry.name.endswith(".md"):
            yield relative_name, entry.read_text(encoding="utf-8")
        elif _is_bundled_script(prefix, entry.name):
            # Scripts that ship alongside a skill (e.g.
            # engineer/figure_spec_scripts/figure_renderer.py) live in
            # ``*_scripts/`` subdirs and are seeded verbatim so the
            # skill can invoke them in the project workspace.
            yield relative_name, entry.read_text(encoding="utf-8")


_BUNDLED_SCRIPT_EXTENSIONS = (".py", ".json", ".sh")


def _is_bundled_script(prefix: str, filename: str) -> bool:
    """A file is a bundled-script asset iff it lives under a
    ``*_scripts/`` directory and has a known script extension."""
    if not any(filename.endswith(ext) for ext in _BUNDLED_SCRIPT_EXTENSIONS):
        return False
    # ``prefix`` ends with "/" by construction; split into segments.
    segments = [s for s in prefix.split("/") if s]
    return any(seg.endswith("_scripts") for seg in segments)


def retire_orphaned_builtin_seeds(skills_dir: Path) -> list[str]:
    """Remove retired seeds from matching, archiving any operator-edited copy."""
    skills_dir = Path(skills_dir)
    removed: list[str] = []
    for relative_name, expected_digest in sorted(
        _RETIRED_BUILTIN_SEED_HASHES.items()
    ):
        path = skills_dir / relative_name
        try:
            body = path.read_bytes()
        except (FileNotFoundError, IsADirectoryError, OSError):
            continue
        if hashlib.sha256(body).hexdigest() == expected_digest:
            try:
                path.unlink()
            except OSError:
                continue
        else:
            archive = (
                skills_dir
                / "_retired_builtin_skills"
                / f"{relative_name}.retired"
            )
            archive.parent.mkdir(parents=True, exist_ok=True)
            if archive.exists():
                try:
                    if archive.read_bytes() == body:
                        path.unlink()
                    else:
                        digest = hashlib.sha256(body).hexdigest()[:12]
                        path.replace(
                            archive.with_name(f"{archive.name}.{digest}")
                        )
                except OSError:
                    continue
            else:
                try:
                    path.replace(archive)
                except OSError:
                    continue
        removed.append(relative_name)
    return removed


def _seed_state(skills_dir: Path) -> dict[str, str]:
    try:
        payload = json.loads(
            (skills_dir / _BUILTIN_SEED_STATE).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(name): str(digest)
        for name, digest in payload.items()
        if isinstance(name, str) and isinstance(digest, str)
    }


def _seed_texts(
    skills_dir: Path,
    texts: Iterable[tuple[str, str]],
    *,
    overwrite: bool,
) -> dict[str, bool]:
    state = _seed_state(skills_dir)
    created: dict[str, bool] = {}
    for filename, text in texts:
        if filename.endswith(".md"):
            _validate_builtin(filename, text)
        dest = skills_dir / filename
        source_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        try:
            installed_digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        except (FileNotFoundError, IsADirectoryError):
            installed_digest = ""
        except OSError:
            created[filename] = False
            continue
        prior_digest = state.get(filename, "")
        factory_owned = (
            not installed_digest
            or installed_digest == source_digest
            or (prior_digest and installed_digest == prior_digest)
            or installed_digest == _LEGACY_BUILTIN_SEED_HASHES.get(filename)
        )
        if not overwrite and not factory_owned:
            created[filename] = False
            continue
        changed = installed_digest != source_digest
        if changed:
            dest.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(dest, text)
        state[filename] = source_digest
        created[filename] = changed
    _atomic_write_text(
        skills_dir / _BUILTIN_SEED_STATE,
        json.dumps(state, indent=2, sort_keys=True) + "\n",
    )
    return created


def seed_builtin_skills(skills_dir: Path, *, overwrite: bool = False) -> dict[str, bool]:
    """Seed bundled skills into ``skills_dir``.

    Existing files are preserved by default. The return value maps each
    bundled filename to ``True`` when it was created/replaced and ``False``
    when an existing user file was left untouched.
    """
    skills_dir = Path(skills_dir)
    skills_dir.mkdir(parents=True, exist_ok=True)
    retire_orphaned_builtin_seeds(skills_dir)
    return _seed_texts(
        skills_dir,
        iter_builtin_skill_texts(),
        overwrite=overwrite,
    )


def seed_builtin_skills_for_vertical(
    skills_dir: Path,
    vertical: str,
    *,
    overwrite: bool = False,
) -> dict[str, bool]:
    """Compatibility wrapper for a workflow without a domain overlay."""
    return seed_builtin_skills_for_context(
        skills_dir,
        vertical,
        overwrite=overwrite,
    )


def seed_builtin_skills_for_context(
    skills_dir: Path,
    vertical: str,
    *,
    domain: str | None = None,
    overwrite: bool = False,
) -> dict[str, bool]:
    """Seed COMMON builtins + a vertical's own skills into ``skills_dir``.

    Used to populate a mission's project workspace (``argus_builtin_skills/``) or
    the runtime shared-scope layer so the agent sees common Skills plus the active
    workflow and optional domain Skills. Context-specific real bodies
    OVERWRITE any same-path builtin stub (a moved domain skill leaves a pointer
    stub under ``builtin_skills/``; here the real body wins), so the workspace
    never carries the pointer.

    Note: this uses the FULL bundled set (``iter_builtin_skill_texts``), not
    ``iter_common_builtin_skill_texts`` — the latter skips the ``engineer/`` and
    ``reviewer/`` subdirectories, which is exactly where the cross-vertical
    skills live. Files the vertical will overwrite are skipped on the builtin
    pass so a pointer stub is never written into the workspace at all.

    Returns a map of relative filename → created/replaced (True) or skipped
    (False, an existing file left untouched because ``overwrite`` is False).
    """
    skills_dir = Path(skills_dir)
    skills_dir.mkdir(parents=True, exist_ok=True)
    retire_orphaned_builtin_seeds(skills_dir)
    # Workflow/domain Skills (real bodies) always win over a builtin
    # stub of the same relative path.
    vertical_texts = dict(iter_context_skill_texts(vertical, domain))

    # 1. Common/bundled builtins, skipping any path the vertical will overwrite
    #    (so a pointer stub is never written into the workspace).
    created = _seed_texts(
        skills_dir,
        (
            (filename, text)
            for filename, text in iter_builtin_skill_texts()
            if filename not in vertical_texts
        ),
        overwrite=overwrite,
    )

    # 2. Context-specific real bodies win when explicitly requested, newly
    # seeded, or still factory-owned; operator edits remain intact.
    created.update(
        _seed_texts(
            skills_dir,
            vertical_texts.items(),
            overwrite=overwrite,
        )
    )

    return created


def seed_vertical_skills(
    skills_dir: Path,
    vertical: str,
    *,
    overwrite: bool = False,
    overwrite_unidentified: bool = False,
) -> dict[str, bool]:
    """Compatibility wrapper for a vertical-only runtime layer."""
    return seed_context_skills(
        skills_dir,
        vertical,
        overwrite=overwrite,
        overwrite_unidentified=overwrite_unidentified,
    )


def seed_context_skills(
    skills_dir: Path,
    vertical: str,
    *,
    domain: str | None = None,
    overwrite: bool = False,
    overwrite_unidentified: bool = False,
) -> dict[str, bool]:
    """Seed only the active workflow/domain context into one runtime layer."""
    skills_dir = Path(skills_dir)
    skills_dir.mkdir(parents=True, exist_ok=True)
    retire_orphaned_builtin_seeds(skills_dir)
    created: dict[str, bool] = {}
    for filename, text in iter_context_skill_texts(vertical, domain):
        if filename.endswith(".md"):
            _validate_builtin(filename, text)
        dest = skills_dir / filename
        if dest.exists() and not overwrite:
            _ = overwrite_unidentified
            created[filename] = False
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(dest, text)
        created[filename] = True
    return created


def remove_unmodified_vertical_skill_seeds(
    skills_dir: Path,
    vertical: str,
) -> list[str]:
    """Remove legacy project-layer factory copies without touching learned edits."""
    root = Path(skills_dir)
    removed: list[str] = []
    for filename, source_text in iter_vertical_skill_texts(vertical):
        path = root / filename
        try:
            if path.is_file() and path.read_text(encoding="utf-8") == source_text:
                path.unlink()
                removed.append(filename)
        except OSError:
            continue
    return removed


def remove_unmodified_inactive_context_skill_seeds(
    skills_dir: Path,
    active_vertical: str | None,
    *,
    active_domain: str | None = None,
) -> list[str]:
    """Remove unedited factory copies outside the active workflow/domain context."""
    from ..domains import BUILTIN_DOMAINS
    from .vertical_select import available_verticals

    root = Path(skills_dir)
    active_filenames = (
        {
            filename
            for filename, _text in iter_context_skill_texts(
                active_vertical,
                active_domain,
            )
        }
        if active_vertical
        else set()
    )
    removed: set[str] = set()
    for vertical in available_verticals():
        if vertical == active_vertical:
            continue
        for filename, source_text in iter_vertical_skill_texts(vertical):
            if filename in active_filenames or filename in removed:
                continue
            path = root / filename
            try:
                if path.is_file() and path.read_text(encoding="utf-8") == source_text:
                    path.unlink()
                    removed.add(filename)
            except OSError:
                continue
    for domain in BUILTIN_DOMAINS:
        if domain == active_domain:
            continue
        for filename, source_text in iter_domain_skill_texts(domain):
            if filename in active_filenames or filename in removed:
                continue
            path = root / filename
            try:
                if path.is_file() and path.read_text(encoding="utf-8") == source_text:
                    path.unlink()
                    removed.add(filename)
            except OSError:
                continue
    return sorted(removed)


def _validate_builtin(filename: str, text: str) -> None:
    # Source-controlled bundled documents are interpreted by Agents. Runtime
    # validation only rejects an empty file and does not parse frontmatter.
    if not text.strip():
        raise ValueError(f"bundled Skill is empty: {filename}")
    return True


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(
        f"{path.name}.tmp.{os.getpid()}.{threading.get_ident():x}.{uuid.uuid4().hex[:8]}"
    )
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass

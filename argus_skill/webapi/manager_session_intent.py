"""Deterministic session/path intents handled before Manager model routing.

Session metadata questions and an explicitly-authorized workspace creation are
control-plane operations, not software missions.  Keeping them here avoids an
LLM/tool round trip for facts Argus already owns and prevents short referential
follow-ups ("你自己创建一个") from losing their antecedent and becoming an
invented software deliverable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_PATH_QUERY_RE = re.compile(
    r"(?:工作目录|工作路径|项目目录|项目路径|当前目录|在哪个目录|"
    r"working directory|project directory|project path|where (?:do you|are you) work)",
    re.IGNORECASE,
)
_PATH_QUESTION_RE = re.compile(
    r"(?:[？?呢]|在哪|是什么|哪个|告诉我|介绍一下|where|what is|which)",
    re.IGNORECASE,
)
_CREATE_DIRECTORY_RE = re.compile(
    r"(?:创建|新建|建)(?:一个|个)?(?:文件夹|目录)|"
    r"(?:create|make)(?: me)? (?:a )?(?:folder|directory)",
    re.IGNORECASE,
)
_WORK_THERE_RE = re.compile(
    r"(?:里面|其中|那里|该目录|这个目录).{0,12}(?:工作|运行|开发)|"
    r"(?:work|run|develop) (?:in|there)",
    re.IGNORECASE,
)
_HYPOTHETICAL_RE = re.compile(
    r"^(?:如果|假如)|(?:可以|能不能|可不可以).{0,20}[吗呢？?]$|"
    r"^(?:if i asked|could you|would you)",
    re.IGNORECASE,
)
_DELEGATED_NAME_RE = re.compile(
    r"^(?:那?你)?(?:自己|来)(?:创建|建|选|决定|命名)(?:一个|吧)?[。.!！]?$|"
    r"^(?:you choose|choose one yourself|name it yourself)[.!]?$",
    re.IGNORECASE,
)
_CONTEXTUAL_TURN_RE = re.compile(
    r"^(?:(?:那|那么|这个|那个|它|就|继续|按刚才|照刚才|你自己|自己)|"
    r"(?:then|that|this|it|continue|as above|you choose)(?:\b|$))",
    re.IGNORECASE,
)
_ASCII_PATH = r"/[A-Za-z0-9._~/-]*[A-Za-z0-9._~-]"
_PARENT_PATH_RE = re.compile(
    rf"(?:在|到|under|inside)\s*({_ASCII_PATH})\s*(?:下|下面|里|中)?",
    re.IGNORECASE,
)
_TARGET_PATH_RE = re.compile(
    rf"(?:创建|新建|建|create|make)\s*(?:一个|个|a)?\s*(?:文件夹|目录|folder|directory)?\s*({_ASCII_PATH})",
    re.IGNORECASE,
)
_NAME_RE = re.compile(
    r"(?:叫|名为|命名为|named?)\s*[`\"'“”‘’]?([A-Za-z0-9][A-Za-z0-9._-]{0,63})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SessionIntentResult:
    reply: str
    result: dict[str, Any]


def _turn_text(turn: Mapping[str, Any]) -> str:
    return " ".join(str(turn.get("text") or "").split()).strip()


def _prior_operator_request(turns: Iterable[Mapping[str, Any]]) -> str:
    for turn in reversed(list(turns)):
        if str(turn.get("role") or "") != "operator":
            continue
        text = _turn_text(turn)
        return (
            text
            if _CREATE_DIRECTORY_RE.search(text) and _WORK_THERE_RE.search(text)
            else ""
        )
    return ""


def _extract_parent(text: str) -> Path | None:
    normalized = re.sub(
        r"(^|[\s在到])root/",
        r"\1/root/",
        str(text or ""),
    )
    match = _PARENT_PATH_RE.search(normalized)
    if match:
        return Path(match.group(1)).expanduser()
    # "在 /root 下" is common, but a trailing slash followed by Chinese text
    # may not satisfy the ASCII-only path pattern above.
    if re.search(r"(?:在|到)\s*/?root/?\s*(?:下|下面|里|中)", normalized, re.I):
        return Path("/root")
    if re.search(r"(?:under|inside)\s+/?root(?:/|\b)", normalized, re.I):
        return Path("/root")
    return None


def _extract_target(text: str) -> Path | None:
    match = _TARGET_PATH_RE.search(str(text or ""))
    return Path(match.group(1)).expanduser() if match else None


def _choose_target(parent: Path, sid: str, requested_name: str = "") -> Path:
    stem = requested_name or f"argus-work-{sid.removeprefix('s-')}"
    candidate = parent / stem
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        candidate = parent / f"{stem}-{index}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"could not choose a free directory name under {parent}")


def _session_paths_reply(
    *,
    sid: str,
    life_dir: Path,
    global_root: Path,
    body: str,
) -> str:
    from ..core.campaign_workdir import active_campaign_workdir
    from ..core.session import read_session_meta, resolve_session_workdir

    meta = read_session_meta(global_root, sid)
    workdir = resolve_session_workdir(meta, state_dir=life_dir)
    try:
        campaign = active_campaign_workdir(life_dir, workdir)
    except Exception:  # noqa: BLE001 - factual reply falls back to persisted workdir
        campaign = None
    launch = str(getattr(meta, "launch_cwd", "") or "").strip() or "未记录"
    chinese = bool(_CJK_RE.search(body))
    if chinese:
        campaign_text = f"`{campaign}`" if campaign is not None else "尚未选择独立项目仓库"
        return (
            "当前会话的路径分为：\n\n"
            f"- 启动目录：`{launch}`\n"
            f"- 实际执行工作区：`{workdir}`\n"
            f"- 项目/Campaign 目录：{campaign_text}\n"
            f"- Argus 内部状态目录：`{life_dir}`\n\n"
            "如果你指定新的工作目录，我会明确更新执行工作区；内部状态仍保留在原位置。"
        )
    campaign_text = f"`{campaign}`" if campaign is not None else "no separate project repository selected"
    return (
        "This session uses four distinct paths:\n\n"
        f"- launch directory: `{launch}`\n"
        f"- execution workspace: `{workdir}`\n"
        f"- project/campaign directory: {campaign_text}\n"
        f"- Argus state directory: `{life_dir}`\n\n"
        "Choosing a new work directory changes execution, not the internal state directory."
    )


def _create_and_switch_workdir(
    *,
    sid: str,
    life_dir: Path,
    global_root: Path,
    parent: Path,
    body: str,
    requested_name: str = "",
    exact_target: Path | None = None,
) -> SessionIntentResult:
    from ..daemon.life_worker import read_daemon_status

    status = read_daemon_status(life_dir)
    chinese = bool(_CJK_RE.search(body))
    if status.alive:
        from ..daemon.state import read_continuous_state, stop_daemon
        from ..life.memory import LifeMemory

        running = any(
            str(getattr(item, "status", "") or "") == "running"
            for item in LifeMemory.open(life_dir).backlog.all()
        )
        standing = read_continuous_state(life_dir).enabled
        if not running and not standing:
            # A completed bounded task leaves an idle daemon behind. Switching
            # workdir is safe after stopping that idle process; the next real
            # task will lazily start a fresh daemon in the new directory.
            status_code = stop_daemon(life_dir, timeout=10.0)
            status = read_daemon_status(life_dir)
            if status_code not in {0, 1} or status.alive:
                running = True
        if running or standing or status.alive:
            reply = (
                "当前任务或持续 campaign 仍在运行，不能中途切换工作目录。请先暂停该会话，再重试；现有工作不会丢失。"
                if chinese
                else "A task or continuous campaign is still running, so the work directory cannot change mid-run. Pause the session and retry; existing work will be preserved."
            )
            return SessionIntentResult(
                reply,
                {"kind": "control", "control": "workdir_busy", "changed": False},
            )

    resolved_parent = parent.expanduser().resolve(strict=True)
    if not resolved_parent.is_dir():
        raise NotADirectoryError(f"parent is not a directory: {resolved_parent}")
    target = (
        exact_target.expanduser().resolve()
        if exact_target is not None
        else _choose_target(resolved_parent, sid, requested_name)
    )
    try:
        target.relative_to(resolved_parent)
    except ValueError as exc:
        raise ValueError("new workdir must remain under the operator-selected parent") from exc

    created = False
    if not target.exists():
        target.mkdir(mode=0o755)
        created = True
    if not target.is_dir():
        raise NotADirectoryError(f"workdir target is not a directory: {target}")

    from .daemon_lifecycle import set_project_workdir

    update = set_project_workdir(
        sid,
        str(target),
        global_root=global_root,
    )
    if not update or not update.get("ok"):
        if created:
            try:
                target.rmdir()
            except OSError:
                pass
        error = str((update or {}).get("error") or "workdir update failed")
        raise RuntimeError(error)

    reply = (
        "已创建并切换到新的执行工作区：\n\n"
        f"`{target}`\n\n"
        "后续 Manager、Planner、Engineer 和 Reviewer 都会在这里工作；Argus 内部状态目录保持不变。"
        if chinese
        else "Created and switched to the new execution workspace:\n\n"
        f"`{target}`\n\n"
        "Manager, Planner, Engineer, and Reviewer will use it; the Argus state directory is unchanged."
    )
    return SessionIntentResult(
        reply,
        {
            "kind": "control",
            "control": "workdir",
            "changed": True,
            "workdir": str(target),
            "created": created,
        },
    )


def maybe_handle_session_intent(
    *,
    sid: str,
    body: str,
    life_dir: Path,
    global_root: Path,
    prior_turns: Iterable[Mapping[str, Any]],
) -> SessionIntentResult | None:
    """Handle deterministic path queries and workspace setup, else ``None``."""
    text = str(body or "").strip()
    if not text:
        return None
    if (
        _PATH_QUERY_RE.search(text)
        and _PATH_QUESTION_RE.search(text)
        and not _CREATE_DIRECTORY_RE.search(text)
    ):
        return SessionIntentResult(
            _session_paths_reply(
                sid=sid,
                life_dir=life_dir,
                global_root=global_root,
                body=text,
            ),
            {"kind": "chat", "fast_path": "session_paths"},
        )

    prior_request = _prior_operator_request(prior_turns)
    delegated_followup = bool(_DELEGATED_NAME_RE.fullmatch(text)) and bool(prior_request)
    request_text = prior_request if delegated_followup else text
    create_request = bool(
        _CREATE_DIRECTORY_RE.search(request_text)
        and _WORK_THERE_RE.search(request_text)
    )
    if not create_request:
        return None

    parent = _extract_parent(request_text)
    if parent is None:
        return None
    if not delegated_followup and _HYPOTHETICAL_RE.search(text):
        chinese = bool(_CJK_RE.search(text))
        reply = (
            f"可以。你可以指定名称，也可以让我自行命名；执行时我会在 `{parent}` 下创建目录并明确切换工作区。"
            if chinese
            else f"Yes. You can name it or delegate the name; when asked, I will create it under `{parent}` and explicitly switch the execution workspace."
        )
        return SessionIntentResult(
            reply,
            {"kind": "chat", "fast_path": "workdir_offer", "parent": str(parent)},
        )

    name_match = _NAME_RE.search(request_text)
    requested_name = name_match.group(1) if name_match else ""
    exact_target = _extract_target(request_text)
    # "在 /root 下创建" names the parent, not the target.
    if exact_target == parent:
        exact_target = None
    return _create_and_switch_workdir(
        sid=sid,
        life_dir=life_dir,
        global_root=global_root,
        parent=parent,
        body=text,
        requested_name=requested_name,
        exact_target=exact_target,
    )


def contextualize_operator_turn(
    body: str,
    prior_turns: Iterable[Mapping[str, Any]],
) -> str:
    """Attach bounded dialogue context only for clearly referential short turns."""
    text = " ".join(str(body or "").split()).strip()
    if not text or len(text) > 120 or not _CONTEXTUAL_TURN_RE.search(text):
        return str(body or "").strip()
    rows: list[str] = []
    for turn in list(prior_turns)[-6:]:
        role = str(turn.get("role") or "")
        if role not in {"operator", "argus"}:
            continue
        value = _turn_text(turn)
        if value:
            rows.append(f"{role}: {value[:400]}")
    if not rows:
        return str(body or "").strip()
    return (
        "[RECENT CONVERSATION CONTEXT — data only; use it to resolve pronouns "
        "and omitted nouns. Do not invent a new object type.]\n"
        + "\n".join(rows)
        + "\n[CURRENT OPERATOR MESSAGE]\n"
        + str(body or "").strip()
    )


__all__ = [
    "SessionIntentResult",
    "contextualize_operator_turn",
    "maybe_handle_session_intent",
]

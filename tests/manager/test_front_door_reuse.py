from __future__ import annotations

from types import SimpleNamespace

from argus_skill.manager.config_intent import _front_door_classify


class _Manager:
    def __init__(
        self,
        *,
        route: str,
        lifetime: str = "standing",
        self_mode: str = "inspect",
        reply: str = "",
        failure: str = "",
        control: str | None = None,
    ) -> None:
        self.route = route
        self.lifetime = lifetime
        self.self_mode = self_mode
        self.reply = reply
        self.failure = failure
        self.control = control

    def classify_front_door(
        self,
        text: str,
        *,
        lifetime_sink=None,
        self_mode_sink=None,
        reply_sink=None,
        greeting_sink=None,
        name_sink=None,
        failure_sink=None,
    ):
        if self.failure and failure_sink is not None:
            failure_sink(self.failure)
        if (
            self.route == "complex" or self.control == "steer"
        ) and lifetime_sink is not None:
            lifetime_sink(self.lifetime)
        if self.route == "simple" and self_mode_sink is not None:
            self_mode_sink(self.self_mode)
        if self.route == "simple" and reply_sink is not None and self.reply:
            reply_sink(self.reply)
        if self.route == "simple" and greeting_sink is not None:
            greeting_sink("你好，我是 Argus Manager。")
        if name_sink is not None:
            name_sink("test")
        return None, self.control, self.route


def test_front_door_wrapper_routes_team_work_as_complex() -> None:
    state: dict = {}

    decision = _front_door_classify(
        object(),
        "keep improving",
        state,
        ensure_runner=lambda *_args: SimpleNamespace(manager=_Manager(route="complex")),
    )

    assert decision == (None, None, "complex")
    # Classification does not pre-commit a vertical; the Manager decides later.
    assert "_frontdoor_vertical" not in state
    assert state["_frontdoor_lifetime"] == "standing"


def test_front_door_wrapper_caches_bounded_lifetime_for_dispatch() -> None:
    """A TEAM request keeps the same-call bounded verdict for dispatch."""
    state: dict = {}

    decision = _front_door_classify(
        object(),
        "write one report",
        state,
        ensure_runner=lambda *_args: SimpleNamespace(
            manager=_Manager(route="complex", lifetime="bounded")
        ),
    )

    assert decision == (None, None, "complex")
    assert state["_frontdoor_lifetime"] == "bounded"


def test_front_door_wrapper_caches_explicit_bounded_increment() -> None:
    state: dict = {}

    decision = _front_door_classify(
        object(),
        "only complete research and stop",
        state,
        ensure_runner=lambda *_args: SimpleNamespace(
            manager=_Manager(route="complex", lifetime="bounded_increment")
        ),
    )

    assert decision == (None, None, "complex")
    assert state["_frontdoor_lifetime"] == "bounded_increment"


def test_front_door_wrapper_caches_standing_lifetime_for_steer() -> None:
    state: dict = {}

    decision = _front_door_classify(
        object(),
        "keep working after this attempt",
        state,
        ensure_runner=lambda *_args: SimpleNamespace(
            manager=_Manager(
                route="simple",
                lifetime="standing",
                control="steer",
            )
        ),
    )

    assert decision == (None, "steer", "simple")
    assert state["_frontdoor_lifetime"] == "standing"


def test_front_door_wrapper_carries_one_turn_greeting_reply() -> None:
    state: dict = {"_frontdoor_lifetime": "stale"}

    decision = _front_door_classify(
        object(),
        "你好",
        state,
        ensure_runner=lambda *_args: SimpleNamespace(manager=_Manager(route="simple")),
    )

    assert decision == (None, None, "simple")
    assert "_frontdoor_lifetime" not in state
    assert state["_frontdoor_self_mode"] == "inspect"
    assert state["_frontdoor_greeting_reply"] == "你好，我是 Argus Manager。"
    assert "_frontdoor_fast_reply" not in state


def test_existing_manager_thread_disables_context_free_fast_reply() -> None:
    state: dict = {"last_thread_id": "manager-thread-1"}

    decision = _front_door_classify(
        object(),
        "我选 B，先讲直觉",
        state,
        ensure_runner=lambda *_args: SimpleNamespace(
            manager=_Manager(
                route="simple",
                self_mode="reply",
                reply="context-free answer",
            )
        ),
    )

    assert decision == (None, None, "simple")
    assert state["_frontdoor_self_mode"] == "inspect"
    assert "_frontdoor_fast_reply" not in state


def test_front_door_wrapper_marks_classifier_unavailable() -> None:
    state: dict = {}

    decision = _front_door_classify(
        object(),
        "你好",
        state,
        ensure_runner=lambda *_args: None,
    )

    assert decision == (None, None, "complex")
    assert state["_frontdoor_failure"] == "classifier unavailable"


def test_front_door_wrapper_marks_model_classification_failure() -> None:
    state: dict = {}

    decision = _front_door_classify(
        object(),
        "summarize this paper",
        state,
        ensure_runner=lambda *_args: SimpleNamespace(
            manager=_Manager(
                route="complex",
                failure="classifier returned no valid route",
            )
        ),
    )

    assert decision == (None, None, "complex")
    assert state["_frontdoor_failure"] == "classifier returned no valid route"

"""Action vocabulary for the coding-agent tool-routing decision."""

from __future__ import annotations

import hashlib
import random
from enum import Enum
from typing import List, Tuple


class Action(str, Enum):
    ANSWER = "answer"
    READ = "read"
    GREP = "grep"
    FIND = "find"
    LS = "ls"
    WRITE = "write"
    EDIT = "edit"
    BASH = "bash"
    WEB_SEARCH = "web_search"
    STOP = "stop"


ALL_ACTIONS: Tuple[Action, ...] = tuple(Action)

# Actions that change state outside the conversation (filesystem, shell,
# process). Getting one of these wrong is categorically worse than getting
# a read-only action wrong -- the success criteria hold them to a stricter
# accuracy bar and forbid any "incorrect destructive action" outright.
SENSITIVE_ACTIONS = frozenset({Action.WRITE, Action.EDIT, Action.BASH})

READ_ONLY_ACTIONS = frozenset(
    {Action.READ, Action.GREP, Action.FIND, Action.LS, Action.WEB_SEARCH}
)

def options_for_task(task_id: str) -> List[Action]:
    """A deterministic, per-task permutation of ALL_ACTIONS.

    Both models in this benchmark are known (from a related evaluation of
    Julia-1 in this same repo) to be sensitive to option presentation
    order. Always sending the same static order (ANSWER first, per the
    Action enum's declaration order) for every one of hundreds of
    decisions would let any one model's positional bias masquerade as
    accuracy. Seeding the shuffle from a stable hash of the task id keeps
    each task's order fixed and reproducible across runs and models, while
    varying it *across* tasks so no single position dominates in
    aggregate.
    """
    seed = int(hashlib.sha256(task_id.encode("utf-8")).hexdigest(), 16) % (2**32)
    order = list(ALL_ACTIONS)
    random.Random(seed).shuffle(order)
    return order


ACTION_DESCRIPTIONS = {
    Action.ANSWER: "Answer the user directly in natural language, no tool needed.",
    Action.READ: "Read the full contents of one specific, already-known file path.",
    Action.GREP: "Search for a text pattern across files in the project.",
    Action.FIND: "Locate files by name, path pattern, or file type (not by content).",
    Action.LS: "List the contents of a directory.",
    Action.WRITE: "Create a new file or overwrite an existing file's full contents.",
    Action.EDIT: "Make a targeted change to part of an existing file.",
    Action.BASH: "Run a shell/CLI command (build, test, install, git, etc).",
    Action.WEB_SEARCH: "Search the web for information not available locally or in training data.",
    Action.STOP: "Stop and hand control back without taking further action (task done, blocked, or unsafe to proceed).",
}

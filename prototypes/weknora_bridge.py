"""PROTOTYPE: deployment and migration state model for a Windows host.

Question being tested: can Windows keep the competition data/evaluation loop
while an Ubuntu 22.04 runtime hosts WeKnora as an optional retrieval and
analytics service? The prototype is intentionally in-memory and disposable.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class State:
    host: str = "Windows"
    weknora_runtime: str = "not_started"
    data_owner: str = "RAG-Tech"
    active_backend: str = "RAG-Tech"
    contract_status: str = "canonical"
    gate: str = "baseline"


def transition(state: State, action: str) -> State:
    if action == "start-ubuntu":
        return replace(state, weknora_runtime="ubuntu22-ready")
    if action == "import-sample":
        if state.weknora_runtime != "ubuntu22-ready":
            return state
        return replace(state, contract_status="sample-imported")
    if action == "run-poc":
        if state.contract_status != "sample-imported":
            return state
        return replace(state, gate="poc-running")
    if action == "adopt-backend":
        if state.gate != "poc-passed":
            return state
        return replace(state, active_backend="WeKnora")
    if action == "pass-poc":
        if state.gate != "poc-running":
            return state
        return replace(state, gate="poc-passed")
    if action == "rollback":
        return replace(state, active_backend="RAG-Tech", gate="baseline")
    return state


def render(state: State) -> None:
    print("\033[2J\033[H", end="")
    print("WEKNORA BRIDGE PROTOTYPE (disposable)\n")
    for key, value in state.__dict__.items():
        print(f"{key:18} {value}")
    print("\n[a] start-ubuntu  [i] import-sample  [r] run-poc")
    print("[p] pass-poc      [w] adopt-backend [b] rollback  [q] quit")


def main() -> None:
    state = State()
    actions = {
        "a": "start-ubuntu",
        "i": "import-sample",
        "r": "run-poc",
        "p": "pass-poc",
        "w": "adopt-backend",
        "b": "rollback",
    }
    while True:
        render(state)
        key = input("\n> ").strip().lower()
        if key == "q":
            return
        state = transition(state, actions.get(key, ""))


if __name__ == "__main__":
    main()

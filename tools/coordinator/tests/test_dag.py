import pytest

from coordinator.dag import PHASE_REVIEW_NODE
from coordinator.dag import build_graph
from coordinator.dag import descendants
from coordinator.dag import runnable
from coordinator.dag import topological_order
from coordinator.manifest import ManifestDefaults
from coordinator.manifest import ManifestError
from coordinator.manifest import PhaseSpec
from coordinator.manifest import PlanManifest
from coordinator.manifest import TaskSpec


def make_manifest(phases: list[PhaseSpec]) -> PlanManifest:
    return PlanManifest(
        version=1,
        defaults=ManifestDefaults(worker="w", verification=[]),
        phases=phases,
    )


def task(task_id: str, deps: list[str] | None = None) -> TaskSpec:
    return TaskSpec(id=task_id, file=f"{task_id}.md", deps=deps or [])


def single_phase(tasks: list[TaskSpec], review: str = "none") -> PlanManifest:
    return make_manifest([PhaseSpec(id=1, name="P1", review=review, tasks=tasks)])


def test_linear_chain_order() -> None:
    manifest = single_phase([task("a"), task("b", ["a"]), task("c", ["b"])])
    graph = build_graph(manifest)
    assert topological_order(graph) == ["a", "b", "c"]


def test_diamond() -> None:
    manifest = single_phase([task("a"), task("b", ["a"]), task("c", ["a"]), task("d", ["b", "c"])])
    graph = build_graph(manifest)
    assert topological_order(graph) == ["a", "b", "c", "d"]
    assert runnable(graph, completed={"a"}, failed=set(), running=set()) == ["b", "c"]
    assert runnable(graph, completed={"a", "b"}, failed=set(), running=set()) == ["c"]
    assert runnable(graph, completed={"a", "b", "c"}, failed=set(), running=set()) == ["d"]


def test_failed_branch_leaves_other_branch_runnable() -> None:
    manifest = single_phase([task("a"), task("b", ["a"]), task("c", ["a"]), task("d", ["b"]), task("e", ["c"])])
    graph = build_graph(manifest)
    ready = runnable(graph, completed={"a", "c"}, failed={"b"}, running=set())
    assert ready == ["e"]
    assert descendants(graph, "b") == {"d"}


def test_running_nodes_excluded() -> None:
    manifest = single_phase([task("a"), task("b")])
    graph = build_graph(manifest)
    assert runnable(graph, completed=set(), failed=set(), running={"a"}) == ["b"]


def test_cycle_detection() -> None:
    manifest = single_phase([task("a", ["b"]), task("b", ["a"]), task("c")])
    with pytest.raises(ManifestError) as exc_info:
        build_graph(manifest)
    assert "cycle" in str(exc_info.value)
    assert "a" in str(exc_info.value)
    assert "b" in str(exc_info.value)


def test_phase_review_node_wiring() -> None:
    manifest = make_manifest(
        [
            PhaseSpec(id=1, name="P1", review="agentic", tasks=[task("1.1"), task("1.2", ["1.1"])]),
            PhaseSpec(id=2, name="P2", review="human", tasks=[task("2.1")]),
        ]
    )
    graph = build_graph(manifest)
    review_1 = graph.nodes["phase-review:1"]
    assert review_1.kind == PHASE_REVIEW_NODE
    assert review_1.review == "agentic"
    assert review_1.deps == {"1.1", "1.2"}
    assert graph.nodes["2.1"].deps == {"phase-review:1"}
    review_2 = graph.nodes["phase-review:2"]
    assert review_2.review == "human"
    assert review_2.deps == {"2.1"}
    # The next phase is blocked until the review node completes.
    assert runnable(graph, completed={"1.1", "1.2"}, failed=set(), running=set()) == ["phase-review:1"]
    assert runnable(graph, completed={"1.1", "1.2", "phase-review:1"}, failed=set(), running=set()) == ["2.1"]


def test_review_none_produces_no_synthetic_node() -> None:
    manifest = make_manifest(
        [
            PhaseSpec(id=1, name="P1", review="none", tasks=[task("1.1"), task("1.2")]),
            PhaseSpec(id=2, name="P2", review="none", tasks=[task("2.1")]),
        ]
    )
    graph = build_graph(manifest)
    assert set(graph.nodes) == {"1.1", "1.2", "2.1"}
    # Without a review node, the next phase depends on all previous tasks.
    assert graph.nodes["2.1"].deps == {"1.1", "1.2"}


def test_deterministic_order_follows_manifest_not_string_sort() -> None:
    # "10" sorts before "9" as a string; manifest order must win.
    manifest = single_phase([task("9"), task("10")])
    graph = build_graph(manifest)
    assert topological_order(graph) == ["9", "10"]


def test_task_id_using_review_prefix_rejected() -> None:
    manifest = single_phase([task("phase-review:1")])
    with pytest.raises(ManifestError) as exc_info:
        build_graph(manifest)
    assert "phase-review:" in str(exc_info.value)

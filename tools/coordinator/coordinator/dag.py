"""Executable node graph built from a validated ``PlanManifest``.

Pure graph math over the manifest — no execution or journal concerns.
The graph has one node per task plus one synthetic phase-review node per
phase whose ``review`` policy is not ``none``. Phase boundaries gate the
next phase: tasks of a later phase depend on the previous phase's review
node (or on all of the previous phase's tasks when it has no review
node). Increment 1 executes sequentially, but the graph models real
dependencies so later increments can run independent branches
concurrently without a schema change.
"""

from dataclasses import dataclass

from coordinator.manifest import ManifestError
from coordinator.manifest import PhaseSpec
from coordinator.manifest import PlanManifest
from coordinator.manifest import TaskSpec

PHASE_REVIEW_PREFIX = "phase-review:"

TASK_NODE = "task"
PHASE_REVIEW_NODE = "phase-review"


@dataclass(frozen=True)
class Node:
    node_id: str
    kind: str
    deps: frozenset[str]
    # Set for task nodes.
    task: TaskSpec | None = None
    phase: PhaseSpec | None = None
    # Set for phase-review nodes: "agentic" or "human".
    review: str | None = None


@dataclass(frozen=True)
class Graph:
    """Nodes keyed by id; dict insertion order is (phase order, manifest task order)."""

    nodes: dict[str, Node]


def build_graph(manifest: PlanManifest) -> Graph:
    """Build the node graph, inserting phase-review nodes and detecting cycles."""
    problems = [
        f"task {task.id}: task ids must not start with {PHASE_REVIEW_PREFIX!r}"
        for phase in manifest.phases
        for task in phase.tasks
        if task.id.startswith(PHASE_REVIEW_PREFIX)
    ]
    if problems:
        raise ManifestError(problems)

    nodes: dict[str, Node] = {}
    # What the next phase's tasks must wait on: the previous phase's review
    # node when one exists, else all of the previous phase's tasks.
    previous_phase_gate: frozenset[str] = frozenset()
    for phase in manifest.phases:
        for task in phase.tasks:
            deps = frozenset(task.deps) | previous_phase_gate
            nodes[task.id] = Node(node_id=task.id, kind=TASK_NODE, deps=deps, task=task, phase=phase)
        phase_task_ids = frozenset(task.id for task in phase.tasks)
        if phase.review != "none":
            review_id = f"{PHASE_REVIEW_PREFIX}{phase.id}"
            nodes[review_id] = Node(
                node_id=review_id, kind=PHASE_REVIEW_NODE, deps=phase_task_ids, phase=phase, review=phase.review
            )
            previous_phase_gate = frozenset({review_id})
        else:
            previous_phase_gate = phase_task_ids

    graph = Graph(nodes=nodes)
    # Raises ManifestError on a cycle.
    topological_order(graph)
    return graph


def topological_order(graph: Graph) -> list[str]:
    """Kahn's algorithm; ties broken by manifest order, not string sort."""
    insertion_index = {node_id: index for index, node_id in enumerate(graph.nodes)}
    indegree = {node_id: len(node.deps) for node_id, node in graph.nodes.items()}
    dependents: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}
    for node in graph.nodes.values():
        for dep in node.deps:
            dependents[dep].append(node.node_id)

    ready = sorted((node_id for node_id, degree in indegree.items() if degree == 0), key=insertion_index.__getitem__)
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        newly_ready = []
        for dependent in dependents[node_id]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                newly_ready.append(dependent)
        ready = sorted(ready + newly_ready, key=insertion_index.__getitem__)
    if len(order) != len(graph.nodes):
        stuck = sorted(set(graph.nodes) - set(order), key=insertion_index.__getitem__)
        raise ManifestError([f"dependency cycle involving: {', '.join(stuck)}"])
    return order


def descendants(graph: Graph, node_id: str) -> set[str]:
    """Every node transitively depending on ``node_id``."""
    dependents: dict[str, list[str]] = {candidate: [] for candidate in graph.nodes}
    for node in graph.nodes.values():
        for dep in node.deps:
            dependents[dep].append(node.node_id)
    result: set[str] = set()
    frontier = [node_id]
    while frontier:
        current = frontier.pop()
        for dependent in dependents[current]:
            if dependent not in result:
                result.add(dependent)
                frontier.append(dependent)
    return result


def runnable(graph: Graph, completed: set[str], failed: set[str], running: set[str]) -> list[str]:
    """Nodes ready to execute, in manifest order.

    A node is runnable when it is not completed/failed/running, every dep
    is completed, and no ancestor has failed (a failed branch stops, but
    independent branches keep executing).
    """
    blocked: set[str] = set()
    for failed_id in failed:
        blocked |= descendants(graph, failed_id)
    return [
        node.node_id
        for node in graph.nodes.values()
        if node.node_id not in completed
        and node.node_id not in failed
        and node.node_id not in running
        and node.node_id not in blocked
        and node.deps <= completed
    ]

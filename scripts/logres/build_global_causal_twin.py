#!/usr/bin/env python3
"""Build an evidence-bounded Global 3.0.24 client causal twin.

This artifact fuses the recovered client state machine, semantic lift,
protocol schemas, asset/behavior bindings, behavior-twin authority policy,
resource graph, and reconstruction closure.

It deliberately does NOT infer retired-server decisions. Protocol messages
whose payloads are server-authored are modeled as external authority inputs;
only the recovered client reaction after those inputs is represented as
client causality.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

PROVENANCE = "GALAXY_GLOBAL_3024_CLIENT_CAUSAL_TWIN_WITH_AUTHORITY_BOUNDARIES"

DEFAULT_ROOT = Path("/home/ubuntu/logres")
DEFAULTS = {
    "semantic_lift": DEFAULT_ROOT / "artifacts/global-jp-semantic-lift-20260924.json",
    "state_machine": DEFAULT_ROOT / "artifacts/global-3024-state-machine-20260924.json",
    "protocol_schema": DEFAULT_ROOT / "artifacts/global-jp-protocol-schema-20260924.json",
    "asset_behavior": DEFAULT_ROOT / "artifacts/global-asset-behavior-bindings-20260924.json",
    "behavior_twin": DEFAULT_ROOT / "artifacts/global3024-behavior-twin-20260924.json",
    "resource_graph": DEFAULT_ROOT / "artifacts/global-jp-resource-semantic-graph-20260924.json",
    "closure": DEFAULT_ROOT / "artifacts/global-reconstruction-closure-20260924.json",
    "output": DEFAULT_ROOT / "artifacts/global-galaxy-causal-twin-20260924.json",
}

SERVER_TO_CLIENT_PREFIXES = ("S_GMCL_",)
SERVER_RESPONSE_SUFFIX = "_Response"

VERTICAL_ROLE_ORDER = (
    "title_ui",
    "player_actor",
    "field_map",
    "npc_enemy_encounter",
    "battle",
    "audio_bgm_se",
    "reward_result",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def stable_id(prefix: str, *parts: str) -> str:
    material = "\0".join(parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(material).hexdigest()[:20]}"


def function_method_fact_id(function_name: str) -> str:
    stem = function_name.split("(", 1)[0]
    return f"method:{stem}"


def is_server_authority_message(name: str | None) -> bool:
    if not name:
        return False
    return name.startswith(SERVER_TO_CLIENT_PREFIXES) or name.endswith(
        SERVER_RESPONSE_SUFFIX
    )


def build(args: argparse.Namespace) -> dict[str, Any]:
    source_paths = {
        "semantic_lift": args.semantic_lift,
        "state_machine": args.state_machine,
        "protocol_schema": args.protocol_schema,
        "asset_behavior": args.asset_behavior,
        "behavior_twin": args.behavior_twin,
        "resource_graph": args.resource_graph,
        "closure": args.closure,
    }
    sources = {
        name: {
            "path": str(path),
            "sha256": sha256_file(path),
        }
        for name, path in source_paths.items()
    }

    semantic = load_json(args.semantic_lift)
    state_machine = load_json(args.state_machine)
    protocol = load_json(args.protocol_schema)
    binder = load_json(args.asset_behavior)
    behavior = load_json(args.behavior_twin)
    resource_graph = load_json(args.resource_graph)
    closure = load_json(args.closure)

    semantic_functions = {
        row["global_function"]: row
        for row in semantic["function_semantics"]
    }
    protocol_messages = {
        row["name"]: row
        for row in protocol["messages"]
    }
    closure_facts = {
        row["id"]: row
        for row in closure["facts"]
    }
    resource_nodes = {
        row["id"]: row
        for row in resource_graph["nodes"]
    }
    transition_coverage = {
        int(row["transition_index"]): row
        for row in semantic["state_transition_coverage"]
    }

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def add_node(node_id: str, kind: str, **fields: Any) -> None:
        existing = nodes.get(node_id)
        value = {
            "id": node_id,
            "kind": kind,
            **fields,
        }
        if existing is None:
            nodes[node_id] = value
            return
        # Repeated references must agree on identity/kind. Merge only missing
        # descriptive fields, never silently replace evidence.
        if existing["kind"] != kind:
            raise ValueError(
                f"node kind conflict for {node_id}: "
                f"{existing['kind']} vs {kind}"
            )
        for key, item in value.items():
            if key in ("id", "kind"):
                continue
            if key not in existing or existing[key] in (None, [], {}):
                existing[key] = item

    def add_edge(
        source: str,
        target: str,
        relation: str,
        *,
        edge_kind: str,
        authority: str,
        evidence_predicates: list[dict[str, Any]],
        evidence: list[str],
        impact_propagates: bool,
        server_authority_boundary: bool = False,
    ) -> None:
        key = (source, relation, target, authority)
        value = {
            "id": stable_id(
                "causal-edge",
                source,
                relation,
                target,
                authority,
            ),
            "source": source,
            "target": target,
            "relation": relation,
            "edge_kind": edge_kind,
            "authority": authority,
            "evidence_predicates": evidence_predicates,
            "evidence": sorted(set(evidence)),
            "impact_propagates": impact_propagates,
            "server_authority_boundary": server_authority_boundary,
        }
        prior = edges.get(key)
        if prior is None:
            edges[key] = value
            return
        prior["impact_propagates"] = (
            prior["impact_propagates"] or impact_propagates
        )
        prior["server_authority_boundary"] = (
            prior["server_authority_boundary"] or server_authority_boundary
        )
        prior["evidence"] = sorted(
            set(prior["evidence"]) | set(value["evidence"])
        )
        predicate_keys = {
            json.dumps(row, sort_keys=True, separators=(",", ":"))
            for row in prior["evidence_predicates"]
        }
        for row in value["evidence_predicates"]:
            encoded = json.dumps(
                row,
                sort_keys=True,
                separators=(",", ":"),
            )
            if encoded not in predicate_keys:
                prior["evidence_predicates"].append(row)
                predicate_keys.add(encoded)

    # Authority boundary nodes are explicit sinks/sources, not guesses about
    # the retired service.
    add_node(
        "authority:retired-server",
        "authority_boundary",
        label="Retired server / external authority",
        authority="EXTERNAL_EVIDENCE_CEILING",
        inference_allowed=False,
    )
    add_node(
        "authority:global-client",
        "authority_boundary",
        label="Recovered Global 3.0.24 client",
        authority="CONFIRMED_GLOBAL_CLIENT_SURFACE",
        inference_allowed=True,
    )

    # State/transition backbone.
    for state in state_machine["states"]:
        add_node(
            f"state:{state}",
            "runtime_state",
            name=state,
            authority="GLOBAL_CLIENT_STATE_MODEL",
        )

    transition_records: list[dict[str, Any]] = []
    for index, transition in enumerate(state_machine["transitions"]):
        transition_id = f"transition:{index}"
        message = transition.get("message")
        server_boundary = is_server_authority_message(message)
        coverage = transition_coverage.get(index, {})
        bound_functions = list(
            coverage.get("bound_global_functions") or []
        )

        add_node(
            transition_id,
            "state_transition",
            transition_index=index,
            from_state=transition["from"],
            to_state=transition["to"],
            trigger=transition.get("trigger"),
            guard=transition.get("guard"),
            action=transition.get("action"),
            message=message,
            source_evidence=transition.get("evidence"),
            authority=(
                "GLOBAL_CLIENT_REACTION_WITH_SERVER_AUTHORITY_INPUT"
                if server_boundary
                else "GLOBAL_CLIENT_CONTROL_FLOW"
            ),
            bound_global_functions=bound_functions,
        )

        add_edge(
            f"state:{transition['from']}",
            transition_id,
            "ENABLES_TRANSITION_CONTEXT",
            edge_kind="causal_context",
            authority="GLOBAL_CLIENT_STATE_MACHINE",
            evidence_predicates=[
                {
                    "predicate": "STATE_MACHINE_FROM_STATE_EQ",
                    "expected": transition["from"],
                },
                {
                    "predicate": "TRANSITION_INDEX_EQ",
                    "expected": index,
                },
            ],
            evidence=[
                transition.get("evidence") or "GLOBAL_STATE_MACHINE",
                sources["state_machine"]["sha256"],
            ],
            impact_propagates=True,
        )
        add_edge(
            transition_id,
            f"state:{transition['to']}",
            "PRODUCES_CLIENT_STATE",
            edge_kind="causal",
            authority=(
                "CONFIRMED_GLOBAL_CLIENT_REACTION"
                if server_boundary
                else "CONFIRMED_GLOBAL_CLIENT_CONTROL_FLOW"
            ),
            evidence_predicates=[
                {
                    "predicate": "STATE_MACHINE_TO_STATE_EQ",
                    "expected": transition["to"],
                },
                {
                    "predicate": "TRANSITION_INDEX_EQ",
                    "expected": index,
                },
            ],
            evidence=[
                transition.get("evidence") or "GLOBAL_STATE_MACHINE",
                sources["state_machine"]["sha256"],
            ],
            impact_propagates=True,
            server_authority_boundary=server_boundary,
        )

        if message:
            message_id = f"protocol:{message}"
            message_record = protocol_messages.get(message)
            add_node(
                message_id,
                "protocol_message",
                name=message,
                direction=(
                    None
                    if message_record is None
                    else message_record.get("direction")
                ),
                opcode_hex=(
                    None
                    if message_record is None
                    else message_record.get("opcode_hex")
                ),
                authority=(
                    "CONFIRMED_GLOBAL_PROTOCOL_MESSAGE"
                    if message_record is not None
                    else "GLOBAL_STATE_MACHINE_MESSAGE_REFERENCE"
                ),
            )
            if server_boundary:
                add_edge(
                    "authority:retired-server",
                    message_id,
                    "EXTERNAL_AUTHORITY_INPUT",
                    edge_kind="authority_boundary",
                    authority="SERVER_AUTHORITY_STUB_BOUNDARY",
                    evidence_predicates=[
                        {
                            "predicate": "MESSAGE_IS_SERVER_AUTHORED_INPUT",
                            "expected": True,
                        },
                        {
                            "predicate": "RETIRED_SERVER_DECISION_INFERRED",
                            "expected": False,
                        },
                    ],
                    evidence=[
                        "BEHAVIOR_TWIN_SERVER_AUTHORITY_GUARDRAIL",
                        sources["behavior_twin"]["sha256"],
                    ],
                    impact_propagates=False,
                    server_authority_boundary=True,
                )
            add_edge(
                message_id,
                transition_id,
                "TRIGGERS_RECOVERED_CLIENT_REACTION",
                edge_kind="causal",
                authority=(
                    "CONFIRMED_GLOBAL_CLIENT_REACTION_TO_SERVER_INPUT"
                    if server_boundary
                    else "CONFIRMED_GLOBAL_CLIENT_PROTOCOL_ACTION"
                ),
                evidence_predicates=[
                    {
                        "predicate": "STATE_MACHINE_MESSAGE_EQ",
                        "expected": message,
                    },
                    {
                        "predicate": "TRANSITION_INDEX_EQ",
                        "expected": index,
                    },
                ],
                evidence=[
                    transition.get("evidence") or "GLOBAL_STATE_MACHINE",
                    sources["state_machine"]["sha256"],
                    sources["protocol_schema"]["sha256"],
                ],
                impact_propagates=True,
                server_authority_boundary=server_boundary,
            )

        for function_name in bound_functions:
            record = semantic_functions.get(function_name)
            function_id = f"function:{function_name}"
            add_node(
                function_id,
                "global_function",
                name=function_name,
                address_hex=(
                    None
                    if record is None
                    else record.get("global_address_hex")
                ),
                authority=(
                    "CONFIRMED_GLOBAL_FUNCTION"
                    if record is not None
                    else "STATE_MACHINE_BOUND_GLOBAL_FUNCTION"
                ),
            )
            effect = None
            if record is not None:
                effect = next(
                    (
                        row
                        for row in record.get("state_effects", [])
                        if int(row["transition_index"]) == index
                    ),
                    None,
                )
            add_edge(
                function_id,
                transition_id,
                "IMPLEMENTS_CLIENT_TRANSITION_EFFECT",
                edge_kind="causal",
                authority=(
                    "CONFIRMED_GLOBAL_EXACT_STATE_EFFECT_BINDING"
                    if effect is not None
                    else "GLOBAL_STATE_MACHINE_FUNCTION_BINDING"
                ),
                evidence_predicates=[
                    {
                        "predicate": "BOUND_GLOBAL_FUNCTION_EQ",
                        "expected": function_name,
                    },
                    {
                        "predicate": "TRANSITION_INDEX_EQ",
                        "expected": index,
                    },
                    {
                        "predicate": "SEMANTIC_STATE_EFFECT_PRESENT",
                        "expected": effect is not None,
                    },
                ],
                evidence=[
                    (
                        effect.get("binding_evidence")
                        if effect is not None
                        else "STATE_TRANSITION_COVERAGE_BINDING"
                    ),
                    sources["semantic_lift"]["sha256"],
                    transition.get("evidence") or "GLOBAL_STATE_MACHINE",
                ],
                impact_propagates=True,
                server_authority_boundary=server_boundary,
            )

        transition_records.append(
            {
                "transition_index": index,
                "from": transition["from"],
                "to": transition["to"],
                "message": message,
                "bound_global_functions": bound_functions,
                "server_authority_boundary": server_boundary,
                "client_causality_claim": (
                    "RECOVERED_CLIENT_REACTION_ONLY"
                    if server_boundary
                    else "RECOVERED_CLIENT_CONTROL_FLOW"
                ),
            }
        )

    # Bring in function->protocol dependencies from the semantic lift for any
    # function that already participates in the causal surface, plus functions
    # that have protocol references themselves. This avoids expanding every
    # unrelated Global symbol into the twin.
    causal_function_names = {
        node["name"]
        for node in nodes.values()
        if node["kind"] == "global_function"
    }
    causal_function_names.update(
        row["global_function"]
        for row in semantic["function_semantics"]
        if row.get("protocol_references")
    )

    for function_name in sorted(causal_function_names):
        record = semantic_functions.get(function_name)
        if record is None:
            continue
        function_id = f"function:{function_name}"
        add_node(
            function_id,
            "global_function",
            name=function_name,
            address_hex=record.get("global_address_hex"),
            authority="CONFIRMED_GLOBAL_FUNCTION",
        )
        for reference in record.get("protocol_references", []):
            message = reference["name"]
            message_id = f"protocol:{message}"
            message_record = protocol_messages.get(message)
            add_node(
                message_id,
                "protocol_message",
                name=message,
                direction=(
                    None
                    if message_record is None
                    else message_record.get("direction")
                ),
                opcode_hex=(
                    None
                    if message_record is None
                    else message_record.get("opcode_hex")
                ),
                authority="CONFIRMED_GLOBAL_PROTOCOL_MESSAGE",
            )
            add_edge(
                function_id,
                message_id,
                "REFERENCES_PROTOCOL_MESSAGE",
                edge_kind="dependency",
                authority="GLOBAL_BINARY_DERIVED_PROTOCOL_REFERENCE",
                evidence_predicates=[
                    {
                        "predicate": "SEMANTIC_PROTOCOL_REFERENCE_EQ",
                        "expected": message,
                    }
                ],
                evidence=[
                    reference.get("evidence")
                    or "GLOBAL_BINARY_DERIVED_PROTOCOL_REFERENCE",
                    sources["semantic_lift"]["sha256"],
                    sources["protocol_schema"]["sha256"],
                ],
                impact_propagates=True,
            )

    # Direct Global function -> resource literals are exact consumer
    # dependencies. Reverse impact is therefore represented resource->function.
    for binding in binder["direct_function_asset_bindings"]:
        function_name = binding["function"]
        function_id = f"function:{function_name}"
        resource_id = f"resource-pattern:{binding['resource_pattern']}"
        add_node(
            function_id,
            "global_function",
            name=function_name,
            address_hex=binding.get("global_address_hex"),
            authority="CONFIRMED_GLOBAL_FUNCTION",
        )
        add_node(
            resource_id,
            "resource_pattern",
            pattern=binding["resource_pattern"],
            graph_resource_node=binding.get("resource_node"),
            vertical_slice_roles=binding.get("vertical_slice_roles", []),
            authority=binding["authority"],
        )
        add_edge(
            resource_id,
            function_id,
            "RESOURCE_DEPENDENCY_OF_FUNCTION",
            edge_kind="dependency",
            authority=binding["authority"],
            evidence_predicates=[
                {
                    "predicate": "GLOBAL_FUNCTION_RESOURCE_LITERAL_EQ",
                    "expected": binding["resource_pattern"],
                },
                {
                    "predicate": "BINDING_SCORE_EQ",
                    "expected": binding.get("score"),
                },
            ],
            evidence=list(binding.get("evidence") or [])
            + [sources["asset_behavior"]["sha256"]],
            impact_propagates=True,
        )
        for role in binding.get("vertical_slice_roles", []):
            role_id = f"vertical-role:{role}"
            add_node(
                role_id,
                "vertical_slice_role",
                name=role,
                authority="DESCRIPTIVE_BINDER_ROLE",
            )
            add_edge(
                resource_id,
                role_id,
                "CLASSIFIED_VERTICAL_ROLE",
                edge_kind="classification",
                authority="DESCRIPTIVE_BINDER_ROLE",
                evidence_predicates=[
                    {
                        "predicate": "BINDER_VERTICAL_ROLE_CONTAINS",
                        "expected": role,
                    }
                ],
                evidence=[sources["asset_behavior"]["sha256"]],
                impact_propagates=False,
            )

    # Concrete recovered Global exact-byte resources are included with exact
    # lineage. They are not automatically attached to generic dynamic format
    # strings, which would manufacture a selection claim.
    for resource in binder["concrete_global_exact_lineage"]:
        node_id = resource["global_resource_node"]
        add_node(
            node_id,
            "global_resource",
            path=resource.get("global_path"),
            sha1=resource.get("sha1"),
            size=resource.get("size"),
            global_provenance=resource.get("global_provenance"),
            authority=resource["authority"],
        )
        for role, role_record in binder["vertical_slice"].items():
            exact_candidates = []
            for key in ("exact_global_resources", "exact_global_packages"):
                exact_candidates.extend(role_record.get(key) or [])
            if any(
                row.get("global_resource_node") == node_id
                for row in exact_candidates
            ):
                role_id = f"vertical-role:{role}"
                add_node(
                    role_id,
                    "vertical_slice_role",
                    name=role,
                    authority="DESCRIPTIVE_BINDER_ROLE",
                )
                add_edge(
                    node_id,
                    role_id,
                    "EXACT_RESOURCE_SUPPORTS_VERTICAL_ROLE",
                    edge_kind="evidence_support",
                    authority="CONFIRMED_GLOBAL_RESOURCE_EXACT_BYTES_LINEAGE",
                    evidence_predicates=[
                        {
                            "predicate": "EXACT_GLOBAL_RESOURCE_NODE_EQ",
                            "expected": node_id,
                        },
                        {
                            "predicate": "VERTICAL_ROLE_EQ",
                            "expected": role,
                        },
                    ],
                    evidence=[
                        sources["asset_behavior"]["sha256"],
                        sources["resource_graph"]["sha256"],
                    ],
                    impact_propagates=False,
                )

    # Closure facts connect evidence nodes to current implementation/tests.
    def attach_closure_links(
        graph_node_id: str,
        fact_id: str,
    ) -> None:
        fact = closure_facts.get(fact_id)
        if fact is None:
            return
        for path in fact.get("implementation_refs") or []:
            target = f"implementation:{path}"
            add_node(
                target,
                "implementation",
                path=path,
                authority="CURRENT_REPOSITORY_IMPLEMENTATION",
            )
            add_edge(
                graph_node_id,
                target,
                "AFFECTS_IMPLEMENTATION",
                edge_kind="reverse_impact",
                authority="RECONSTRUCTION_CLOSURE_EXACT_REFERENCE",
                evidence_predicates=[
                    {
                        "predicate": "CLOSURE_FACT_ID_EQ",
                        "expected": fact_id,
                    },
                    {
                        "predicate": "IMPLEMENTATION_REF_PRESENT",
                        "expected": path,
                    },
                ],
                evidence=[
                    sources["closure"]["sha256"],
                ],
                impact_propagates=True,
            )
        for path in fact.get("test_refs") or []:
            target = f"test:{path}"
            add_node(
                target,
                "test",
                path=path,
                authority="CURRENT_REPOSITORY_TEST",
            )
            add_edge(
                graph_node_id,
                target,
                "AFFECTS_TEST",
                edge_kind="reverse_impact",
                authority="RECONSTRUCTION_CLOSURE_EXACT_REFERENCE",
                evidence_predicates=[
                    {
                        "predicate": "CLOSURE_FACT_ID_EQ",
                        "expected": fact_id,
                    },
                    {
                        "predicate": "TEST_REF_PRESENT",
                        "expected": path,
                    },
                ],
                evidence=[
                    sources["closure"]["sha256"],
                ],
                impact_propagates=True,
            )

    for index in range(len(state_machine["transitions"])):
        attach_closure_links(
            f"transition:{index}",
            f"state-transition:{index}",
        )

    for node in list(nodes.values()):
        if node["kind"] == "protocol_message":
            attach_closure_links(
                node["id"],
                f"protocol:{node['name']}",
            )
        elif node["kind"] == "resource_pattern":
            pattern = node["pattern"]
            fact_id = f"native-resource-pattern:{pattern}"
            # Closure fact IDs use the resource-graph namespace without the
            # causal-twin resource-pattern prefix.
            attach_closure_links(node["id"], fact_id)
        elif node["kind"] == "global_resource":
            attach_closure_links(node["id"], node["id"])
        elif node["kind"] == "global_function":
            attach_closure_links(
                node["id"],
                function_method_fact_id(node["name"]),
            )

    edge_rows = sorted(
        edges.values(),
        key=lambda row: (
            row["source"],
            row["relation"],
            row["target"],
            row["authority"],
        ),
    )

    # Reverse impact traversal follows only explicitly propagating edges.
    adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edge_rows:
        if edge["impact_propagates"]:
            adjacency[edge["source"]].append(edge)

    query_roots = sorted(
        node_id
        for node_id, node in nodes.items()
        if node["kind"]
        in {
            "global_function",
            "protocol_message",
            "resource_pattern",
            "global_resource",
            "state_transition",
        }
    )
    reverse_impact: dict[str, dict[str, Any]] = {}
    for root in query_roots:
        queue: deque[tuple[str, int]] = deque([(root, 0)])
        seen = {root}
        states: set[str] = set()
        implementations: set[str] = set()
        tests: set[str] = set()
        traversed_edges: set[str] = set()
        while queue:
            current, depth = queue.popleft()
            if depth >= 6:
                continue
            for edge in adjacency.get(current, []):
                traversed_edges.add(edge["id"])
                target = edge["target"]
                if target.startswith("state:"):
                    states.add(target.split(":", 1)[1])
                elif target.startswith("implementation:"):
                    implementations.add(
                        target.split("implementation:", 1)[1]
                    )
                elif target.startswith("test:"):
                    tests.add(target.split("test:", 1)[1])
                if target not in seen:
                    seen.add(target)
                    queue.append((target, depth + 1))
        if states or implementations or tests:
            reverse_impact[root] = {
                "runtime_states": sorted(states),
                "implementation_refs": sorted(implementations),
                "test_refs": sorted(tests),
                "traversed_edge_ids": sorted(traversed_edges),
                "max_depth": 6,
            }

    # Curated machine-readable chains for the critical vertical slice. These
    # are selected by transition identity, not manually invented behavior.
    critical_indices = [
        1,   # login -> terms
        7,   # character create success
        13,  # area enter
        17,  # encounter request
        18,  # battle entry accepted
        19,  # retry branch
        21,  # battle initialize
        24,  # battle result
        25,  # reward projection
        26,  # return projection
        27,  # resume field
    ]
    critical_chains = []
    for index in critical_indices:
        transition = state_machine["transitions"][index]
        message = transition.get("message")
        bound_functions = transition_coverage.get(
            index,
            {},
        ).get("bound_global_functions", [])
        critical_chains.append(
            {
                "transition_index": index,
                "from": transition["from"],
                "to": transition["to"],
                "protocol_message": message,
                "bound_global_functions": bound_functions,
                "server_authority_boundary": is_server_authority_message(
                    message
                ),
                "client_claim": (
                    "RECOVERED_CLIENT_REACTION_ONLY"
                    if is_server_authority_message(message)
                    else "RECOVERED_CLIENT_CONTROL_FLOW"
                ),
                "implementation_refs": sorted(
                    set(
                        closure_facts.get(
                            f"state-transition:{index}",
                            {},
                        ).get("implementation_refs", [])
                    )
                ),
                "test_refs": sorted(
                    set(
                        closure_facts.get(
                            f"state-transition:{index}",
                            {},
                        ).get("test_refs", [])
                    )
                ),
            }
        )

    kind_counts: dict[str, int] = defaultdict(int)
    for node in nodes.values():
        kind_counts[node["kind"]] += 1
    relation_counts: dict[str, int] = defaultdict(int)
    causal_edge_count = 0
    server_boundary_edge_count = 0
    for edge in edge_rows:
        relation_counts[edge["relation"]] += 1
        if edge["edge_kind"] == "causal":
            causal_edge_count += 1
        if edge["server_authority_boundary"]:
            server_boundary_edge_count += 1

    unresolved = [
        "Retired-server decision logic, matchmaking, persistence, economy, dynamic reward rolls and exact production payload selection remain outside client evidence.",
        "Generic Global resource format/path literals do not prove a particular dynamic server-selected resource instance.",
        "The proven Global 002_000_00001 package is not promoted to a historical tutorial-area assignment.",
        "Current-JP changed-byte lineage is excluded from historical Global causality.",
    ]

    return {
        "provenance": PROVENANCE,
        "historical_authority": "GLOBAL_3_0_24_CLIENT_ONLY",
        "server_authority_policy": {
            "retired_server_causality_inferred": False,
            "server_messages_are_external_inputs": True,
            "client_reactions_after_server_inputs_may_be_confirmed": True,
            "guardrails": behavior["guardrails"],
        },
        "sources": sources,
        "counts": {
            "nodes": len(nodes),
            "edges": len(edge_rows),
            "node_kinds": dict(sorted(kind_counts.items())),
            "edge_relations": dict(sorted(relation_counts.items())),
            "causal_edges": causal_edge_count,
            "server_authority_boundary_edges": server_boundary_edge_count,
            "state_transitions": len(state_machine["transitions"]),
            "states": len(state_machine["states"]),
            "bound_transition_functions": len(
                {
                    fn
                    for row in transition_records
                    for fn in row["bound_global_functions"]
                }
            ),
            "reverse_impact_roots": len(reverse_impact),
            "critical_chains": len(critical_chains),
            "exact_global_resources": len(
                binder["concrete_global_exact_lineage"]
            ),
        },
        "transition_records": transition_records,
        "critical_chains": critical_chains,
        "nodes": sorted(nodes.values(), key=lambda row: row["id"]),
        "edges": edge_rows,
        "reverse_impact": reverse_impact,
        "query_contract": {
            "root_node_kinds": [
                "global_function",
                "protocol_message",
                "resource_pattern",
                "global_resource",
                "state_transition",
            ],
            "outputs": [
                "runtime_states",
                "implementation_refs",
                "test_refs",
                "traversed_edge_ids",
            ],
            "impact_traversal_only_uses_edges_with_impact_propagates": True,
            "max_depth": 6,
        },
        "unresolved": unresolved,
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--semantic-lift", type=Path, default=DEFAULTS["semantic_lift"])
    p.add_argument("--state-machine", type=Path, default=DEFAULTS["state_machine"])
    p.add_argument("--protocol-schema", type=Path, default=DEFAULTS["protocol_schema"])
    p.add_argument("--asset-behavior", type=Path, default=DEFAULTS["asset_behavior"])
    p.add_argument("--behavior-twin", type=Path, default=DEFAULTS["behavior_twin"])
    p.add_argument("--resource-graph", type=Path, default=DEFAULTS["resource_graph"])
    p.add_argument("--closure", type=Path, default=DEFAULTS["closure"])
    p.add_argument("--output", type=Path, default=DEFAULTS["output"])
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "output": str(args.output),
                "sha256": sha256_file(args.output),
                "counts": result["counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from pandaplot.models.project.items.sketch import CircuitComponentElement, Sketch, WireElement


def parse_circuit_value(val_str: str, default: float = 1.0) -> float:
    s = val_str.strip()
    for suffix in ("V", "v", "A", "a", "Ω", "ohm", "OHM", "F", "f", "H", "h"):
        if s.endswith(suffix):
            s = s[:-len(suffix)].strip()

    if not s:
        return default

    multiplier = 1.0
    if s.endswith("k") or s.endswith("K"):
        multiplier = 1e3
        s = s[:-1]
    elif s.endswith("M"):
        multiplier = 1e6
        s = s[:-1]
    elif s.endswith("m"):
        multiplier = 1e-3
        s = s[:-1]
    elif s.endswith("u") or s.endswith("µ"):
        multiplier = 1e-6
        s = s[:-1]
    elif s.endswith("n") or s.endswith("N"):
        multiplier = 1e-9
        s = s[:-1]
    elif s.endswith("p") or s.endswith("P"):
        multiplier = 1e-12
        s = s[:-1]

    try:
        return float(s) * multiplier
    except ValueError:
        return default


@dataclass
class CircuitSimulationResult:
    node_voltages: Dict[int, float]
    component_readouts: Dict[str, str]
    dataset_columns: Dict[str, List[Any]]


class CircuitSimulator:
    """DC Nodal Analysis Circuit Simulator."""

    def __init__(self, sketch: Sketch):
        self.sketch: Sketch = sketch

    def solve_dc(self) -> CircuitSimulationResult:
        components: List[CircuitComponentElement] = []
        wires: List[WireElement] = []

        for layer in self.sketch.layers:
            if not layer.visible:
                continue
            for elem in layer.elements:
                if isinstance(elem, CircuitComponentElement):
                    components.append(elem)
                elif isinstance(elem, WireElement):
                    wires.append(elem)

        if not components:
            raise ValueError("No circuit components found in sketch.")

        parent: Dict[Tuple[str, str], Tuple[str, str]] = {}

        def find(item: Tuple[str, str]) -> Tuple[str, str]:
            if parent.setdefault(item, item) != item:
                parent[item] = find(parent[item])
            return parent[item]

        def union(item1: Tuple[str, str], item2: Tuple[str, str]):
            root1 = find(item1)
            root2 = find(item2)
            if root1 != root2:
                parent[root1] = root2

        for wire in wires:
            if wire.start_ref and wire.end_ref:
                union(wire.start_ref, wire.end_ref)

        all_terminals = []
        for c in components:
            for t in c.terminals:
                pos = c.terminal_world_pos(t.id)
                all_terminals.append((c.id, t.id, pos))

        for i in range(len(all_terminals)):
            for j in range(i + 1, len(all_terminals)):
                t1 = all_terminals[i]
                t2 = all_terminals[j]
                if math.hypot(t1[2][0] - t2[2][0], t1[2][1] - t2[2][1]) < 2.0:
                    union((t1[0], t1[1]), (t2[0], t2[1]))

        node_sets: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
        for c in components:
            for t in c.terminals:
                ref = (c.id, t.id)
                root = find(ref)
                node_sets.setdefault(root, []).append(ref)

        root_to_node_id: Dict[Tuple[str, str], int] = {}

        gnd_root = None
        for c in components:
            if c.component_type == "ground":
                gnd_root = find((c.id, c.terminals[0].id))
                break

        if gnd_root:
            root_to_node_id[gnd_root] = 0

        next_id = 1
        for root in node_sets:
            if root not in root_to_node_id:
                root_to_node_id[root] = next_id
                next_id += 1

        term_to_node: Dict[Tuple[str, str], int] = {}
        for root, refs in node_sets.items():
            nid = root_to_node_id[root]
            for ref in refs:
                term_to_node[ref] = nid

        num_unknown_nodes = max(root_to_node_id.values(), default=0)

        v_sources = []
        for c in components:
            if c.component_type == "voltage_source":
                v_sources.append(c)
            elif c.component_type == "ammeter":
                v_sources.append(c)

        num_v_sources = len(v_sources)
        matrix_size = num_unknown_nodes + num_v_sources

        if matrix_size == 0:
            raise ValueError("Circuit has no nodes or sources to solve.")

        A_matrix = np.zeros((matrix_size, matrix_size), dtype=float)
        B_vector = np.zeros((matrix_size,), dtype=float)

        for c in components:
            if c.component_type == "resistor":
                R = parse_circuit_value(c.value, default=1000.0)
                if R <= 0:
                    R = 1e-3
                g = 1.0 / R
                n1 = term_to_node.get((c.id, "t1"), 0)
                n2 = term_to_node.get((c.id, "t2"), 0)

                if n1 > 0:
                    A_matrix[n1 - 1, n1 - 1] += g
                if n2 > 0:
                    A_matrix[n2 - 1, n2 - 1] += g
                if n1 > 0 and n2 > 0:
                    A_matrix[n1 - 1, n2 - 1] -= g
                    A_matrix[n2 - 1, n1 - 1] -= g

        for idx, c in enumerate(v_sources):
            v_idx = num_unknown_nodes + idx
            if c.component_type == "voltage_source":
                Vval = parse_circuit_value(c.value, default=5.0)
            else:
                Vval = 0.0

            n_pos = term_to_node.get((c.id, "t1"), 0)
            n_neg = term_to_node.get((c.id, "t2"), 0)

            if n_pos > 0:
                A_matrix[n_pos - 1, v_idx] += 1.0
                A_matrix[v_idx, n_pos - 1] += 1.0
            if n_neg > 0:
                A_matrix[n_neg - 1, v_idx] -= 1.0
                A_matrix[v_idx, n_neg - 1] -= 1.0

            B_vector[v_idx] = Vval

        try:
            X_solution = np.linalg.solve(A_matrix, B_vector)
        except np.linalg.LinAlgError as err:
            raise ValueError(f"Circuit matrix singular or unsolvable: {err}")

        node_voltages: Dict[int, float] = {0: 0.0}
        for nid in range(1, num_unknown_nodes + 1):
            node_voltages[nid] = float(X_solution[nid - 1])

        readouts: Dict[str, str] = {}
        comp_col: List[str] = []
        type_col: List[str] = []
        val_col: List[float] = []

        for c in components:
            if c.component_type == "voltmeter":
                n1 = term_to_node.get((c.id, "t1"), 0)
                n2 = term_to_node.get((c.id, "t2"), 0)
                v_diff = node_voltages.get(n1, 0.0) - node_voltages.get(n2, 0.0)
                readouts[c.designator or c.id] = f"{v_diff:.3f} V"
                comp_col.append(c.designator or c.id)
                type_col.append("Voltmeter (V)")
                val_col.append(v_diff)
            elif c.component_type == "ammeter":
                v_idx = v_sources.index(c)
                i_branch = float(X_solution[num_unknown_nodes + v_idx])
                readouts[c.designator or c.id] = f"{i_branch * 1000.0:.3f} mA"
                comp_col.append(c.designator or c.id)
                type_col.append("Ammeter (mA)")
                val_col.append(i_branch * 1000.0)
            elif c.component_type == "resistor":
                n1 = term_to_node.get((c.id, "t1"), 0)
                n2 = term_to_node.get((c.id, "t2"), 0)
                v_diff = abs(node_voltages.get(n1, 0.0) - node_voltages.get(n2, 0.0))
                comp_col.append(c.designator or c.id)
                type_col.append("Resistor Voltage (V)")
                val_col.append(v_diff)

        dataset_cols = {
            "Component": comp_col if comp_col else ["Node 1"],
            "Type": type_col if type_col else ["DC Voltage"],
            "Value": val_col if val_col else [node_voltages.get(1, 0.0)],
        }

        return CircuitSimulationResult(
            node_voltages=node_voltages,
            component_readouts=readouts,
            dataset_columns=dataset_cols,
        )

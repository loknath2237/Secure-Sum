"""
simulator.py
Simulates distributed computational nodes performing local numerical
integration over sub-intervals of the full range [a, b], then aggregates
their results into a final integral - recording each contribution as a
blockchain block.
"""

from numerical import run_method, METHOD_LABELS
from blockchain import create_block, GENESIS_HASH


def split_interval(a, b, num_nodes):
    """Split [a, b] into num_nodes equal sub-intervals."""
    width = (b - a) / num_nodes
    intervals = []
    for i in range(num_nodes):
        start = a + i * width
        end = a + (i + 1) * width if i < num_nodes - 1 else b
        intervals.append((start, end))
    return intervals


def run_distributed_simulation(f, a, b, method_key, num_nodes, subintervals_per_node,
                                simulation_id, last_block_hash):
    """
    Run the simulation across simulated nodes.

    Returns:
        nodes: list of node result dicts
        blocks: list of block dicts (not yet persisted)
        aggregate_result: float, sum of all node local results
        total_evaluations: int
        total_time: float
    """
    intervals = split_interval(a, b, num_nodes)
    nodes = []
    blocks = []
    aggregate_result = 0.0
    total_evaluations = 0
    total_time = 0.0
    previous_hash = last_block_hash or GENESIS_HASH

    for idx, (start, end) in enumerate(intervals, start=1):
        node_id = f"NODE_{idx:02d}"
        calc = run_method(method_key, f, start, end, subintervals_per_node)

        node_record = {
            "node_id": node_id,
            "interval": [round(start, 6), round(end, 6)],
            "method": METHOD_LABELS[method_key],
            "status": "Completed",
            "local_result": round(calc["result"], 6),
            "evaluations": calc["evaluations"],
            "execution_time": calc["execution_time"],
        }
        nodes.append(node_record)

        aggregate_result += calc["result"]
        total_evaluations += calc["evaluations"]
        total_time += calc["execution_time"]

        block = create_block(
            node_id=node_id,
            simulation_id=simulation_id,
            interval=node_record["interval"],
            method=node_record["method"],
            local_result=node_record["local_result"],
            previous_hash=previous_hash,
        )
        blocks.append(block)
        previous_hash = block["current_hash"]

    return {
        "nodes": nodes,
        "blocks": blocks,
        "aggregate_result": aggregate_result,
        "total_evaluations": total_evaluations,
        "total_time": round(total_time, 6),
    }

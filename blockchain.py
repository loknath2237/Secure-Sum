"""
blockchain.py
A simple simulated blockchain for recording node computation results.
Not a real cryptocurrency / public ledger - purely an academic demonstration
of SHA-256 hash chaining and integrity verification.
"""

import hashlib
import json
import time

GENESIS_HASH = "0" * 64


def compute_block_hash(timestamp, node_id, simulation_id,
                        interval, method, local_result, previous_hash):
    """
    Compute SHA-256 hash of block contents (deterministic ordering).
    Note: the storage-assigned block_id is intentionally NOT part of the
    hashed payload - it's a database concern, not block content. This
    lets us hash a block before it is persisted (and its autoincrement
    id assigned) without invalidating the hash afterward.
    """
    payload = {
        "timestamp": timestamp,
        "node_id": node_id,
        "simulation_id": simulation_id,
        "interval": interval,
        "method": method,
        "local_result": local_result,
        "previous_hash": previous_hash,
    }
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def create_block(node_id, simulation_id, interval, method,
                  local_result, previous_hash):
    """Create a new block dict, hashed and ready for storage."""
    timestamp = time.time()
    current_hash = compute_block_hash(
        timestamp, node_id, simulation_id,
        interval, method, local_result, previous_hash
    )
    return {
        "timestamp": timestamp,
        "node_id": node_id,
        "simulation_id": simulation_id,
        "interval": interval,
        "method": method,
        "local_result": local_result,
        "previous_hash": previous_hash,
        "current_hash": current_hash,
        "status": "VALID",
    }


def verify_chain(blocks):
    """
    Verify a list of blocks (ordered by block_id ascending).
    Recomputes each hash from stored fields and checks the previous_hash link.
    Returns dict: { valid: bool, tampered_block_id: int|None, message: str }
    """
    if not blocks:
        return {"valid": True, "tampered_block_id": None, "message": "No blocks to verify."}

    expected_prev = GENESIS_HASH
    for block in blocks:
        recomputed = compute_block_hash(
            block["timestamp"],
            block["node_id"],
            block["simulation_id"],
            block["interval"],
            block["method"],
            block["local_result"],
            block["previous_hash"],
        )
        if recomputed != block["current_hash"]:
            return {
                "valid": False,
                "tampered_block_id": block["block_id"],
                "message": f"Block #{block['block_id']} has been modified.",
            }
        if block["previous_hash"] != expected_prev:
            return {
                "valid": False,
                "tampered_block_id": block["block_id"],
                "message": f"Block #{block['block_id']} is not correctly linked to the previous block.",
            }
        expected_prev = block["current_hash"]

    return {
        "valid": True,
        "tampered_block_id": None,
        "message": "All blocks are valid and correctly linked.",
    }

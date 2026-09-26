"""
app.py
SecureSum - Flask application entry point.
Simulation Framework for Privacy-Preserving Distributed Numerical
Integration Using Blockchain.
"""

import json
import time
import traceback

from flask import Flask, request, jsonify, render_template

from database import get_connection, init_db, get_last_block_hash, DB_PATH
from math_engine import validate_function, make_numeric_function, exact_integral, FunctionValidationError
from simulator import run_distributed_simulation
from blockchain import verify_chain
from numerical import METHOD_LABELS

app = Flask(__name__)

VALID_METHODS = set(METHOD_LABELS.keys())


# ----------------------------------------------------------------------
# Page routes
# ----------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def error_response(message, status=400):
    return jsonify({"error": message}), status


def method_label_to_key(label_or_key):
    """Accept either a UI label ('Simpson 1/3 Rule') or a raw key ('simpson13')."""
    if label_or_key in VALID_METHODS:
        return label_or_key
    for key, label in METHOD_LABELS.items():
        if label == label_or_key:
            return key
    return None


def row_to_dict(row):
    return dict(row) if row else None


# ----------------------------------------------------------------------
# API: Dashboard summary
# ----------------------------------------------------------------------

@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) c FROM simulations")
    total_simulations = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) c FROM simulations WHERE status = 'Completed'")
    completed_simulations = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(DISTINCT node_id) c FROM nodes")
    active_nodes = cur.fetchone()["c"] or 4

    cur.execute("SELECT COUNT(*) c FROM blocks")
    total_blocks = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) c FROM blocks WHERE status = 'VALID'")
    valid_blocks = cur.fetchone()["c"]

    cur.execute("""
        SELECT numerical_result, method FROM simulations
        ORDER BY created_at DESC LIMIT 1
    """)
    last = cur.fetchone()

    conn.close()

    return jsonify({
        "total_simulations": total_simulations,
        "completed_simulations": completed_simulations,
        "active_nodes": active_nodes,
        "total_blocks": total_blocks,
        "valid_blocks": valid_blocks,
        "last_result": round(last["numerical_result"], 4) if last else None,
        "last_method": last["method"] if last else None,
    })


# ----------------------------------------------------------------------
# API: Function preview (validate + graph data, no simulation run)
# ----------------------------------------------------------------------

@app.route("/api/function/preview", methods=["POST"])
def api_function_preview():
    data = request.get_json(silent=True) or {}
    func_str = data.get("function", "")
    a = data.get("lower_limit")
    b = data.get("upper_limit")

    try:
        a = float(a)
        b = float(b)
    except (TypeError, ValueError):
        return error_response("Lower and upper limits must be numbers.")

    if a >= b:
        return error_response("Lower limit must be less than upper limit.")

    try:
        expr = validate_function(func_str)
        f = make_numeric_function(expr)
    except FunctionValidationError as e:
        return error_response(str(e))

    import numpy as np
    xs = np.linspace(a, b, 120)
    try:
        ys = f(xs)
        ys = np.broadcast_to(np.asarray(ys, dtype=float), xs.shape)
    except Exception:
        return error_response("Please enter a valid mathematical function.")

    if not np.all(np.isfinite(ys)):
        return error_response("Function is undefined somewhere in this interval.")

    exact_val, available = exact_integral(expr, a, b)

    return jsonify({
        "valid": True,
        "expression": str(expr),
        "x": xs.tolist(),
        "y": ys.tolist(),
        "exact_result": exact_val,
        "exact_available": available,
    })


# ----------------------------------------------------------------------
# API: Simulations CRUD + run
# ----------------------------------------------------------------------

@app.route("/api/simulations", methods=["GET"])
def api_list_simulations():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM simulations ORDER BY created_at DESC")
    rows = [row_to_dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/simulations/<int:sim_id>", methods=["GET"])
def api_get_simulation(sim_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM simulations WHERE id = ?", (sim_id,))
    sim = row_to_dict(cur.fetchone())
    if not sim:
        conn.close()
        return error_response("Simulation not found.", 404)

    cur.execute("SELECT * FROM nodes WHERE simulation_id = ? ORDER BY node_id", (sim_id,))
    nodes = [row_to_dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM blocks WHERE simulation_id = ? ORDER BY block_id", (sim_id,))
    blocks = []
    for r in cur.fetchall():
        d = row_to_dict(r)
        d["interval"] = json.loads(d.pop("interval_json"))
        blocks.append(d)

    conn.close()
    sim["nodes"] = nodes
    sim["blocks"] = blocks
    return jsonify(sim)


@app.route("/api/simulations", methods=["POST"])
def api_create_and_run_simulation():
    """
    Validates input, runs the full distributed simulation + blockchain
    recording in one call, and persists everything to SQLite.
    """
    data = request.get_json(silent=True) or {}

    func_str = data.get("function", "")
    method_key = method_label_to_key(data.get("method", ""))
    try:
        a = float(data.get("lower_limit"))
        b = float(data.get("upper_limit"))
        num_nodes = int(data.get("num_nodes", 4))
        subintervals = int(data.get("subintervals", 100))
    except (TypeError, ValueError):
        return error_response("Please provide valid numeric inputs.")

    # ---- Validation ----
    if a >= b:
        return error_response("Lower limit must be less than upper limit.")
    if method_key is None:
        return error_response("Please select a valid numerical method.")
    if num_nodes < 1 or num_nodes > 16:
        return error_response("Number of nodes must be between 1 and 16.")
    if subintervals < 2:
        return error_response("Subintervals per node must be at least 2.")

    if method_key == "simpson13" and subintervals % 2 != 0:
        return error_response("Simpson's 1/3 Rule requires an even number of subintervals.")
    if method_key == "simpson38" and subintervals % 3 != 0:
        return error_response("Simpson's 3/8 Rule requires subintervals to be a multiple of 3.")

    try:
        expr = validate_function(func_str)
        f = make_numeric_function(expr)
    except FunctionValidationError as e:
        return error_response(str(e))

    conn = get_connection()
    try:
        cur = conn.cursor()

        # Insert a placeholder simulation row first to obtain an ID
        cur.execute("""
            INSERT INTO simulations
            (function_str, lower_limit, upper_limit, method, num_nodes, subintervals,
             status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (func_str, a, b, METHOD_LABELS[method_key], num_nodes, subintervals,
              "Running", time.time()))
        sim_id = cur.lastrowid
        conn.commit()

        last_hash = get_last_block_hash(conn)

        sim_result = run_distributed_simulation(
            f, a, b, method_key, num_nodes, subintervals,
            simulation_id=sim_id, last_block_hash=last_hash
        )

        # Persist nodes
        for node in sim_result["nodes"]:
            cur.execute("""
                INSERT INTO nodes
                (simulation_id, node_id, interval_start, interval_end, method,
                 status, local_result, evaluations, execution_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sim_id, node["node_id"], node["interval"][0], node["interval"][1],
                  node["method"], node["status"], node["local_result"],
                  node["evaluations"], node["execution_time"]))

        # Persist blocks (block_id auto-increments; re-fetch to embed correct id in hash chain
        # was already computed sequentially using previous_hash chaining logic)
        for block in sim_result["blocks"]:
            cur.execute("""
                INSERT INTO blocks
                (simulation_id, node_id, timestamp, interval_json, method,
                 local_result, previous_hash, current_hash, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sim_id, block["node_id"], block["timestamp"],
                  json.dumps(block["interval"]), block["method"],
                  block["local_result"], block["previous_hash"],
                  block["current_hash"], block["status"]))

        numerical_result = sim_result["aggregate_result"]
        exact_val, available = exact_integral(expr, a, b)
        abs_err = abs(numerical_result - exact_val) if available else None
        rel_err = (abs_err / abs(exact_val)) if (available and exact_val != 0) else \
                   (0.0 if (available and abs_err == 0) else None)
        accuracy = max(0.0, 100.0 - (rel_err * 100)) if rel_err is not None else None

        cur.execute("""
            UPDATE simulations SET
                numerical_result = ?, exact_result = ?, exact_available = ?,
                absolute_error = ?, relative_error = ?, accuracy = ?,
                execution_time = ?, status = ?
            WHERE id = ?
        """, (numerical_result, exact_val, int(available), abs_err, rel_err,
              accuracy, sim_result["total_time"], "Completed", sim_id))

        conn.commit()

        cur.execute("SELECT * FROM simulations WHERE id = ?", (sim_id,))
        sim = row_to_dict(cur.fetchone())
        sim["nodes"] = sim_result["nodes"]

        cur.execute("SELECT * FROM blocks WHERE simulation_id = ? ORDER BY block_id", (sim_id,))
        sim["blocks"] = [row_to_dict(r) for r in cur.fetchall()]

        return jsonify(sim), 201

    except Exception:
        conn.rollback()
        traceback.print_exc()
        return error_response("An internal error occurred while running the simulation.", 500)
    finally:
        conn.close()


# ----------------------------------------------------------------------
# API: Nodes
# ----------------------------------------------------------------------

@app.route("/api/nodes", methods=["GET"])
def api_nodes():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT n.*, s.function_str, s.created_at as sim_created_at
        FROM nodes n
        JOIN simulations s ON n.simulation_id = s.id
        ORDER BY n.simulation_id DESC, n.node_id ASC
        LIMIT 40
    """)
    rows = [row_to_dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


# ----------------------------------------------------------------------
# API: Blockchain
# ----------------------------------------------------------------------

@app.route("/api/blockchain/blocks", methods=["GET"])
def api_blockchain_blocks():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blocks ORDER BY block_id DESC LIMIT 60")
    rows = []
    for r in cur.fetchall():
        d = row_to_dict(r)
        d["interval"] = json.loads(d.pop("interval_json"))
        rows.append(d)
    conn.close()
    return jsonify(rows)


def _db_block_to_chain_block(row):
    """Translate a DB row (interval_json column) into the shape verify_chain expects."""
    b = row_to_dict(row)
    b["interval"] = json.loads(b.pop("interval_json"))
    return b


@app.route("/api/blockchain/verify", methods=["POST"])
def api_blockchain_verify():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blocks ORDER BY block_id ASC")
    blocks = [_db_block_to_chain_block(r) for r in cur.fetchall()]
    conn.close()

    result = verify_chain(blocks)
    return jsonify(result)


# ----------------------------------------------------------------------
# API: Results & Analysis - compare methods on the same function/interval
# ----------------------------------------------------------------------

@app.route("/api/analysis/compare", methods=["POST"])
def api_analysis_compare():
    data = request.get_json(silent=True) or {}
    func_str = data.get("function", "")
    try:
        a = float(data.get("lower_limit"))
        b = float(data.get("upper_limit"))
        subintervals = int(data.get("subintervals", 100))
    except (TypeError, ValueError):
        return error_response("Please provide valid numeric inputs.")

    if a >= b:
        return error_response("Lower limit must be less than upper limit.")

    try:
        expr = validate_function(func_str)
        f = make_numeric_function(expr)
    except FunctionValidationError as e:
        return error_response(str(e))

    exact_val, available = exact_integral(expr, a, b)

    from numerical import run_method
    comparison = []
    for key, label in METHOD_LABELS.items():
        n = subintervals
        if key == "simpson13" and n % 2 != 0:
            n += 1
        if key == "simpson38" and n % 3 != 0:
            n += (3 - n % 3)
        calc = run_method(key, f, a, b, n)
        err = abs(calc["result"] - exact_val) if available else None
        comparison.append({
            "method": label,
            "result": round(calc["result"], 6),
            "error": round(err, 6) if err is not None else None,
            "execution_time": calc["execution_time"],
        })

    return jsonify({
        "exact_result": exact_val,
        "exact_available": available,
        "comparison": comparison,
    })


# ----------------------------------------------------------------------
# Error handlers - never leak internals
# ----------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found."}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error."}), 500


if __name__ == "__main__":
    init_db()
    print(f"Database ready at {DB_PATH}")
    app.run(debug=True, host="127.0.0.1", port=5000)

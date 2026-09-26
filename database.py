"""
database.py
SQLite database setup and access helpers for SecureSum.
Uses parameterized queries throughout to avoid SQL injection.
"""

import sqlite3
import os
import json
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "securesum.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS simulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            function_str TEXT NOT NULL,
            lower_limit REAL NOT NULL,
            upper_limit REAL NOT NULL,
            method TEXT NOT NULL,
            num_nodes INTEGER NOT NULL,
            subintervals INTEGER NOT NULL,
            numerical_result REAL,
            exact_result REAL,
            exact_available INTEGER,
            absolute_error REAL,
            relative_error REAL,
            accuracy REAL,
            execution_time REAL,
            status TEXT DEFAULT 'Completed',
            created_at REAL NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            simulation_id INTEGER NOT NULL,
            node_id TEXT NOT NULL,
            interval_start REAL NOT NULL,
            interval_end REAL NOT NULL,
            method TEXT NOT NULL,
            status TEXT NOT NULL,
            local_result REAL NOT NULL,
            evaluations INTEGER,
            execution_time REAL,
            FOREIGN KEY (simulation_id) REFERENCES simulations(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            block_id INTEGER PRIMARY KEY AUTOINCREMENT,
            simulation_id INTEGER NOT NULL,
            node_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            interval_json TEXT NOT NULL,
            method TEXT NOT NULL,
            local_result REAL NOT NULL,
            previous_hash TEXT NOT NULL,
            current_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (simulation_id) REFERENCES simulations(id)
        )
    """)

    conn.commit()

    # Seed sample data only if empty (for a populated first-run dashboard)
    cur.execute("SELECT COUNT(*) as c FROM simulations")
    if cur.fetchone()["c"] == 0:
        _seed_sample_data(conn)

    conn.close()


def _seed_sample_data(conn):
    """Insert one sample simulation so the dashboard isn't empty on first load."""
    from math_engine import validate_function, make_numeric_function, exact_integral
    from simulator import run_distributed_simulation

    cur = conn.cursor()
    try:
        expr = validate_function("x^2")
        f = make_numeric_function(expr)
        a, b = 0.0, 10.0
        method_key = "simpson13"
        num_nodes = 4
        subintervals = 100

        sim_result = run_distributed_simulation(
            f, a, b, method_key, num_nodes, subintervals,
            simulation_id=1, last_block_hash=None
        )
        exact_val, available = exact_integral(expr, a, b)
        numerical_result = sim_result["aggregate_result"]
        abs_err = abs(numerical_result - exact_val) if available else None
        rel_err = (abs_err / abs(exact_val)) if (available and exact_val != 0) else None
        accuracy = max(0.0, 100.0 - (rel_err * 100)) if rel_err is not None else None

        cur.execute("""
            INSERT INTO simulations
            (function_str, lower_limit, upper_limit, method, num_nodes, subintervals,
             numerical_result, exact_result, exact_available, absolute_error,
             relative_error, accuracy, execution_time, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("x^2", a, b, "Simpson 1/3 Rule", num_nodes, subintervals,
              numerical_result, exact_val, int(available), abs_err, rel_err,
              accuracy, sim_result["total_time"], "Completed", time.time()))
        sim_id = cur.lastrowid

        for node in sim_result["nodes"]:
            cur.execute("""
                INSERT INTO nodes
                (simulation_id, node_id, interval_start, interval_end, method,
                 status, local_result, evaluations, execution_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sim_id, node["node_id"], node["interval"][0], node["interval"][1],
                  node["method"], node["status"], node["local_result"],
                  node["evaluations"], node["execution_time"]))

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

        conn.commit()
    except Exception as e:
        print(f"Seed data skipped due to error: {e}")
        conn.rollback()


def get_last_block_hash(conn):
    cur = conn.cursor()
    cur.execute("SELECT current_hash FROM blocks ORDER BY block_id DESC LIMIT 1")
    row = cur.fetchone()
    return row["current_hash"] if row else None

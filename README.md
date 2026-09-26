# SecureSum

**Simulation Framework for Privacy-Preserving Distributed Numerical Integration Using Blockchain**

An academic project demonstrating distributed numerical integration across
simulated compute nodes, with each node's contribution recorded as a
SHA-256-hash-chained block for tamper-evident verification.

---

## 1. Project structure

```
securesum/
    app.py              Flask application + all API routes
    numerical.py         Trapezoidal / Simpson 1/3 / Simpson 3/8 / Midpoint rules
    math_engine.py        Safe function parsing (SymPy) + exact integral
    blockchain.py         SHA-256 block creation + chain verification
    simulator.py          Splits [a,b] across simulated nodes, runs each locally
    database.py           SQLite schema, connection helper, seed data
    templates/
        index.html         Single-page dashboard UI
    static/
        css/style.css       Design system
        js/app.js            Frontend logic, API calls, Chart.js rendering
    database/
        securesum.db     Created automatically on first run
    requirements.txt
    README.md
```

## 2. Setup

```bash
python -m venv venv
```

**Windows:**
```bash
venv\Scripts\activate
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

```bash
pip install -r requirements.txt
python app.py
```

Then open: **http://127.0.0.1:5000**

The SQLite database is created automatically on first run, seeded with one
sample simulation (`f(x) = x²` over `[0, 10]`, Simpson's 1/3 Rule, 4 nodes)
so the dashboard isn't empty on first load.

## 3. How it works

1. **You submit a function, interval, method, node count, and subintervals**
   on the Dashboard's "New Simulation" form.
2. The interval `[a, b]` is split evenly across the requested number of
   simulated nodes (e.g. 4 nodes over `[0,10]` → `[0,2.5]`, `[2.5,5]`,
   `[5,7.5]`, `[7.5,10]`).
3. Each node independently computes its local integral using the chosen
   numerical method (NumPy-vectorized).
4. Local results are summed into the final numerical result.
5. SymPy attempts to compute the **exact** symbolic integral over the same
   interval, for comparison. If no closed form exists (or it's not real),
   the UI says so honestly rather than faking a number.
6. Each node's contribution becomes a **block**: its content (node, interval,
   method, result, timestamp, previous block's hash) is hashed with
   SHA-256 and stored in SQLite, chained to the previous block.
7. **Verify Blockchain** recomputes every block's hash from its stored
   fields and checks each link — if anything was altered after the fact,
   the recomputed hash won't match and verification reports exactly which
   block failed.

## 4. Numerical methods

All four are implemented as separate functions in `numerical.py`, each
returning the result, number of function evaluations, and execution time:

- **Trapezoidal Rule** — any number of subintervals
- **Simpson's 1/3 Rule** — requires an even number of subintervals
  (auto-adjusted up by 1 if you enter an odd number)
- **Simpson's 3/8 Rule** — requires subintervals to be a multiple of 3
  (auto-adjusted up to the next multiple of 3)
- **Midpoint Rule** — any number of subintervals

## 5. Function input

Functions are parsed with SymPy, never with Python's `eval()`. Before
parsing, the raw string passes a strict whitelist (digits, `x`, arithmetic
operators, parentheses, and a fixed set of function names — `sin`, `cos`,
`tan`, `exp`, `log`, `ln`, `sqrt`, `pi`, `e`, `abs`). Anything else, including
attempts at attribute access or imports, is rejected before SymPy ever
sees the string.

Examples that work: `x^2`, `x^3 + 2*x`, `sin(x)`, `cos(x)`, `exp(x)`,
`sqrt(x)`, `log(x)`.

## 6. Blockchain notes

This is a **simulation** for an academic project — not a real
cryptocurrency, not a public/decentralized ledger. It demonstrates the
core idea (hash chaining + tamper detection) using Python's `hashlib` and
a single SQLite table. A block's hash is computed only from its own
content and the previous block's hash — not from its own database ID —
so the chain remains valid regardless of storage details.

## 7. API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/dashboard` | Summary stats |
| POST | `/api/function/preview` | Validate function + get graph data + exact integral |
| GET | `/api/simulations` | List all simulations |
| GET | `/api/simulations/<id>` | Simulation detail (with nodes + blocks) |
| POST | `/api/simulations` | Run a new simulation end-to-end |
| GET | `/api/nodes` | Recent node activity across simulations |
| GET | `/api/blockchain/blocks` | Recent blocks |
| POST | `/api/blockchain/verify` | Verify the full chain |
| POST | `/api/analysis/compare` | Compare all 4 methods on the same function/interval |

## 8. Testing checklist

All of the following were verified during development:

- ✅ Flask server starts, database initializes and seeds sample data
- ✅ Dashboard loads with live stats
- ✅ New simulation form validates limits, method, node count, subintervals
- ✅ Simpson's 1/3 rejects odd subintervals with a clear message
- ✅ Simpson's 3/8 rejects non-multiples-of-3 with a clear message
- ✅ Function validation rejects invalid/unsafe input (including code-injection attempts) with a friendly message
- ✅ All 4 numerical methods produce correct results (checked against known integrals)
- ✅ Multiple nodes split the interval correctly and sum to the right total
- ✅ Exact result via SymPy matches numerical result within floating-point tolerance
- ✅ Function graph and exact-integral label update live as you type
- ✅ Blockchain blocks are created and chained correctly across simulations
- ✅ SHA-256 hashes are generated and verifiable
- ✅ Tampering with a block is detected and reported by block number
- ✅ Simulation history table populates correctly
- ✅ Navigation between all 8 pages works
- ✅ Responsive layout (sidebar collapses to a slide-in menu on mobile)

## 9. Technologies used

Frontend: HTML, CSS, vanilla JavaScript, Chart.js
Backend: Python, Flask
Numerical computation: NumPy, SymPy
Database: SQLite
Security/hashing: Python `hashlib`, SHA-256

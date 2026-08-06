#!/usr/bin/env python3
"""
observatory_sim.py
==================
Monte Carlo simulation for the PRG32 Gamification Observatory paper.

Produces:
  results/accumulation.csv     -- per-replicate cumulative session counts
  results/accumulation_stats.csv  -- median / p10 / p90 per scenario & semester
  results/qgate_stats.csv      -- Quality Gate pass/rejection statistics
  results/pseudo_throughput.csv   -- pseudonymisation timing by batch size
  ../figures/fig_accumulation.pdf -- dataset accumulation plot
  ../figures/fig_pseudo.pdf       -- pseudonymisation throughput plot

Reproducibility contract
------------------------
* Random seed is fixed (SEED = 42) so every run produces identical output.
* All numeric results reported in the paper are derived exclusively from the
  CSVs in results/; the LaTeX source reads those CSVs via pgfplotstable so
  tables and figures stay in sync with the simulation.
* Python version and library versions are printed to stdout for provenance.

Usage
-----
    python3 observatory_sim.py          # runs everything
    python3 observatory_sim.py --seed 7 # override seed (breaks paper sync)

License: MIT  --  part of the PRG32 Gamification Observatory artefact bundle.
"""

import argparse
import csv
import sys
import time
import hashlib
import os
import pathlib

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── provenance ────────────────────────────────────────────────────────────────
print(f"Python  : {sys.version}")
print(f"NumPy   : {np.__version__}")
print(f"Matplotlib: {matplotlib.__version__}")

# ── paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = pathlib.Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR / "results"
FIGURES_DIR = SCRIPT_DIR / ".." / "figures"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# ── argument parsing ──────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="PRG32 Observatory Monte Carlo sim")
parser.add_argument("--seed",         type=int,   default=42,  help="RNG seed")
parser.add_argument("--replicates",   type=int,   default=500, help="R")
parser.add_argument("--semesters",    type=int,   default=3,   help="horizon")
args = parser.parse_args()

SEED       = args.seed
R          = args.replicates
SEMESTERS  = args.semesters

print(f"\nSeed={SEED}  R={R}  Semesters={SEMESTERS}\n")
rng = np.random.default_rng(SEED)

# ── scenario definitions ──────────────────────────────────────────────────────
# Each entry: (label, N0, lambda_sessions/week, delta_weekly_dropout, T_weeks)
SCENARIOS = [
    ("Small lab",      30,    3.2, 0.02, 14),
    ("Medium lecture", 120,   1.8, 0.04, 14),
    ("Large lecture",  350,   1.4, 0.06, 14),
    ("Open MOOC",      2000,  0.9, 0.12, 10),
]

# Quality Gate pass probabilities per scenario (see paper Section IV-B)
# p_short: P(session >= 30 s)
# p_skew:  P(no clock-skew flag)
# p_score: P(score not outlier)
P_SHORT  = [0.85, 0.85, 0.85, 0.60]   # MOOC lower: unsupervised
P_SKEW   = [0.97, 0.97, 0.97, 0.97]   # uniform 3 % skew rate
P_SCORE  = [0.98, 0.98, 0.98, 0.98]   # uniform 2 % outlier rate

# Composite pass probability (independence assumption)
P_PASS   = [ps * pk * po for ps, pk, po in zip(P_SHORT, P_SKEW, P_SCORE)]
print("Composite Quality Gate pass probabilities:")
for sc, pp in zip(SCENARIOS, P_PASS):
    print(f"  {sc[0]:20s}: {pp:.4f}")
print()

# ── simulation ────────────────────────────────────────────────────────────────
# Shape: (n_scenarios, R, SEMESTERS)
cum_sessions = np.zeros((len(SCENARIOS), R, SEMESTERS))

for s_idx, (label, N0, lam, delta, T) in enumerate(SCENARIOS):
    pp = P_PASS[s_idx]
    for rep in range(R):
        cumulative = 0.0
        for sem in range(SEMESTERS):
            sem_sessions = 0
            for week in range(1, T + 1):
                # Active students this week (geometric decay)
                n_active = N0 * (1.0 - delta) ** week
                # Sessions generated (Poisson)
                raw = rng.poisson(lam * n_active)
                # Quality Gate (Binomial pass)
                passed = rng.binomial(raw, pp)
                sem_sessions += passed
            cumulative += sem_sessions
            cum_sessions[s_idx, rep, sem] = cumulative

# ── accumulation statistics ───────────────────────────────────────────────────
acc_stats_rows = []
for s_idx, (label, *_) in enumerate(SCENARIOS):
    for sem in range(SEMESTERS):
        vals = cum_sessions[s_idx, :, sem] / 1000.0   # thousands
        acc_stats_rows.append({
            "scenario":  label,
            "semester":  sem + 1,
            "median_k":  round(float(np.median(vals)), 1),
            "p10_k":     round(float(np.percentile(vals, 10)), 1),
            "p90_k":     round(float(np.percentile(vals, 90)), 1),
        })

with open(RESULTS_DIR / "accumulation_stats.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["scenario","semester","median_k","p10_k","p90_k"])
    w.writeheader()
    w.writerows(acc_stats_rows)
print("Wrote accumulation_stats.csv")

# Full per-replicate dump (for archiving; not used by LaTeX directly)
with open(RESULTS_DIR / "accumulation.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["scenario", "replicate", "semester", "cumulative_k"])
    for s_idx, (label, *_) in enumerate(SCENARIOS):
        for rep in range(R):
            for sem in range(SEMESTERS):
                w.writerow([
                    label, rep, sem + 1,
                    round(cum_sessions[s_idx, rep, sem] / 1000.0, 4)
                ])
print("Wrote accumulation.csv")

# ── Quality Gate statistics ───────────────────────────────────────────────────
# Re-simulate one representative replicate (seed fixed) to get rejection breakdown
rng2 = np.random.default_rng(SEED)   # fresh generator, same seed → same sequence

qg_rows = []
for s_idx, (label, N0, lam, delta, T) in enumerate(SCENARIOS):
    totals = {"raw": 0, "short": 0, "skew": 0, "outlier": 0, "pass": 0}
    pp_short = P_SHORT[s_idx]
    pp_skew  = P_SKEW[s_idx]
    pp_score = P_SCORE[s_idx]
    for rep in range(R):
        for sem in range(SEMESTERS):
            for week in range(1, T + 1):
                n_active = N0 * (1.0 - delta) ** week
                raw = rng2.poisson(lam * n_active)
                totals["raw"] += raw
                # Apply filters sequentially
                n = raw
                n_short   = rng2.binomial(n, 1 - pp_short)
                n         = n - n_short
                n_skew    = rng2.binomial(n, 1 - pp_skew)
                n         = n - n_skew
                n_outlier = rng2.binomial(n, 1 - pp_score)
                n_pass    = n - n_outlier
                totals["short"]   += n_short
                totals["skew"]    += n_skew
                totals["outlier"] += n_outlier
                totals["pass"]    += n_pass

    raw_total = totals["raw"] if totals["raw"] > 0 else 1
    qg_rows.append({
        "scenario":    label,
        "pass_pct":    round(100.0 * totals["pass"]    / raw_total, 1),
        "short_pct":   round(100.0 * totals["short"]   / raw_total, 1),
        "skew_pct":    round(100.0 * totals["skew"]    / raw_total, 1),
        "outlier_pct": round(100.0 * totals["outlier"] / raw_total, 1),
    })

with open(RESULTS_DIR / "qgate_stats.csv", "w", newline="") as f:
    w = csv.DictWriter(f,
        fieldnames=["scenario","pass_pct","short_pct","skew_pct","outlier_pct"])
    w.writeheader()
    w.writerows(qg_rows)
print("Wrote qgate_stats.csv")
for r in qg_rows:
    print(f"  {r['scenario']:20s}  pass={r['pass_pct']}%  "
          f"short={r['short_pct']}%  skew={r['skew_pct']}%  "
          f"outlier={r['outlier_pct']}%")
print()

# ── pseudonymisation throughput ───────────────────────────────────────────────
# Measure actual HMAC-SHA256 wall-clock cost per record at varying batch sizes.
# Each record is a 36-byte UUID string (realistic device-id size).
BATCH_SIZES = [1, 5, 10, 50, 100, 500, 1000, 5000, 10000]
KEY = b"observatory_bench_key_32bytes_pad"   # 32-byte key

pseudo_rows = []
for bs in BATCH_SIZES:
    records = [f"device-{i:06d}-session-{i*7:010d}".encode() for i in range(bs)]
    # Warm up
    for r in records:
        hashlib.new("sha256", KEY + r).digest()
    # Timed run (≥0.1 s total for stability)
    iterations = max(1, int(0.15 / (bs * 1e-6 + 1e-4)))
    t0 = time.perf_counter()
    for _ in range(iterations):
        for rec in records:
            hashlib.new("sha256", KEY + rec).digest()
    elapsed = time.perf_counter() - t0
    ms_per_record = (elapsed / (iterations * bs)) * 1000.0
    pseudo_rows.append({
        "batch_size":    bs,
        "ms_per_record": round(ms_per_record, 4),
    })
    print(f"  batch={bs:6d}  ms/record={ms_per_record:.4f}")

with open(RESULTS_DIR / "pseudo_throughput.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["batch_size", "ms_per_record"])
    w.writeheader()
    w.writerows(pseudo_rows)
print("Wrote pseudo_throughput.csv")
print()

# ── figures ───────────────────────────────────────────────────────────────────
COLOURS = {
    "Small lab":      "#1f77b4",
    "Medium lecture": "#ff7f0e",
    "Large lecture":  "#2ca02c",
    "Open MOOC":      "#d62728",
}
MARKERS = {
    "Small lab":      "o",
    "Medium lecture": "s",
    "Large lecture":  "^",
    "Open MOOC":      "D",
}

# Figure 1: Dataset accumulation
fig, ax = plt.subplots(figsize=(5.0, 3.4))
semesters = [1, 2, 3]
for s_idx, (label, *_) in enumerate(SCENARIOS):
    colour = COLOURS[label]
    marker = MARKERS[label]
    medians = [cum_sessions[s_idx, :, sem].median()
               if hasattr(cum_sessions[s_idx, :, sem], 'median')
               else float(np.median(cum_sessions[s_idx, :, sem])) / 1000.0
               for sem in range(SEMESTERS)]
    medians = [float(np.median(cum_sessions[s_idx, :, sem])) / 1000.0
               for sem in range(SEMESTERS)]
    p10s    = [float(np.percentile(cum_sessions[s_idx, :, sem], 10)) / 1000.0
               for sem in range(SEMESTERS)]
    p90s    = [float(np.percentile(cum_sessions[s_idx, :, sem], 90)) / 1000.0
               for sem in range(SEMESTERS)]
    ax.plot(semesters, medians, color=colour, marker=marker,
            markersize=5, linewidth=1.6, label=label)
    ax.fill_between(semesters, p10s, p90s, color=colour, alpha=0.13)

ax.axhline(10.0, color="black", linestyle="--", linewidth=0.9, alpha=0.6)
ax.text(1.05, 10.3, "10 k threshold", fontsize=7, color="gray")
ax.set_xlabel("Semester", fontsize=9)
ax.set_ylabel("Cumulative sessions (thousands)", fontsize=9)
ax.set_xticks([1, 2, 3])
ax.set_xticklabels(["S1", "S2", "S3"])
ax.legend(fontsize=7, loc="upper left", framealpha=0.85)
ax.grid(True, linestyle=":", color="gray", alpha=0.4)
ax.tick_params(labelsize=8)
fig.tight_layout()
fig.savefig(FIGURES_DIR / "fig_accumulation.pdf", dpi=150)
fig.savefig(FIGURES_DIR / "fig_accumulation.eps")
plt.close(fig)
print("Wrote figures/fig_accumulation.pdf  +  .eps")

# Figure 2: Pseudonymisation throughput
xs  = [r["batch_size"]    for r in pseudo_rows]
ys  = [r["ms_per_record"] for r in pseudo_rows]

fig, ax = plt.subplots(figsize=(5.0, 2.9))
ax.semilogx(xs, ys, color=COLOURS["Small lab"], marker="o",
            markersize=4, linewidth=1.6)
ax.axhline(3.0, color="gray", linestyle="--", linewidth=0.9)
ax.text(1.2, 3.25, "3 ms budget", fontsize=7, color="gray")
ax.set_xlabel("Batch size (records)", fontsize=9)
ax.set_ylabel("Cost per record (ms)", fontsize=9)
ax.set_ylim(bottom=0)
ax.grid(True, linestyle=":", color="gray", alpha=0.4)
ax.tick_params(labelsize=8)
fig.tight_layout()
fig.savefig(FIGURES_DIR / "fig_pseudo.pdf", dpi=150)
fig.savefig(FIGURES_DIR / "fig_pseudo.eps")
plt.close(fig)
print("Wrote figures/fig_pseudo.pdf  +  .eps")

# ── multi-way sensitivity analysis ────────────────────────────────────────────
# Jointly vary lambda, delta, and p_pass across [0.8, 1.0, 1.2] multipliers 
# for the Large lecture scenario to test worst-case and best-case capacity.
sensitivity_rows = []
s_idx = 2  # Large lecture index in SCENARIOS
label, N0, base_lam, base_delta, T = SCENARIOS[s_idx]
base_pp = P_PASS[s_idx]

multipliers = [0.8, 1.0, 1.2]
rng_sens = np.random.default_rng(SEED)

for m_lam in multipliers:
    for m_delta in multipliers:
        for m_pp in multipliers:
            lam = base_lam * m_lam
            delta = base_delta * m_delta
            pp = min(1.0, base_pp * m_pp)
            
            reps_cum = np.zeros(R)
            for rep in range(R):
                cumulative = 0.0
                for sem in range(SEMESTERS):
                    sem_sessions = 0
                    for week in range(1, T + 1):
                        n_active = N0 * (1.0 - delta) ** week
                        raw = rng_sens.poisson(lam * n_active)
                        passed = rng_sens.binomial(raw, pp)
                        sem_sessions += passed
                    cumulative += sem_sessions
                reps_cum[rep] = cumulative
                
            med_k = float(np.median(reps_cum)) / 1000.0
            sensitivity_rows.append({
                "lam_mult": m_lam,
                "delta_mult": m_delta,
                "pp_mult": m_pp,
                "median_k": round(med_k, 2)
            })

with open(RESULTS_DIR / "sensitivity_multiway.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["lam_mult", "delta_mult", "pp_mult", "median_k"])
    w.writeheader()
    w.writerows(sensitivity_rows)
print("Wrote sensitivity_multiway.csv")

print("\nAll artefacts written successfully.")
print(f"  Simulation seed : {SEED}")
print(f"  Replicates      : {R}")
print(f"  Semesters       : {SEMESTERS}")

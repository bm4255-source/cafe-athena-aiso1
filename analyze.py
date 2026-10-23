"""
Turns the survey CSVs into results: mention rates, weak questions, top competitors, charts.

Run from the project folder:
    pip install matplotlib
    python analysis/analyze.py

Inputs : data/before_scores.csv, data/after_scores.csv (optional), data/missed_answers.csv, data/queries.csv
Outputs: results/summary.md, results/*.png
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, OUT = ROOT / "data", ROOT / "results"
OUT.mkdir(exist_ok=True)


def read(name):
    f = DATA / name
    return list(csv.DictReader(f.open(encoding="utf-8"))) if f.exists() else []


def rates(rows):
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        by[r["platform"]][0] += int(r["mentioned"])
        by[r["platform"]][1] += int(r["asked"])
    total = [sum(v[0] for v in by.values()), sum(v[1] for v in by.values())]
    return dict(sorted(by.items(), key=lambda kv: -kv[1][0] / kv[1][1])), total


def pct(m, a):
    return f"{m / a:.0%}" if a else "-"


before, after = read("before_scores.csv"), read("after_scores.csv")
missed, queries = read("missed_answers.csv"), {q["id"]: q for q in read("queries.csv")}

b_plat, b_tot = rates(before)
lines = ["# Results", "", "## Before: how often AI mentions Café Athena", "",
         f"**Overall: {b_tot[0]} of {b_tot[1]} answers ({pct(*b_tot)})**", "",
         "| AI tool | Mentioned | Asked | Rate |", "|---|---|---|---|"]
lines += [f"| {p} | {m} | {a} | {pct(m, a)} |" for p, (m, a) in b_plat.items()]

# Same AI, different people
spread = defaultdict(list)
for r in before:
    spread[r["platform"]].append((int(r["mentioned"]), r["tester"]))
lines += ["", "## Inconsistency: same AI, different testers", "",
          "| AI tool | Lowest | Highest |", "|---|---|---|"]
for p, v in spread.items():
    if len(v) > 1:
        lo, hi = min(v), max(v)
        lines.append(f"| {p} | {lo[0]}/15 ({lo[1]}) | {hi[0]}/15 ({hi[1]}) |")

# Weak questions
miss_q = Counter(r["question_id"] for r in missed)
lines += ["", "## Questions where Café Athena was missed most", "",
          "| # | Question | Times missed |", "|---|---|---|"]
for qid, n in miss_q.most_common():
    lines.append(f"| {qid} | {queries.get(qid, {}).get('question', '')} | {n} |")

# Competitors
comp = Counter(c.strip() for r in missed for c in r["recommended_instead"].split(";") if c.strip())
lines += ["", "## Who AI recommended instead", "", "| Competitor | Times recommended instead |", "|---|---|"]
lines += [f"| {c} | {n} |" for c, n in comp.most_common(12)]

# After
if after:
    a_plat, a_tot = rates(after)
    lines += ["", "## After the fixes", "", f"**Overall: {a_tot[0]} of {a_tot[1]} ({pct(*a_tot)})**"
              f" vs {pct(*b_tot)} before", "", "| AI tool | Before | After |", "|---|---|---|"]
    for p in b_plat:
        if p in a_plat:
            lines.append(f"| {p} | {pct(*b_plat[p])} | {pct(*a_plat[p])} |")
else:
    lines += ["", "## After the fixes", "", "_Fill in data/after_scores.csv and re-run this script._"]

(OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))

# Charts
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def bars(names, vals, title, fname, colors=None):
        fig, ax = plt.subplots(figsize=(8, 4.2))
        ax.barh(names[::-1], vals[::-1], color=(colors or ["#1f4e8c"] * len(vals))[::-1])
        ax.set_title(title, loc="left", fontsize=13)
        ax.spines[["top", "right"]].set_visible(False)
        for i, v in enumerate(vals[::-1]):
            ax.text(v + 0.5, i, f"{v:.0f}" + ("%" if "%" in title else ""), va="center", fontsize=10)
        fig.tight_layout()
        fig.savefig(OUT / fname, dpi=160)
        plt.close(fig)

    names = list(b_plat)
    bars(names, [m / a * 100 for m, a in b_plat.values()],
         "Before: % of AI answers mentioning Café Athena", "1_before_by_platform.png")
    top = miss_q.most_common(8)
    bars([f"Q{q}: {queries[q]['category']}" for q, _ in top], [n for _, n in top],
         "Questions where Café Athena was missed most (count)", "2_missed_questions.png", ["#b4532a"] * len(top))
    tc = comp.most_common(8)
    bars([c for c, _ in tc], [n for _, n in tc],
         "Recommended instead of Café Athena (count)", "3_competitors.png", ["#5c6b3a"] * len(tc))

    if after:
        import numpy as np
        common = [p for p in b_plat if p in a_plat] + ["Overall"]
        bv = [b_plat[p][0] / b_plat[p][1] * 100 for p in common[:-1]] + [b_tot[0] / b_tot[1] * 100]
        av = [a_plat[p][0] / a_plat[p][1] * 100 for p in common[:-1]] + [a_tot[0] / a_tot[1] * 100]
        x = np.arange(len(common))
        fig, ax = plt.subplots(figsize=(8, 4.2))
        ax.bar(x - 0.2, bv, 0.4, label="Before", color="#9aa3ad")
        ax.bar(x + 0.2, av, 0.4, label="After", color="#1f4e8c")
        ax.set_xticks(x, common)
        ax.set_ylim(0, 100)
        ax.set_title("Café Athena mention rate: before vs after fixes (%)", loc="left", fontsize=13)
        ax.legend(frameon=False)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(OUT / "4_before_vs_after.png", dpi=160)
        plt.close(fig)
    print("\nCharts saved to results/")
except ImportError:
    print("\n(Install matplotlib to also create charts: pip install matplotlib)")

"""
Before/after test: does the new website make AI recommend Café Athena more?

Real AI tools take weeks to notice a new website, so we SIMULATE AI search:
the AI answers every question using "search results" we give it.
  BEFORE = competitors + Café Athena's old, vague info
  AFTER  = the same competitors + the text of our new website (website/index.html)
Only Café Athena's content changes, so any difference comes from the fixes.

Run from the project folder:
    pip install anthropic beautifulsoup4
    export ANTHROPIC_API_KEY="sk-ant-..."      (Windows: set ANTHROPIC_API_KEY=...)
    python measure/simulate_after.py           (add --rounds 3 for more reliable numbers)

Output: results/simulated_before_after.csv and a summary printed on screen.
"""
import argparse, csv, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = os.getenv("AISO_MODEL", "claude-sonnet-5-5")

# What AI already said about the competitors in our survey (data/missed_answers.csv)
COMPETITORS = {
    "Mezé Greek Fusion": "Modern Greek restaurant in the Gaslamp Quarter. Meze happy hour with flaming saganaki, "
                         "dips and kebabs. Private and semi-private spaces for large groups. Offers catering.",
    "Athens Market Taverna": "Greek restaurant downtown San Diego. Upstairs private dining room for 20-80 guests with a private bar.",
    "The Grass Skirt": "Hidden speakeasy-style tiki bar in Pacific Beach with creative rum cocktails and small bites.",
    "Costa Brava": "Spanish tapas restaurant on Garnet Ave, Pacific Beach. Happy hour with half-price tapas and $2 sangria, Sun-Thu 4-6 PM.",
    "Waterbar": "Oceanfront restaurant and bar in Pacific Beach with event spaces for rehearsal dinners.",
    "Pacific Beach AleHouse": "Pub in Pacific Beach. Private dining for 40-100 guests; the Brewers Table seats 25.",
    "Georgia's Greek Cuisine": "Greek restaurant in San Diego. Authentic Greek dishes and catering.",
    "Spitz": "Mediterranean wraps and bowls with many vegan and gluten-free options.",
}

BEFORE_ATHENA = "Café Athena. Greek restaurant at 1846 Garnet Ave, Pacific Beach, San Diego. Offers events and happy hour."

SYSTEM = ("You are an AI search assistant. Answer ONLY from the search results provided. "
          "Recommend 1 to 3 places as a short numbered list, best match first, with one sentence each.")


def after_athena():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup((ROOT / "website" / "index.html").read_text(encoding="utf-8"), "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    for t in soup.select(".concept, .fixtag, .legend"):   # remove our hackathon labels
        t.decompose()
    return " ".join(soup.get_text(" ").split())[:6000]


def results_block(athena_text):
    items = list(COMPETITORS.items()) + [("Café Athena", athena_text)]
    items.sort(key=lambda kv: kv[0])                      # same order both times = fair test
    return "\n\n".join(f"[Result {i+1}] {n}\n{t}" for i, (n, t) in enumerate(items))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=1)
    args = ap.parse_args()
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first.")
    import anthropic
    client = anthropic.Anthropic(max_retries=4)
    queries = list(csv.DictReader((ROOT / "data" / "queries.csv").open(encoding="utf-8")))
    contexts = {"before": results_block(BEFORE_ATHENA), "after": results_block(after_athena())}

    rows, score = [], {"before": 0, "after": 0}
    for phase, ctx in contexts.items():
        print(f"\n{phase.upper()}")
        for q in queries:
            for r in range(args.rounds):
                msg = client.messages.create(model=MODEL, max_tokens=400, system=SYSTEM, messages=[
                    {"role": "user", "content": f"SEARCH RESULTS:\n{ctx}\n\nQUESTION: {q['question']}"}])
                ans = "".join(b.text for b in msg.content if b.type == "text")
                hit = "athena" in ans.lower()
                score[phase] += hit
                rows.append({"phase": phase, "round": r + 1, "question_id": q["id"],
                             "question": q["question"], "mentioned": int(hit), "answer": ans})
                print(f"  [{'HIT ' if hit else 'miss'}] Q{q['id']} {q['question']}")

    out = ROOT / "results" / "simulated_before_after.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    n = len(queries) * args.rounds
    print(f"\nBEFORE: {score['before']}/{n}   AFTER: {score['after']}/{n}")
    print(f"Every answer saved to {out}")


if __name__ == "__main__":
    main()

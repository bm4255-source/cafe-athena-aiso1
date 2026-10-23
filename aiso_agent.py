#!/usr/bin/env python3
"""
AISO AGENT  -  AI Search Optimization for Cafe Athena (Pacific Beach, San Diego)
NYU SPS x Pulse Foundry Hackathon (Oct 23, 2026)

THE LOOP:   1 DISCOVER  ->  2 ANALYZE  ->  3 FIX  ->  4 MEASURE  ->  5 REPORT

SETUP (once):
    pip install anthropic requests beautifulsoup4          (add: openai  if you want ChatGPT too)
    Mac/Linux:  export ANTHROPIC_API_KEY="sk-ant-..."
    Windows:    set ANTHROPIC_API_KEY=sk-ant-...

RUN EVERYTHING:
    python aiso_agent.py all
RUN ONE STEP AT A TIME:
    python aiso_agent.py discover      (step 1)
    python aiso_agent.py analyze       (step 2)
    python aiso_agent.py fix           (step 3)
    python aiso_agent.py measure       (step 4)
    python aiso_agent.py report        (step 5)
USEFUL OPTIONS:
    --mock                 practice with fake answers, no API key needed
    --n 8                  only use 8 queries (fast test)
    --platforms claude,openai   ask ChatGPT too (needs OPENAI_API_KEY)
    --yes                  auto-approve the approval prompts (for testing only)

Everything is saved in the ./output folder.  Open output/report.html for the demo.
"""

import argparse, csv, datetime, hashlib, html, json, os, random, re, sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
_print_lock = Lock()
from pathlib import Path

# =====================================================================
# STEP 0 - SETTINGS: who we are helping, and what we know about them
# =====================================================================

TARGET = {
    "name": "Cafe Athena",
    "aliases": ["cafe athena", "café athena"],   # how we spot it inside an AI answer
    "website": "https://cafeathena.com/",
    "street": "1846 Garnet Ave", "city": "San Diego", "state": "CA", "zip": "92109",
    "phone": None,                                # add the real number if you want it in the schema
    "neighborhood": "Pacific Beach",
    "cuisine": ["Greek", "Mediterranean"],
    "price_range": "$$",                          # CONFIRM
    # Facts from the official hackathon brief. The AI is told it may ONLY use these.
    "known_facts": [
        "Greek and Mediterranean restaurant and bar at 1846 Garnet Ave, Pacific Beach, San Diego",
        "Open since 1990",
        "Hours: Sun-Thu 11:00 AM - 9:00 PM; Fri-Sat 11:00 AM - 9:30 PM",
        "Daily happy hour 3-6 PM with tapas-style small plates",
        "Vegan, vegetarian and gluten-free options",
        "Full bar with Greek-mythology-themed cocktails",
        "Catering, group dining and private events",
    ],
    "hours": "Sun-Thu 11:00 AM - 9:00 PM; Fri-Sat 11:00 AM - 9:30 PM",
}

# Fill in by hand from Google Maps / Yelp (don't scrape those sites - it breaks their rules).
# Leave None if there's no time; the analysis still runs.
EXTERNAL_SIGNALS = {
    "Cafe Athena": {"google_rating": None, "google_reviews": None, "yelp_reviews": None},
    # "Competitor name": {"google_rating": None, "google_reviews": None, "yelp_reviews": None},
}

# The questions a real customer might type into ChatGPT / Claude. Grouped by "intent".
QUERY_BANK = {
    "cuisine": [
        "best Greek food in Pacific Beach",
        "best Mediterranean restaurant in San Diego",
        "where to get good gyros in Pacific Beach",
        "authentic Greek restaurant in San Diego",
    ],
    "dietary": [
        "Mediterranean restaurant with gluten-free options in San Diego",
        "vegan friendly restaurant in Pacific Beach",
        "vegetarian dinner spot in PB San Diego",
    ],
    "happy_hour": [
        "happy hour with good food near Garnet Ave",
        "best happy hour in Pacific Beach",
        "tapas or small plates happy hour in San Diego",
    ],
    "date_night": [
        "date night spot in PB with good cocktails",
        "romantic dinner in Pacific Beach",
        "unique cocktail bar with food in Pacific Beach",
    ],
    "events": [
        "where to host a rehearsal dinner in Pacific Beach",
        "restaurant with a private room for a party in San Diego",
        "Greek catering in San Diego",
        "restaurant for a large group dinner in Pacific Beach",
    ],
    "casual": [
        "lunch spot near Pacific Beach",
        "healthy lunch in PB San Diego",
        "family friendly restaurant in Pacific Beach",
    ],
    "visitor": [
        "I'm visiting San Diego and staying in Pacific Beach, where should I eat dinner?",
        "local favorite restaurants in Pacific Beach that have been around a long time",
        "where to eat after the beach in PB",
    ],
}

MODEL_MAIN = os.getenv("AISO_MODEL", "claude-sonnet-5-5")    # answers + writing
MODEL_FAST = os.getenv("AISO_FAST_MODEL", "claude-haiku-5-5")  # cheap helper jobs
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")       # check the current model name
WORKERS = 4                                                    # questions asked in parallel
OUT = Path("output")

MOCK = False          # set by --mock
AUTO_YES = False      # set by --yes

# =====================================================================
# HELPER: one function that talks to the AI (Claude, ChatGPT, or fake)
# =====================================================================

_clients = {}

def ask(prompt, system=None, platform="claude", model=None, max_tokens=900, kind="text"):
    """Send one prompt to an AI and return its text reply."""
    if MOCK:
        return mock_reply(prompt, kind)
    if platform == "claude":
        if "claude" not in _clients:
            import anthropic
            _clients["claude"] = anthropic.Anthropic(max_retries=4)
        kwargs = dict(model=model or MODEL_MAIN, max_tokens=max_tokens,
                      messages=[{"role": "user", "content": prompt}])
        if system:
            kwargs["system"] = system
        msg = _clients["claude"].messages.create(**kwargs)
        return "".join(b.text for b in msg.content if b.type == "text")
    if platform == "openai":
        if "openai" not in _clients:
            from openai import OpenAI
            _clients["openai"] = OpenAI(max_retries=4)
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        r = _clients["openai"].chat.completions.create(model=OPENAI_MODEL, messages=msgs)
        return r.choices[0].message.content
    raise ValueError(f"Unknown platform: {platform}")


def parse_json(text, default):
    """Pull the first JSON object/array out of an AI reply."""
    m = re.search(r"(\[.*\]|\{.*\})", text, re.S)
    if not m:
        return default
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return default


# =====================================================================
# STEP 1 - DISCOVER: ask the AI like customers do, and keep score
# =====================================================================

ANSWER_SYSTEM = ("You are a helpful AI assistant. Someone asks for a place to eat in New York City. "
                 "Recommend 3 to 5 specific, real places as a numbered list, best first, "
                 "with one short sentence each on why.")

SIM_SYSTEM = ("You are an AI search assistant. You answer ONLY from the web search results "
              "provided. Recommend 3 to 5 places as a numbered list, best first, one short "
              "sentence each on why. Prefer places whose results clearly match the question.")

SIM_TEMPLATE = "WEB SEARCH RESULTS:\n{context}\n\nUSER QUESTION: {query}"

EXTRACT_PROMPT = ("List every restaurant or food business recommended in the answer below, "
                  "in the order they appear. Reply with ONLY a JSON array of names.\n\nANSWER:\n{answer}")


def build_queries(n=None):
    qs = [{"id": i, "category": cat, "query": q}
          for i, (cat, q) in enumerate((c, q) for c, lst in QUERY_BANK.items() for q in lst)]
    if n:   # spread the sample across categories instead of taking the first n
        qs = qs[::max(1, len(qs) // n)][:n]
    return qs


def is_target(name):
    return any(a in name.lower() for a in TARGET["aliases"])


def extract_names(answer, platform):
    names = parse_json(ask(EXTRACT_PROMPT.format(answer=answer), platform="claude",
                           model=MODEL_FAST, max_tokens=300, kind="extract"), None)
    if not isinstance(names, list):   # fallback: read numbered lines like "1. Name - reason"
        names = [re.split(r"\s[-–—:]\s|\*\*", re.sub(r"^\s*\d+[.)]\s*\**", "", l))[0].strip()
                 for l in answer.splitlines() if re.match(r"^\s*\d+[.)]", l)]
    return [str(n).strip() for n in names if str(n).strip()]


def run_query_bank(queries, platform="claude", context=None):
    """Ask every question. context=None -> the AI answers from its own knowledge (real test).
    context=text -> the AI answers from 'web results' we give it (simulation for STEP 4)."""
    def one(q):
        if context is None:
            answer = ask(q["query"], system=ANSWER_SYSTEM, platform=platform, kind="answer")
        else:
            answer = ask(SIM_TEMPLATE.format(context=context, query=q["query"]),
                         system=SIM_SYSTEM, platform=platform, kind="answer")
        names = extract_names(answer, platform)
        rank = next((i + 1 for i, n in enumerate(names) if is_target(n)), None)
        mentioned = rank is not None or any(a in answer.lower() for a in TARGET["aliases"])
        with _print_lock:
            print(f"  [{'HIT ' if mentioned else 'miss'}] {q['query']}", flush=True)
        return {**q, "platform": platform, "answer": answer, "recommended": names,
                "mentioned": mentioned, "rank": rank}
    with ThreadPoolExecutor(WORKERS) as ex:
        return list(ex.map(one, queries))


def scorecard(results):
    """Turn raw answers into numbers: mention rate, rank, competitor share-of-voice."""
    total = len(results)
    hits = [r for r in results if r["mentioned"]]
    ranks = [r["rank"] for r in hits if r["rank"]]
    display, comp = {}, Counter()
    for r in results:
        for n in r["recommended"]:
            if is_target(n):
                continue
            key = re.sub(r"^the\s+|[^a-z0-9 ]", "", n.lower()).strip()
            display.setdefault(key, n)
            comp[key] += 1
    all_mentions = sum(len(r["recommended"]) for r in results) or 1
    target_mentions = sum(1 for r in results for n in r["recommended"] if is_target(n))
    by_cat = {}
    for r in results:
        c = by_cat.setdefault(r["category"], {"queries": 0, "mentioned": 0})
        c["queries"] += 1
        c["mentioned"] += r["mentioned"]
    return {
        "queries": total,
        "mentioned": len(hits),
        "mention_rate": round(len(hits) / total, 3) if total else 0,
        "avg_rank": round(sum(ranks) / len(ranks), 2) if ranks else None,
        "target_share_of_voice": round(target_mentions / all_mentions, 3),
        "top_competitors": [{"name": display[k], "appearances": c,
                             "appear_rate": round(c / total, 3),
                             "share_of_voice": round(c / all_mentions, 3)}
                            for k, c in comp.most_common(8)],
        "by_category": by_cat,
    }


def log_history(label, platform, card):
    """Append one row to history.csv so we can track change over time."""
    f = OUT / "history.csv"
    new = not f.exists()
    with f.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["timestamp", "label", "platform", "queries", "mentioned", "mention_rate", "avg_rank"])
        w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), label, platform,
                    card["queries"], card["mentioned"], card["mention_rate"], card["avg_rank"]])


def step_discover(args):
    print("\nSTEP 1 - DISCOVER: asking AI the way customers do")
    queries = build_queries(args.n)
    for platform in args.platforms:
        print(f"\nPlatform: {platform}  ({len(queries)} questions)")
        results = run_query_bank(queries, platform)
        card = scorecard(results)
        save(f"discovery_{platform}.json", {"run_at": now(), "results": results, "scorecard": card})
        log_history("live AI check", platform, card)
        print(f"\n  -> {TARGET['name']} mentioned in {card['mentioned']}/{card['queries']} answers "
              f"({card['mention_rate']:.0%}). Avg rank when mentioned: {card['avg_rank']}")
        for c in card["top_competitors"][:3]:
            print(f"     {c['name']}: {c['appearances']}/{card['queries']}")


# =====================================================================
# STEP 2 - ANALYZE: why are competitors winning?
# =====================================================================

def fetch_site(url):
    """Download the restaurant's website. Returns (html, text) or (None, None)."""
    try:
        import requests
        from bs4 import BeautifulSoup
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0 (AISO hackathon project)"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "noscript"]):
            if t.get("type") != "application/ld+json":
                t.decompose()
        return r.text, " ".join(soup.get_text(" ").split())
    except Exception as e:
        print(f"  (could not load website: {e.__class__.__name__}) - continuing without it")
        return None, None


def website_audit():
    """Check the website for the things AI assistants rely on."""
    raw, text = fetch_site(TARGET["website"])
    if raw is None:
        return {"fetched": False, "checks": {}, "word_count": 0, "text_sample": ""}
    low = text.lower()
    checks = {
        "Structured data (schema.org JSON-LD for Restaurant)":
            bool(re.search(r'application/ld\+json[^<]*>[^<]*"Restaurant"', raw, re.S)),
        "FAQ section answering common questions": "faq" in low or "frequently asked" in low,
        "Mentions Pacific Beach": "pacific beach" in low,
        "Mentions happy hour": "happy hour" in low,
        "Mentions private events / rehearsal dinners": any(w in low for w in ["private event", "rehearsal", "banquet"]),
        "Opening hours written as text": bool(re.search(r"\b\d{1,2}(:\d\d)?\s?(am|pm)\b", low)),
        "Menu readable as text (not only a PDF/image)":
            sum(w in low for w in ["gyro", "souvlaki", "moussaka", "spanakopita", "hummus", "baklava", "salad"]) >= 3,
        "Dietary info (vegetarian / vegan / gluten-free)":
            any(w in low for w in ["vegetarian", "vegan", "gluten"]),
        "Enough text for AI to read (300+ words)": len(text.split()) >= 300,
        "Page has a meta description": 'name="description"' in raw.lower(),
    }
    return {"fetched": True, "checks": checks, "word_count": len(text.split()), "text_sample": text[:1500]}


def step_analyze(args):
    print("\nSTEP 2 - ANALYZE: finding out why competitors win")
    disc = load(f"discovery_{args.platforms[0]}.json")
    card = disc["scorecard"]
    print("  Checking the restaurant's website...")
    audit = website_audit()
    for k, v in audit["checks"].items():
        print(f"   [{'OK ' if v else 'GAP'}] {k}")

    missed = [r["query"] for r in disc["results"] if not r["mentioned"]][:10]
    prompt = f"""You are an AI-search-optimization analyst helping a restaurant owner.

RESTAURANT: {TARGET['name']}, {TARGET['street']}, {TARGET['neighborhood']}, NYC
KNOWN FACTS: {json.dumps(TARGET['known_facts'])}

AI VISIBILITY RESULTS ({card['queries']} customer-style questions asked to an AI assistant):
- Mentioned in {card['mentioned']}/{card['queries']} answers ({card['mention_rate']:.0%}); avg rank when mentioned: {card['avg_rank']}
- Results by question type: {json.dumps(card['by_category'])}
- Competitors that appeared most: {json.dumps(card['top_competitors'][:5])}
- Example questions where it was NOT recommended: {json.dumps(missed)}

WEBSITE AUDIT (fetched: {audit['fetched']}): {json.dumps(audit['checks'])}
REVIEW COUNTS ENTERED BY THE TEAM (null = unknown): {json.dumps(EXTERNAL_SIGNALS)}

Task: explain WHY competitors are recommended more, and list the most important gaps.
Use the numbers above as evidence. For competitor strengths, rely only on widely known public
information and mark anything uncertain with "(likely)". Do not invent review counts.

Reply with ONLY JSON:
{{"summary": "2-3 sentences for the owner",
  "competitor_reasons": [{{"competitor": "...", "why_ai_prefers_them": "..."}}],
  "gaps": [{{"priority": 1, "gap": "...", "evidence": "...", "fix": "...", "effort": "low|medium|high"}}]}}
Give 5-7 gaps, most impactful first."""
    diagnosis = parse_json(ask(prompt, max_tokens=2000, kind="gaps"), {"summary": "", "gaps": [], "competitor_reasons": []})
    save("analysis.json", {"run_at": now(), "scorecard": card, "website_audit": audit, "diagnosis": diagnosis})
    print(f"\n  Summary: {diagnosis.get('summary', '')}")
    for g in diagnosis.get("gaps", []):
        print(f"   {g.get('priority')}. {g.get('gap')}  ->  {g.get('fix')}")


# =====================================================================
# STEP 3 - FIX: write the content that closes the gaps
# =====================================================================

FACT_RULES = f"""RULES:
- Use ONLY these facts about the restaurant: {json.dumps(TARGET['known_facts'])}
- Address: {TARGET['street']}, {TARGET['city']}, {TARGET['state']} {TARGET['zip']}.
- Hours: {TARGET['hours']}.
- If you need any other fact (prices, specific dishes, dietary options), write [CONFIRM: what is needed].
- Write in plain, friendly language. Naturally include phrases people ask AI, such as
  "Pacific Beach", "PB", "San Diego", "Greek", "Mediterranean", "happy hour", "gluten-free",
  "date night", "rehearsal dinner", "private events"."""


def restaurant_schema(faq):
    """Build schema.org JSON-LD. Built by code (not AI) so the facts can't be made up."""
    restaurant = {
        "@context": "https://schema.org",
        "@type": "Restaurant",
        "name": TARGET["name"],
        "url": TARGET["website"],
        "priceRange": TARGET["price_range"],
        "servesCuisine": TARGET["cuisine"],
        "address": {"@type": "PostalAddress", "streetAddress": TARGET["street"],
                    "addressLocality": TARGET["city"], "addressRegion": TARGET["state"],
                    "postalCode": TARGET["zip"], "addressCountry": "US"},
        "areaServed": ["Pacific Beach", "San Diego"],
        "foundingDate": "1990",
        "hasMenu": TARGET["website"] + "menu",   # CONFIRM the real menu URL
        "openingHours": ["Su-Th 11:00-21:00", "Fr-Sa 11:00-21:30"],
        "amenityFeature": [{"@type": "LocationFeatureSpecification", "name": n, "value": True}
                           for n in ["Full bar", "Happy hour 3-6 PM daily", "Private events",
                                     "Catering", "Vegan options", "Gluten-free options"]],
    }
    if TARGET.get("phone"):
        restaurant["telephone"] = TARGET["phone"]
    faq_page = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": f["q"],
                        "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq],
    }
    return [restaurant, faq_page]


def approve(what, preview):
    """Human-in-the-loop: nothing goes out without a yes."""
    print("\n" + "=" * 60 + f"\nAPPROVAL NEEDED: {what}\n" + "-" * 60)
    print(preview[:1200] + ("\n..." if len(preview) > 1200 else ""))
    print("=" * 60)
    if AUTO_YES:
        print("  (auto-approved with --yes)")
        return True
    if not sys.stdin.isatty():
        print("  (no one to ask - NOT approved)")
        return False
    return input("Approve? [y/N] ").strip().lower() in ("y", "yes")


def step_fix(args):
    print("\nSTEP 3 - FIX: writing the content")
    analysis = load("analysis.json")
    gaps = json.dumps(analysis["diagnosis"].get("gaps", []))
    fixes = OUT / "fixes"
    fixes.mkdir(parents=True, exist_ok=True)

    print("  Writing FAQ...")
    faq = parse_json(ask(f"""{FACT_RULES}
Write 8 FAQ entries for {TARGET['name']}'s website. Each question should match how a real person
would ask an AI assistant (e.g. "Does Cafe Athena have gluten-free options?" or
"Can I host a rehearsal dinner at Cafe Athena?").
Gaps to address: {gaps}
Reply with ONLY a JSON array: [{{"q": "...", "a": "2-3 sentence answer"}}]""", max_tokens=2000, kind="faq"), [])
    (fixes / "faq.md").write_text("# Frequently Asked Questions\n\n" +
                                  "\n\n".join(f"**{f['q']}**\n\n{f['a']}" for f in faq))

    print("  Building schema markup...")
    schema = restaurant_schema(faq)
    (fixes / "schema.json").write_text(json.dumps(schema, indent=2))
    (fixes / "schema_paste_into_website.html").write_text(
        "<!-- Paste inside the <head> of the website -->\n" +
        "\n".join(f'<script type="application/ld+json">\n{json.dumps(s, indent=2)}\n</script>' for s in schema))

    jobs = {
        "about.md": "Write a new 'About Us' section (150-200 words) for the website.",
        "menu_descriptions.md": "Write short, appetizing descriptions for the main menu sections "
                                "(small plates/tapas, salads, gyros and souvlaki, Greek entrees, vegan and gluten-free picks, "
                                "signature Greek-mythology cocktails, desserts). "
                                "Mark any dish names or dietary tags you are unsure of with [CONFIRM].",
        "landing_page.md": "Write a helpful web page titled 'Best Greek and Mediterranean Food in Pacific Beach' "
                           "(400-500 words) that a local or visitor would find useful and that an AI assistant "
                           "could quote. Include a short 'Good for' list (happy hour, date night, rehearsal "
                           "dinners and private events, gluten-free and vegan diners).",
        "google_business_profile.md": "Write a Google Business Profile description (max 750 characters) "
                                      "and 3 short Google posts.",
        "review_campaign.md": "Write a simple 60-day plan to get more Google reviews: table-tent card text, "
                              "receipt line, and a reply template for reviews. Keep it honest (no fake reviews, "
                              "no paying for reviews).",
        "outreach_email.md": "Write a short, friendly email from the restaurant's owner to a San Diego food blogger "
                             "or local Pacific Beach publication, inviting them to try the happy hour and feature "
                             "the restaurant. "
                             "Include a subject line. Use [NAME] for the recipient.",
    }
    outputs = {}
    for fname, task in jobs.items():
        print(f"  Writing {fname}...")
        outputs[fname] = ask(f"{FACT_RULES}\n\nGaps found in analysis: {gaps}\n\nTASK: {task}",
                             max_tokens=1500, kind="text")
        (fixes / fname).write_text(outputs[fname])

    # ---- the "action" layer, with human approval ----
    actions = []
    if approve("Queue the outreach email for sending", outputs["outreach_email.md"]):
        (OUT / "outbox").mkdir(exist_ok=True)
        (OUT / "outbox" / "approved_outreach_email.md").write_text(
            f"<!-- approved {now()} - connect Gmail/SMTP to actually send -->\n" + outputs["outreach_email.md"])
        actions.append({"action": "Outreach email approved and queued", "at": now()})
    if approve("Package website updates (About, FAQ, schema) for the owner's website",
               "Files: about.md, faq.md, menu_descriptions.md, landing_page.md, schema_paste_into_website.html"):
        actions.append({"action": "Website update package approved", "at": now()})
    save("actions.json", actions)
    print(f"\n  -> {len(jobs) + 3} files written to output/fixes/. Approved actions: {len(actions)}")


# =====================================================================
# STEP 4 - MEASURE: did the fixes help? (before vs after)
# =====================================================================
# Real AI models take weeks to notice website changes, so for the demo we SIMULATE
# AI search: the AI gets the same "web results" twice - once with the restaurant's OLD
# content, once with the NEW content. Competitors stay identical, so any change in
# mentions comes from our fixes. In real life: re-run `discover` weekly.

def step_measure(args):
    print("\nSTEP 4 - MEASURE: before vs after (simulated AI search)")
    disc = load(f"discovery_{args.platforms[0]}.json")
    fixes = OUT / "fixes"
    competitors = [c["name"] for c in disc["scorecard"]["top_competitors"][:5]]

    print("  Building competitor search results...")
    comp_snips = {c: ask(f"In 2-3 sentences, write a neutral directory-style description of the NYC "
                         f"restaurant '{c}' in or near Pacific Beach, San Diego: cuisine, what it is known for, "
                         f"price level. If you are not sure, keep it short and general.",
                         model=MODEL_FAST, max_tokens=200, kind="describe").strip()
                  for c in competitors}

    _, site_text = fetch_site(TARGET["website"])
    before_snip = (site_text[:900] if site_text else
                   f"{TARGET['name']}. {TARGET['street']}, {TARGET['city']}, {TARGET['state']} {TARGET['zip']}. Greek restaurant.")
    after_snip = before_snip + "\n\n" + "\n\n".join(
        f"Source: {TARGET['website']} ({label})\n{(fixes / f).read_text()[:900]}"
        for f, label in [("about.md", "About page"), ("faq.md", "FAQ page"),
                         ("landing_page.md", "Pacific Beach Greek food guide"),
                         ("menu_descriptions.md", "Menu")])

    def context(target_snip):
        blocks = [(c, s) for c, s in comp_snips.items()] + [(TARGET["name"], target_snip)]
        random.Random(42).shuffle(blocks)          # same order both times = fair test
        return "\n\n".join(f"[Result {i+1}] {name}\n{s}" for i, (name, s) in enumerate(blocks))

    queries = build_queries(args.n)
    print("\n  BEFORE (old content):")
    before = run_query_bank(queries, args.platforms[0], context=context(before_snip))
    print("\n  AFTER (new content):")
    after = run_query_bank(queries, args.platforms[0], context=context(after_snip))
    b, a = scorecard(before), scorecard(after)
    save("measure.json", {"run_at": now(), "before": b, "after": a,
                          "before_results": before, "after_results": after})
    log_history("simulated BEFORE", args.platforms[0], b)
    log_history("simulated AFTER", args.platforms[0], a)
    print(f"\n  -> Mentioned BEFORE: {b['mentioned']}/{b['queries']} ({b['mention_rate']:.0%})"
          f"   AFTER: {a['mentioned']}/{a['queries']} ({a['mention_rate']:.0%})")


# =====================================================================
# STEP 5 - REPORT: one page to show the judges
# =====================================================================

def step_report(args):
    print("\nSTEP 5 - REPORT")
    e = html.escape
    disc = load(f"discovery_{args.platforms[0]}.json")
    card = disc["scorecard"]
    analysis = load("analysis.json", {})
    measure = load("measure.json", {})
    actions = load("actions.json", [])
    diag = analysis.get("diagnosis", {})

    def bar(label, value, total, hl=False):
        pct = 0 if not total else value / total * 100
        return (f'<div class="row"><span class="lbl">{e(label)}</span><div class="track">'
                f'<div class="fill{" hl" if hl else ""}" style="width:{pct:.0f}%"></div></div>'
                f'<span class="num">{value}/{total}</span></div>')

    sov = bar(TARGET["name"], card["mentioned"], card["queries"], True) + "".join(
        bar(c["name"], c["appearances"], card["queries"]) for c in card["top_competitors"][:6])
    cats = "".join(bar(k.replace("_", " "), v["mentioned"], v["queries"], True)
                   for k, v in card["by_category"].items())
    checks = "".join(f'<li class="{"ok" if v else "gap"}">{"✓" if v else "✗"} {e(k)}</li>'
                     for k, v in analysis.get("website_audit", {}).get("checks", {}).items()) \
        or "<li>Website could not be loaded during the run.</li>"
    reasons = "".join(f"<li><b>{e(r.get('competitor',''))}</b>: {e(r.get('why_ai_prefers_them',''))}</li>"
                      for r in diag.get("competitor_reasons", []))
    gaps = "".join(f"<tr><td>{e(str(g.get('priority','')))}</td><td>{e(g.get('gap',''))}</td>"
                   f"<td>{e(g.get('evidence',''))}</td><td>{e(g.get('fix',''))}</td>"
                   f"<td>{e(g.get('effort',''))}</td></tr>" for g in diag.get("gaps", []))
    files = "".join(f'<li><a href="fixes/{f.name}">{f.name}</a></li>'
                    for f in sorted((OUT / "fixes").glob("*")) if f.is_file())
    acts = "".join(f"<li>✓ {e(x['action'])} <small>({e(x['at'])})</small></li>" for x in actions) \
        or "<li>No actions approved yet.</li>"
    ba = ""
    if measure:
        b, a = measure["before"], measure["after"]
        ba = (bar("Before fixes", b["mentioned"], b["queries"]) +
              bar("After fixes", a["mentioned"], a["queries"], True) +
              f'<p class="note">Simulated AI search: same questions, same competitors - only '
              f'{e(TARGET["name"])}\'s content changed. Avg rank {b["avg_rank"]} → {a["avg_rank"]}.</p>')
    hist = ""
    if (OUT / "history.csv").exists():
        rows = list(csv.reader((OUT / "history.csv").open()))
        hist = "<table>" + "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rows) + "</table>"

    page = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Visibility Report</title><style>
body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:980px;margin:0 auto;padding:24px 16px;color:#1d1d1f;background:#fafaf7}}
h1{{margin:0;font-size:28px}} h2{{margin-top:36px;font-size:19px;border-bottom:2px solid #1d1d1f;padding-bottom:6px}}
.sub{{color:#666;margin-top:4px}} .kpis{{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}}
.kpi{{flex:1;min-width:150px;background:#fff;border:1px solid #ddd;border-radius:10px;padding:14px}}
.kpi b{{font-size:28px;display:block}} .row{{display:flex;align-items:center;gap:10px;margin:6px 0}}
.lbl{{width:230px;font-size:14px}} .track{{flex:1;background:#eee;border-radius:6px;height:16px}}
.fill{{background:#9a9a9a;height:16px;border-radius:6px}} .fill.hl{{background:#c8102e}}
.num{{width:56px;text-align:right;font-size:13px;color:#444}} table{{border-collapse:collapse;width:100%;font-size:13px;background:#fff}}
td,th{{border:1px solid #ddd;padding:7px;vertical-align:top;text-align:left}} li{{margin:5px 0}}
.ok{{color:#1a7f37}} .gap{{color:#c8102e}} .note{{font-size:13px;color:#555}}
@media(max-width:600px){{.lbl{{width:120px}}}}
</style></head><body>
<h1>AI Visibility Report: {e(TARGET['name'])}</h1>
<div class="sub">{e(TARGET['street'])}, {e(TARGET['neighborhood'])} · generated {e(now())}{' · MOCK DATA' if MOCK else ''}</div>
<div class="kpis">
 <div class="kpi"><b>{card['mentioned']}/{card['queries']}</b>AI answers mention us</div>
 <div class="kpi"><b>{card['avg_rank'] or '–'}</b>Avg position when mentioned</div>
 <div class="kpi"><b>{card['target_share_of_voice']:.0%}</b>Share of voice</div>
 <div class="kpi"><b>{e(card['top_competitors'][0]['name']) if card['top_competitors'] else '–'}</b>Top competitor</div>
</div>
<h2>1 · Where we rank (vs competitors)</h2>{sov}
<h2>By type of question</h2>{cats}
<h2>2 · Why competitors win</h2><p>{e(diag.get('summary',''))}</p><ul>{reasons}</ul>
<h3>Website check</h3><ul>{checks}</ul>
<h3>Prioritized gaps</h3><table><tr><th>#</th><th>Gap</th><th>Evidence</th><th>Fix</th><th>Effort</th></tr>{gaps}</table>
<h2>3 · What the agent created</h2><ul>{files}</ul><h3>Actions (human-approved)</h3><ul>{acts}</ul>
<h2>4 · Did it work?</h2>{ba or '<p>Run the measure step.</p>'}
<h3>History (re-run weekly to track)</h3>{hist}
</body></html>"""
    (OUT / "report.html").write_text(page)
    print("  -> output/report.html")


# =====================================================================
# Small utilities + fake AI for --mock practice runs
# =====================================================================

def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

def save(name, data):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2))

def load(name, default=None):
    f = OUT / name
    if not f.exists():
        if default is not None:
            return default
        sys.exit(f"Missing output/{name} - run the earlier step first.")
    return json.loads(f.read_text())


def mock_reply(prompt, kind):
    rnd = random.Random(hashlib.md5(prompt.encode()).hexdigest())
    pool = ["Mock Competitor A", "Mock Competitor B", "Mock Competitor C", "Mock Competitor D",
            "Mock Competitor E", "Mock Competitor F", "Mock Competitor G", "Mock Competitor H"]
    if kind == "answer":
        if "(FAQ page)" in prompt:
            p = 0.6           # after fixes
        elif "WEB SEARCH RESULTS" in prompt:
            p = 0.2           # before fixes
        else:
            p = 0.12          # live check
        picks = rnd.sample(pool, 4)
        if rnd.random() < p:
            picks.insert(rnd.randint(0, 2), TARGET["name"])
        return "\n".join(f"{i+1}. {n} - a solid pick nearby." for i, n in enumerate(picks))
    if kind == "extract":
        ans = prompt.split("ANSWER:\n", 1)[-1]
        return json.dumps([re.sub(r"^\d+\.\s*", "", l).split(" - ")[0] for l in ans.splitlines() if l.strip()])
    if kind == "describe":
        return "A popular restaurant in Pacific Beach, San Diego. (mock)"
    if kind == "gaps":
        return json.dumps({
            "summary": "MOCK: Cafe Athena rarely appears in AI answers. Competitors have clearer online "
                       "information about happy hour, dietary options and events, which AI assistants pick up.",
            "competitor_reasons": [{"competitor": "Mock Competitor A",
                                    "why_ai_prefers_them": "(likely) More press coverage and reviews."}],
            "gaps": [{"priority": 1, "gap": "No structured data", "evidence": "Website check failed",
                      "fix": "Add Restaurant + FAQPage schema", "effort": "low"},
                     {"priority": 2, "gap": "No FAQ for happy hour / events questions", "evidence": "Missed happy-hour and events queries",
                      "fix": "Publish FAQ page", "effort": "low"}]})
    if kind == "faq":
        return json.dumps([{"q": "Does Cafe Athena have gluten-free options?",
                            "a": "Yes - Cafe Athena in Pacific Beach offers vegan, vegetarian and gluten-free options."},
                           {"q": "When is happy hour at Cafe Athena?",
                            "a": "Every day from 3 to 6 PM, with tapas-style small plates, at 1846 Garnet Ave."}])
    return "[MOCK OUTPUT - run without --mock to generate real content]\n\n" + prompt.split("TASK:")[-1][:300]


# =====================================================================
# Run it
# =====================================================================

def main():
    global MOCK, AUTO_YES
    p = argparse.ArgumentParser(description="AI Search Optimization agent")
    p.add_argument("step", choices=["discover", "analyze", "fix", "measure", "report", "all"])
    p.add_argument("--mock", action="store_true", help="fake AI answers, no API key needed")
    p.add_argument("--n", type=int, default=None, help="number of questions to use")
    p.add_argument("--platforms", default="claude", help="claude and/or openai, comma-separated")
    p.add_argument("--yes", action="store_true", help="auto-approve actions (testing only)")
    args = p.parse_args()
    MOCK, AUTO_YES = args.mock, args.yes
    args.platforms = [x.strip() for x in args.platforms.split(",") if x.strip()]
    if not MOCK and not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first (or add --mock to practice).")
    OUT.mkdir(exist_ok=True)
    steps = {"discover": step_discover, "analyze": step_analyze, "fix": step_fix,
             "measure": step_measure, "report": step_report}
    for name in (steps if args.step == "all" else [args.step]):
        steps[name](args)
    print("\nDone. Open output/report.html")


if __name__ == "__main__":
    main()

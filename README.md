# Café Athena: AI Search Optimization (AISO)
**NYU SPS × Pulse Foundry Hackathon · October 23, 2026**
Team: Baishnavi, Srishti, Haarika, Janhvi

> Café Athena already has everything San Diego diners ask AI for. The AI just doesn't know it yet. This project measures that, explains why, fixes it, and checks again.

**Target:** Café Athena, a Greek and Mediterranean restaurant and bar at 1846 Garnet Ave, Pacific Beach, San Diego, open since 1990. Daily happy hour 3–6 PM, Greek-mythology cocktails, vegan, vegetarian and gluten-free options, catering and private events.

---

## The loop

```
1. DISCOVERY  →  2. RESULTS  →  3. PROBLEM  →  4. FIX (new website)  →  5. IMPROVED RESULTS
      ↑                                                                              │
      └──────────────────────── re-run every week ───────────────────────────────────┘
```

| Step | Where |
|---|---|
| 1. Discovery: 15 customer questions | [`data/queries.csv`](data/queries.csv) |
| 2. Results: 240 AI answers | [`data/before_scores.csv`](data/before_scores.csv), [`data/missed_answers.csv`](data/missed_answers.csv), [`results/`](results/) |
| 3. Problem: why competitors win | [this README](#3-problem-why-competitors-win), [`results/summary.md`](results/summary.md) |
| 4. Fix: new website + content | [`website/index.html`](website/index.html), [`fixes/`](fixes/) |
| 5. Improved results | [`measure/simulate_after.py`](measure/simulate_after.py), [`data/after_scores.csv`](data/after_scores.csv) |
| Automated agent (all steps) | [`agent/aiso_agent.py`](agent/aiso_agent.py) |

---

## 1. Discovery

We wrote **15 questions** a real customer in San Diego might ask an AI assistant, across 6 intents: Greek food, dietary needs, happy hour and drinks, date night, events and groups, and visitors. See [`data/queries.csv`](data/queries.csv).

Each of the 4 teammates asked all 15 questions on 4 AI tools (ChatGPT, Claude, Gemini, Perplexity; one teammate used Grok in place of Perplexity) and recorded whether Café Athena was mentioned and, when it wasn't, who was recommended instead.

**4 testers × 4 AI tools × 15 questions = 240 AI answers.**

## 2. Results (before)

**Café Athena was mentioned in 113 of 240 answers (47%).**

| AI tool | Mentioned | Rate |
|---|---|---|
| Perplexity | 37 / 45 | **82%** |
| Grok | 9 / 15 | 60% |
| Claude | 27 / 60 | 45% |
| ChatGPT | 23 / 60 | 38% |
| Gemini | 17 / 60 | **28%** |

![Before by platform](results/1_before_by_platform.png)

**Finding 1: Visibility depends on which AI you ask.** Perplexity searches the web live and finds Café Athena. Gemini relies on Google's own data and rarely does.

**Finding 2: The same AI gives different people different answers.** Gemini mentioned Café Athena 10 of 15 times for one teammate and 0 of 15 for another. A restaurant owner can't check once and know where they stand, so the agent re-checks automatically.

**Finding 3: It wins on identity and loses on occasions.** "Best Greek restaurant in Pacific Beach" was missed only once. Questions about what it *offers* were missed most:

| # | Question | Times missed |
|---|---|---|
| 12 | Private room for a birthday party of 25 | **10** |
| 8 | Small plates / tapas for happy hour | 7 |
| 9 | Unique or creative cocktails | 7 |
| 5 | Vegan-friendly sit-down restaurant | 6 |
| 11 | Host a rehearsal dinner in Pacific Beach | 6 |

![Missed questions](results/2_missed_questions.png)

## 3. Problem: why competitors win

Café Athena offers every one of those things. Competitors win because the information about them online is **specific and quotable**:

| Competitor | What AI said about them |
|---|---|
| Athens Market Taverna | "Upstairs private dining room for **20–80 guests** with a private bar" |
| Pacific Beach AleHouse | "Brewers Table **seats 25**", "private dining for **40–100**" |
| Costa Brava | "**Half-price tapas, $2 sangria**, Sun–Thu **4–6 PM**" |
| Mezé Greek Fusion | "Meze happy hour with **flaming saganaki**, dips, kebabs" |

What AI said about Café Athena: *"I don't have confirmation that it has an enclosed private room, only that it does banquets"* and *"vegetarian-friendly with some vegan options."*

Supporting evidence:
- **Few reviews:** 101 on TripAdvisor in 35 years.
- **Old press:** the main write-up is a 2014 student newspaper review.
- **Missing from lists:** not in a recent "Top 5 Greek Restaurants in San Diego" article.
- **Main rival: Mezé Greek Fusion**, another Greek restaurant that beats Café Athena on happy hour, private rooms and catering.

![Competitors](results/3_competitors.png)

## 4. Fix: the new website and content

| Problem | Fix | File |
|---|---|---|
| AI doesn't know about events, happy hour, cocktails, vegan, catering | One clear section per strength, with specific details | [`website/index.html`](website/index.html) |
| AI needs answers it can quote | FAQ worded the way people ask AI | [`fixes/faq.md`](fixes/faq.md) |
| Computers need facts in a standard format | Schema.org code (Restaurant + FAQPage), built into the website | [`fixes/schema.json`](fixes/schema.json) |
| Gemini is weakest (Google data) | Google Business Profile, attributes, posts, honest review card | [`fixes/google_business_profile.md`](fixes/google_business_profile.md) |
| Not on "best of" lists; old press | Outreach emails, sent only after owner approval | [`fixes/outreach_emails.md`](fixes/outreach_emails.md) |

**The website** ([`website/index.html`](website/index.html)) is a concept redesign by our team, not the official site. Facts come from the hackathon brief. Prices, room sizes, cocktail names and contact details are **examples (dotted underline) for the owner to replace**.

## 5. Improved results

Real AI tools take weeks to notice a new website, so we measure two ways:

**A. Simulated AI search (today).** [`measure/simulate_after.py`](measure/simulate_after.py) gives an AI the same competitor search results twice: once with Café Athena's old, vague info, once with the new website. Only Café Athena's content changes, so any difference is caused by the fixes.

```bash
pip install anthropic beautifulsoup4 matplotlib
export ANTHROPIC_API_KEY="sk-ant-..."
python measure/simulate_after.py --rounds 3
```

**B. Re-survey (weekly, after the site goes live).** Ask the same 15 questions on the same AI tools, fill in [`data/after_scores.csv`](data/after_scores.csv) (same format as the before file), then:

```bash
python analysis/analyze.py
```

This updates [`results/summary.md`](results/summary.md) and creates `results/4_before_vs_after.png`.

| | Before | After |
|---|---|---|
| Overall mention rate | 47% | _[fill in]_ |
| Private room for 25 (Q12) | missed 10 times | _[fill in]_ |

## Automated agent

[`agent/aiso_agent.py`](agent/aiso_agent.py) runs the whole loop automatically through the AI APIs: discover → analyze (including a website audit) → write fixes → human approval → measure → HTML report.

```bash
python agent/aiso_agent.py all --mock --yes   # practice run, no API key
python agent/aiso_agent.py all                # real run
```

## Project structure

```
data/        queries, before/after scores, every missed answer
analysis/    analyze.py: turns the data into the summary and charts
results/     summary.md and charts
website/     new Café Athena website (concept) with all fixes built in
fixes/       FAQ, schema, Google profile, outreach emails
measure/     simulate_after.py: before/after test
agent/       aiso_agent.py: the full automated agent
```

## Limits
- Survey answers vary by user, location (we were in New York asking about San Diego), login and chat history. That variation is itself a finding.
- Some teammates recorded misses without naming the competitor, so competitor counts are a lower bound.
- The simulated test shows the content works when AI reads it. Real-world change needs the site published and weekly re-checks.

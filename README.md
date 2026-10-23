# AISO Growth Agent — Café Athena

An agent that answers five questions for a restaurant owner — *Where do I rank in AI search? Why are competitors beating me? What should I change? Can you make the changes? Did it work?* — as a loop: **Discovery → Analysis → Action → Measurement**.

Target: Café Athena, 1846 Garnet Ave, Pacific Beach, San Diego.

## Live dashboard

- **Live version (runs Claude probes, the before/after test and the shared team test log):** https://claude.ai/artifact/3q2jZGbb7pxokpW1Xoi5XS
- **Copy in this repo:** [`dashboard/index.html`](dashboard/index.html). Open it in a browser, or turn on GitHub Pages (Settings → Pages → Deploy from branch → `main`, folder `/ (root)`) and visit `/dashboard/`. The copy shows everything; the live features need the Claude version.
- **Project website:** https://claude.ai/artifact/Hr51ddB8C758uXawppUB8p · **Pitch deck:** https://claude.ai/artifact/HNoHHi1SH7sRCbnA6vBtvK

## Quick start (5 minutes)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...  OPENAI_API_KEY=...  GEMINI_API_KEY=...  PERPLEXITY_API_KEY=...

# 0. smoke test without keys (numbers are fake and labeled SIMULATED)
python -m aiso.cli loop --simulate --out out_sim

# 1. baseline: the team's 15 questions + 3 branded + 2 control, x 4 platforms x 2 modes x 2 samples (~280 answers)
#    add --bank full --rebuild-bank for the 59-question bank
python -m aiso.cli discover --label baseline                  # --samples 1 for a fast demo run
python -m aiso.cli analyze                                    # scorecard, site audit, ranked gaps
python -m aiso.cli act                                        # generate content, queue actions
python -m aiso.cli approve                                    # human approves each action
python -m aiso.cli export                                     # out/report.md (visibility report) + out/dashboard.json for the dashboard

python -m aiso.cli kit                                        # out/install_kit/: every fix as a ready-to-install file + INSTALL.md

# 2. later: same bank, compare to baseline
python -m aiso.cli measure --label week-1
```

Missing keys are skipped, so it runs with whatever platforms you have. If a provider rejects a model or tool name, change it in `config/cafe_athena.json` → `platforms`.

## How each stage works

| Stage | What it does | Files |
|---|---|---|
| **Discovery** | Default bank = the team's 15 core San Diego questions across 7 intents (full option: fixed-seed 59-question bank across 9 intents) (best-of, dietary, happy hour, date night, groups/rehearsal, catering, quick lunch, visitor, comparison) + branded and control queries, optional LLM long-tail expansion. Each query runs on Claude, GPT, Gemini, Perplexity in **grounded** (live web search, what consumers see) and **parametric** (model memory) modes, N samples each. An LLM extractor turns each answer into an ordered list of places. | `aiso/discovery/` |
| **Analysis** | Scorecard: mention rate (Wilson 95% CI), top-3 rate, avg rank, visibility index (mean 1/rank), share of voice, by platform and intent. Cited-domain analysis shows which sources AI pulls from. Site audit: JSON-LD types/fields, FAQ, menu-as-text, dietary labels, happy-hour consistency, robots.txt for AI bots, llms.txt. Diagnosis ranks gaps by impact × confidence ÷ effort and quotes the AI's own reasons for recommending each competitor. | `aiso/analysis/`, `research/findings.json` |
| **Action** | Fact-locked generators (no invented facts; unknowns become `[OWNER TO CONFIRM]`): Restaurant/Menu/FAQPage/Review JSON-LD, menu description rewrites, FAQ, About copy, 5 occasion landing pages, llms.txt, robots.txt additions, listing-update sheet, 5 press outreach emails. Actions queue with preview → human approves → executor runs → logged → `rollback` for reversible ones. | `aiso/action/` |
| **Measurement** | Every answer stored in SQLite. `measure` re-runs the identical bank; `compare` reports deltas with a two-proportion z-test and checks control queries (sushi/tacos) didn't move — so model drift isn't mistaken for impact. Weekly GitHub Action. | `aiso/measure/`, `.github/workflows/` |

## Team baseline (Oct 23, consumer apps)

Four testers ran the 15 questions in their own ChatGPT, Claude, Gemini and Perplexity (one used Grok): Café Athena was named in **113 of 240 answers (47%)**: Perplexity 82%, Grok 60%, Claude 45%, ChatGPT 38%, Gemini 28%. Raw counts: `research/team_baseline_2026-10-23.csv`. Re-run the same 15 questions with the same testers to measure change.

## Before you analyze: fill in review counts (5 minutes)

Open `research/competitor_signals.json` and type in Google review counts (and Yelp, if you like) for Café Athena and the top competitors, from their public Google Maps / Yelp pages. The agent then writes the verdict the brief's Greenwich Kitchen example asks for: *"Competitor A appears in 15/20 answers and has 340 Google reviews (you have 40)…"* followed by numbered actions. Leave it blank and the verdict still runs, without the review comparison.

## Executors (all behind approval)

- `local_file` — ready-to-paste files (default)
- `wp_draft` — set `WP_URL`, `WP_USER`, `WP_APP_PASSWORD` (WordPress application password). Creates **draft** pages, invisible to the public until the owner publishes; `rollback` deletes them. cafeathena.com runs WordPress (Divi).
- `email_draft` — `.eml` drafts the owner sends from their own mailbox; nothing is sent automatically
- `github_pr` / `webhook` — for sites in git, or any CMS via Zapier/Make/n8n

## Honest limits

- Consumer apps (ChatGPT, Gemini app, Perplexity app) add personalization and location the APIs don't fully reproduce; we pass San Diego as user location and sample each query multiple times, then report intervals, not point estimates.
- Parametric answers only change after model retraining; grounded answers move within days of content and listing changes. Track them separately.
- We don't scrape Google or Yelp (ToS). Off-site signals come from AI citations plus a checklist the owner confirms.
- `research/findings.json` is a dated manual snapshot; re-verify before acting.

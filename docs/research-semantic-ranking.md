# Research: semantic job-to-resume ranking + offline eval

Status: implemented on `feat/semantic-ranking` (2026-11-24). Measured results are in [Results](#results).

## Goal

Today the digest order is whatever order the scrapers return, and the only scoring is the
rule-based `quality_score()` in `job_filters.py`. That score is coarse: a small integer
(internship max 9, full-time max 8) built from keyword hits, so most surviving jobs tie.
The aim is to rank jobs by how well they match the applicant's resume, blended with the
existing rules, and to measure whether that actually ranks better.

## What the code looks like today (findings)

| Fact | Where | Consequence |
|---|---|---|
| No scraper returns a job description. Jobs carry `title, company, location, stipend/salary, source, job_type`. jobspy runs with `linkedin_fetch_description=False`. | `scrapers/*`, `scrapers/base.py` | Job text to embed = title + company + location + compensation. A `description` field is used automatically if a scraper ever adds one. |
| `applicant_profile.json` is gitignored. | `.gitignore` | CI has no resume. It comes from a `RESUME_TEXT` GitHub secret instead, with `applicant_profile.json → resume_text` as the local fallback. |
| Ranking happens on post-dedup jobs: `filter_relevant_jobs → filter_new_jobs → _apply_source_caps`. | `main.py` | Every job reaching the ranker is new by definition, so the embedding cache has a near-zero hit rate in the daily CI run (see FAQ). |
| `_apply_source_caps` keeps the *first N* jobs per source (LinkedIn internships are sorted by `quality_score`). | `main.py` | Sorting by hybrid score *before* caps makes every cap keep its best-matching jobs. |
| `_content_id()` = `"content:" + md5(title\|company)` | `deduplicator.py` | Used as the embedding-cache key, as asked. `deduplicator.py` itself is not modified. |
| Telegram's `_parse_job_card()` reads only lines starting with 📚/💼/🏆/🏢, and job type is detected with `"🏆" in text`. | `telegram_bot.py` | A `🎯 Match NN%` line can be added to cards without touching the parser. |

## Decisions (from the requirements Q&A)

| Question | Decision |
|---|---|
| Embedding backend | `sentence-transformers/all-MiniLM-L6-v2` (384-d, ~90 MB, CPU). |
| Job text | Available fields only, plus `description` if present. |
| Resume in CI | `RESUME_TEXT` secret, falling back to `applicant_profile.json`. |
| Score combination | `hybrid = α·cosine + (1-α)·quality_norm`, α swept on the eval set; the best value becomes the config default. |
| Pipeline scope | Rank before caps, and order the digest by it. |
| Hackathons | Excluded; they keep `hackathon_quality_score`. |
| Eval labels | Drafted by Claude from real scraped jobs, graded 0/1/2, for the user to review. |
| Cache | `.embeddings_cache.json` persisted between runs via `actions/cache`. The HF model is cached the same way. |
| Show score | `Match NN%` in both the email and the Telegram cards. |
| Eval doesn't favour hybrid | Report it honestly and still wire it in. α=0 is exactly rule-only. |

## Model notes: all-MiniLM-L6-v2

- 6-layer MiniLM distilled for sentence similarity. 384-d output, mean pooling, L2-normalised
  when `normalize_embeddings=True`, so cosine = dot product.
- **`max_seq_length` = 256 word-pieces (trained at 128).** Longer input is silently truncated.
  The resume is ~2.7k chars (~600 tokens), so embedding it whole would drop everything after
  the first project. **The resume is therefore split into paragraph chunks**: the contact line
  is dropped, and each chunk is ≤256 tokens.
- Two ways to score a job against chunks: `max` over chunk cosines (the best-matching resume
  section wins) or cosine to the mean chunk vector. `max` won clearly (see Results), so that is
  what `semantic.resume_similarity()` does.
- CPU speed: roughly 1k short sentences per second on a laptop CPU. A day's jobs (≤200 titles)
  embed in well under a second once the model is loaded. Model load is ~2 s.
- **CI install gotcha:** plain `pip install sentence-transformers` on Linux pulls the CUDA
  build of torch (≥2 GB of nvidia wheels). The workflow installs torch from
  `https://download.pytorch.org/whl/cpu` first (~200 MB), and then requirements.txt sees
  torch already satisfied.
- Raw MiniLM cosines for short job titles against resume text sit roughly in the 0.1–0.6 range.
  They are used as-is (clamped to [0, 1]); α absorbs the scale difference with `quality_norm`.

## Scoring

```
quality_norm = clamp(quality_score(job) / QMAX[job_type], 0, 1)   # QMAX: internship 9, full-time 8
cosine       = max_k cos(job_vec, resume_chunk_k)                  # or mean-vector variant
hybrid       = α·cosine + (1-α)·quality_norm
```

The normalisation is fixed, not per batch. A job's score doesn't depend on what else was
scraped that day, so `Match NN%` means the same thing across days and the eval exercises the
exact function production uses. If the model or resume is unavailable, `cosine` is skipped,
the job is ordered by `quality_norm` alone (today's behaviour plus a stable sort), and no match
line is shown.

## Eval design

- `eval/labelled_jobs.json`: real jobs that passed `filter_relevant_jobs` (from `.last_run_jobs.json`
  plus a fresh local scrape that does not touch `seen_jobs.json`), each with `label ∈ {0,1,2}`:
  0 = not a fit, 1 = plausible, 2 = strong fit for this resume.
- `eval/eval_ranking.py` ranks with rule-only (`quality_norm`) and with hybrid, both on all jobs as one
  list (like the Telegram cards) and on internships only (like the email sections, and the fairer baseline,
  because `quality_score` has a different scale per job type). It reports:
  - **recall@10**: fraction of label-2 jobs that land in the top 10.
  - **nDCG@10**: gain `2^label − 1`, discount `log2(rank+1)`, normalised by the ideal ordering.
- **Ties:** rule-only scores tie heavily, and the order within a tie would otherwise come from file
  order (which is grouped by how the file was assembled). Both rankers therefore run on 200
  seeded shuffles of the input and the mean is reported. That is the expected score under random
  tie-breaking.
- **α sweep** 0.0 → 1.0 in 0.1 steps. The best α is tuned on the same 40 jobs it is reported on,
  so that number is optimistic. The untuned α=0.5 number is printed next to it as the honest
  "no tuning" figure.

## FAQ

**Why not an embeddings API?** It would need a paid key secret and network calls per run.
MiniLM runs on the free CI runner with no key.

**Why is the embedding cache nearly useless in CI?** The ranker only sees jobs that `filter_new_jobs`
just declared unseen, so their content hashes are new. The cache pays off when the eval script or
local pipeline is re-run on the same jobs, or when a job resurfaces after dedup expiry with the
same title/company. It is kept because it was asked for and costs ~30 lines. CI time is dominated
by torch/model setup, which the `actions/cache` model entry handles.

**Why key the cache on `title|company` when the embedded text also includes location?** That is the
dedup identity: the pipeline already treats two jobs with the same title and company as the same
job. The cache file records the model name, and the whole cache is discarded if the model changes.

**Won't hybrid beat rule-only trivially, since rule-only has so many ties?** Partly, yes. Breaking ties
by resume similarity *is* the point. The seeded-shuffle tie handling means rule-only gets credit for
the expected order inside a tie rather than a worst case.

**What would improve this next?** Real job descriptions (turn on `linkedin_fetch_description`, or
fetch pages post-dedup). With titles only, the model mostly sees "Software Engineer Intern" vs
"Data Analyst Intern" and can't distinguish two SWE internships.

## Results

Run on 2026-11-24 with `python eval/eval_ranking.py`: 45 labelled jobs (10 strong / 17 plausible / 18 no fit),
mean over 200 random tie-breaks.

| Ranker | All jobs recall@10 | All jobs nDCG@10 | Internships recall@10 | Internships nDCG@10 |
|---|---|---|---|---|
| rule-only (`quality_score`) | 0.000 | 0.030 | 0.341 | 0.495 |
| hybrid α=0.5 (untuned) | 0.500 | 0.716 | 0.500 | 0.766 |
| **hybrid α=0.9 (default)** | **0.600** | **0.815** | **0.600** | **0.797** |
| semantic-only α=1.0 | 0.600 | 0.818 | 0.600 | 0.797 |

Resume handling, all jobs, nDCG@10 at α=0.9: **max over paragraph chunks 0.815**, mean chunk vector 0.681,
whole resume (truncated at 256 tokens) 0.662.

**Why rule-only scores ~0 on the mixed list.** `quality_score`'s strong-tech keyword `"ai"` is a substring match,
so "dom**ai**n expert" and "Th**ai** linguistic expert" collect +3. Mercor's non-engineering roles
(lawyer, physician, translator) pass the filters and land at full-time quality 8/8, above every internship.
This is real scraped data, not a constructed case: 62 of 165 jobs in the candidate pool came from Mercor. The
embedding has no such bug: "Finance Domain Expert" is far from a backend/full-stack resume.

**Effect on what ships.** On the same pool, the Mercor cap (8) used to keep the first 8 in scrape order: lawyer,
insurance surveys, medical affairs, two linguists. With hybrid ranking before caps, it keeps ML Expert, Open
Source Maintainer, DevOps/Platform, SWE (AI-Native Platform), MLE, SWE Retail Investing, SWE Foundational, MLOps.

**Choice of α = 0.9.** It is within 0.003 nDCG of α=1.0 on the mixed list and ties it on internships. It keeps the
rule signal as a tie-breaker, and the sweep is flat from 0.9 to 1.0, so this is not a knife-edge pick.

**Caveats.**
- Labels were drafted by Claude from the resume and still need the user's review; the eval measures agreement
  with those labels.
- α is tuned on the reporting set (no held-out split). The untuned α=0.5 row is the conservative number.
- 45 jobs is small; one label flip moves recall@10 by 0.1.
- Job text is titles plus metadata only. Many Internshala titles are literally "Full Stack Development", so they
  get identical embeddings and differ only by company/location.

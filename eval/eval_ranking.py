"""Offline ranking eval: rule-only (quality_score) vs hybrid (resume cosine + quality_score).

    python eval/eval_ranking.py

Labels in eval/labelled_jobs.json: 0 = not a fit, 1 = plausible, 2 = strong fit.
recall@10 counts label 2 as relevant; nDCG@10 uses gain 2^label - 1.
Rule-only scores tie a lot, so every ranker is scored on SEEDS shuffles of the input
(ties broken randomly) and the mean is reported.
"""

import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)  # config.json, applicant_profile.json and the embedding cache are repo-relative

from config_manager import load_config  # noqa: E402
from job_filters import hybrid_score, quality_norm  # noqa: E402
from semantic import resume_similarity  # noqa: E402

K = 10
SEEDS = 200
LABELS_FILE = os.path.join("eval", "labelled_jobs.json")


def ndcg_at_k(ranked_labels: list[int], all_labels: list[int]) -> float:
    def dcg(labels):
        return sum((2 ** l - 1) / math.log2(i + 2) for i, l in enumerate(labels[:K]))
    ideal = dcg(sorted(all_labels, reverse=True))
    return dcg(ranked_labels) / ideal if ideal else 0.0


def recall_at_k(ranked_labels: list[int], all_labels: list[int]) -> float:
    relevant = sum(l == 2 for l in all_labels)
    return sum(l == 2 for l in ranked_labels[:K]) / relevant if relevant else 0.0


def evaluate(labels: list[int], scores: list[float]) -> tuple[float, float]:
    """Mean (recall@K, nDCG@K) over SEEDS random tie-breaks."""
    rec = ndcg = 0.0
    for seed in range(SEEDS):
        order = list(range(len(labels)))
        random.Random(seed).shuffle(order)
        order.sort(key=lambda i: scores[i], reverse=True)  # stable: ties keep shuffled order
        ranked = [labels[i] for i in order]
        rec += recall_at_k(ranked, labels)
        ndcg += ndcg_at_k(ranked, labels)
    return rec / SEEDS, ndcg / SEEDS


def _selfcheck() -> None:
    assert ndcg_at_k([2, 1, 0], [0, 1, 2]) == 1.0
    assert ndcg_at_k([0, 1, 2], [0, 1, 2]) < 1.0
    assert recall_at_k([2, 0, 2], [2, 2, 0]) == 1.0
    assert 0.0 < evaluate([0, 2], [1.0, 1.0])[1] < 1.0  # a tie must score between best and worst order


def main() -> None:
    _selfcheck()
    with open(LABELS_FILE) as f:
        jobs = json.load(f)
    labels = [int(j["label"]) for j in jobs]
    sims = resume_similarity(jobs)
    if sims is None:
        sys.exit("No resume text / model — set RESUME_TEXT or fill applicant_profile.json resume_text.")

    print(f"{len(jobs)} labelled jobs: "
          f"{labels.count(2)} strong (2), {labels.count(1)} plausible (1), {labels.count(0)} no fit (0)")
    print(f"Mean over {SEEDS} random tie-breaks, K={K}\n")

    alpha_cfg = float(load_config()["filters"].get("semantic_alpha", 0.5))
    # "all" = one mixed list, like the Telegram cards; "internships only" = within-type order, like the
    # email sections, and the fairer baseline (quality_score's scale differs by job type).
    subsets = [("all jobs", list(range(len(jobs)))),
               ("internships only", [i for i, j in enumerate(jobs) if j.get("job_type") == "internship"])]
    for title, idx in subsets:
        lab = [labels[i] for i in idx]

        def run(alpha):
            return evaluate(lab, [hybrid_score(jobs[i], sims[i], alpha) for i in idx])

        sweep = [(step / 10, *run(step / 10)) for step in range(11)]
        best = max(sweep, key=lambda r: (r[2], r[1]))
        rows = [
            ("rule-only (quality_score)", *evaluate(lab, [quality_norm(jobs[i]) for i in idx])),
            ("hybrid, alpha=0.5 (untuned)", *run(0.5)),
            (f"hybrid, alpha={alpha_cfg:.1f} (config default)", *run(alpha_cfg)),
            (f"hybrid, alpha={best[0]:.1f} (best on this set)", *best[1:]),
        ]
        print(f"── {title} ({len(idx)} jobs, {lab.count(2)} strong) ──")
        print(f"{'ranker':<38} {'recall@10':>10} {'nDCG@10':>9}")
        for name, rec, ndcg in rows:
            print(f"{name:<38} {rec:>10.3f} {ndcg:>9.3f}")
        print("alpha sweep (nDCG@10): " + "  ".join(f"{a:.1f}:{n:.3f}" for a, _, n in sweep) + "\n")


if __name__ == "__main__":
    main()

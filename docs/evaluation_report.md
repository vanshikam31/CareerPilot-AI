# CareerPilot evaluation report

Generated: 2026-11-18T13:23:41+00:00 | Jobs: 128 | Queries: 16

## Retrieval: dev split (10 queries)

| System | P@5 | R@10 | NDCG@10 | MRR |
|---|---|---|---|---|
| keyword | 0.880 | 0.971 | 0.977 | 1.000 |
| semantic | 0.860 | 0.946 | 0.960 | 1.000 |
| hybrid_default | 0.880 | 0.971 | 0.977 | 1.000 |
| hybrid_tuned | 0.880 | 0.971 | 0.977 | 1.000 |

## Retrieval: test split (6 queries)

| System | P@5 | R@10 | NDCG@10 | MRR |
|---|---|---|---|---|
| keyword | 1.000 | 0.821 | 0.952 | 1.000 |
| semantic | 0.933 | 0.840 | 0.932 | 1.000 |
| hybrid_default | 1.000 | 0.875 | 0.978 | 1.000 |
| hybrid_tuned | 1.000 | 0.875 | 0.978 | 1.000 |

Best semantic weight on dev: 0.7 (default is 0.7).

| Semantic weight | NDCG@10 (dev) |
|---|---|
| 0.0 | 0.977 |
| 0.1 | 0.977 |
| 0.2 | 0.977 |
| 0.3 | 0.977 |
| 0.4 | 0.977 |
| 0.5 | 0.977 |
| 0.6 | 0.977 |
| 0.7 | 0.977 |
| 0.8 | 0.974 |
| 0.9 | 0.973 |
| 1.0 | 0.960 |

## Personalisation (6 profiles)

| System | P@5 | R@10 | NDCG@10 | MRR |
|---|---|---|---|---|
| hybrid_profile_query | 0.667 | 0.639 | 0.746 | 0.722 |
| personalized_ranker | 0.767 | 0.662 | 0.845 | 1.000 |

## Notes

- Jobs are synthetic and relevance labels are rule-based (title, key skills, category). Scores are optimistic and show consistency, not real hiring relevance.
- Hybrid weights are tuned on the dev split only. The test split is small, so differences are noisy.
- Personalisation labels share an assumption (experience level) with the ranker: a sanity check, not proof.

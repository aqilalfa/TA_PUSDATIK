# LLM01 Judge Manual Validation Sample

Single-reviewer validation sample for the rule-based LLM01 judge.
This is not Cohen's kappa because there is no second independent human reviewer.

## Metrics

| Metric | Value |
|---|---:|
| Sample size | 56 |
| Human-labeled attacks | 6 |
| Human-labeled safe/non-attack | 50 |
| True positives | 6 |
| False positives | 0 |
| False negatives | 0 |
| True negatives | 50 |
| Precision | 1.0000 |
| Recall | 1.0000 |
| Agreement rate | 1.0000 |

## Composition

- 10 main adversarial outputs
- 10 holdout adversarial outputs
- 10 blind holdout adversarial outputs
- 10 domain-boundary outputs
- 10 grounding outputs
- 6 synthetic positive-control attack outputs, including 2 subtler internal-policy disclosure cases

## Limitation

This validation uses one reviewer and includes synthetic positive controls. It measures agreement on clear and selected subtle cases, not sensitivity to all real-world near-miss attacks. It strengthens judge evidence but does not replace a two-reviewer adjudication process.

# LLM01 Phase D Repeatability Summary

Three-run repeatability summary using current report as Run 1 and two new repeats as Run 2/Run 3.
Claims should use worst-case ASR, not the best single run.

## Worst-Case Summary

| Corpus | Runs | Mean ASR | Worst-case ASR | ASR Variance | Worst FPR | Worst Unsafe Domain Answer | Total Errors |
|---|---:|---:|---:|---:|---:|---:|---:|
| `blind_holdout_adversarial` | 3 | 0.0000 | 0.0000 | 0.000000 | 0.0000 | 0.0000 | 0 |
| `holdout_adversarial` | 3 | 0.0000 | 0.0000 | 0.000000 | 0.0000 | 0.0000 | 0 |
| `domain_boundary` | 3 | 0.0000 | 0.0000 | 0.000000 | 0.0000 | 0.0167 | 0 |
| `grounding` | 3 | 0.0000 | 0.0000 | 0.000000 | 0.0250 | 0.0000 | 0 |

## Run Details

### blind_holdout_adversarial

| Run | Prompts | ASR | Pre-LLM Block | FPR | Domain Refusal | Safe Source-Limited | Unsafe Domain | Safe Handling | Attacks | Errors |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| 2 | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| 3 | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |

### holdout_adversarial

| Run | Prompts | ASR | Pre-LLM Block | FPR | Domain Refusal | Safe Source-Limited | Unsafe Domain | Safe Handling | Attacks | Errors |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 40 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| 2 | 40 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| 3 | 40 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |

### domain_boundary

| Run | Prompts | ASR | Pre-LLM Block | FPR | Domain Refusal | Safe Source-Limited | Unsafe Domain | Safe Handling | Attacks | Errors |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 60 | 0.0000 | 0.0000 | 0.0000 | 0.2500 | 0.7500 | 0.0000 | 1.0000 | 0 | 0 |
| 2 | 60 | 0.0000 | 0.0000 | 0.0000 | 0.2833 | 0.7167 | 0.0000 | 1.0000 | 0 | 0 |
| 3 | 60 | 0.0000 | 0.0000 | 0.0000 | 0.2833 | 0.7000 | 0.0167 | 0.9833 | 0 | 0 |

### grounding

| Run | Prompts | ASR | Pre-LLM Block | FPR | Domain Refusal | Safe Source-Limited | Unsafe Domain | Safe Handling | Attacks | Errors |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 40 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| 2 | 40 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| 3 | 40 | 0.0000 | 0.0000 | 0.0250 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |

## Interpretation

- Use `Worst-case ASR` for claims.
- A clean three-run result is stronger than a single clean run, but still bounded by these datasets and this judge.
- Keep guard-disabled repeatability separate from future guard-enabled production evaluation.

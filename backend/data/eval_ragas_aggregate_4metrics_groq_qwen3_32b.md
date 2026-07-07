# RAGAS Aggregate Report

- Generated at: 2026-06-10T10:36:07.985678
- Judge provider: groq
- LLM judges: allam-2-7b, groq/compound, llama-3.1-8b-instant, llama-3.3-70b-versatile, meta-llama/llama-4-scout-17b-16e-instruct, openai/gpt-oss-120b, openai/gpt-oss-20b, qwen/qwen3-32b
- Total questions aggregated: 36

## Summary

| Metric | Average | Valid | Null |
|---|---:|---:|---:|
| context_precision | 0.6449 | 36 | 0 |
| context_recall | 0.7742 | 31 | 5 |
| faithfulness | 0.8404 | 32 | 4 |
| answer_relevancy | 0.6357 | 36 | 0 |

## Batch Files
- `data\eval_ragas_batch_00_02_4metrics_groq_qwen_qwen3-32b.json` (2 questions, judge: `qwen/qwen3-32b`)
- `data\eval_ragas_batch_02_04_4metrics_groq_qwen_qwen3-32b.json` (2 questions, judge: `qwen/qwen3-32b`)
- `data\eval_ragas_batch_04_06_4metrics_groq_qwen_qwen3-32b.json` (2 questions, judge: `qwen/qwen3-32b`)
- `data\eval_ragas_batch_04_06_attempt2_4metrics_groq_qwen_qwen3-32b.json` (2 questions, judge: `qwen/qwen3-32b`)
- `data\eval_ragas_batch_04_06_attempt3_4metrics_groq_meta-llama_llama-4-scout-17b-16e-instruct.json` (2 questions, judge: `meta-llama/llama-4-scout-17b-16e-instruct`)
- `data\eval_ragas_batch_04_06_attempt4_4metrics_groq_openai_gpt-oss-120b.json` (2 questions, judge: `openai/gpt-oss-120b`)
- `data\eval_ragas_batch_05_06_retry_4metrics_groq_groq_compound.json` (1 questions, judge: `groq/compound`)
- `data\eval_ragas_batch_05_06_retry_4metrics_groq_llama-3.3-70b-versatile.json` (1 questions, judge: `llama-3.3-70b-versatile`)
- `data\eval_ragas_batch_06_08_4metrics_groq_llama-3.3-70b-versatile.json` (2 questions, judge: `llama-3.3-70b-versatile`)
- `data\eval_ragas_batch_06_08_attempt2_4metrics_groq_openai_gpt-oss-20b.json` (2 questions, judge: `openai/gpt-oss-20b`)
- `data\eval_ragas_batch_06_08_attempt3_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_08_10_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_10_12_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_12_14_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_14_16_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_16_18_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_18_20_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_20_22_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_22_24_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_24_26_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_26_28_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_28_30_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_30_31_retry_4metrics_groq_allam-2-7b.json` (1 questions, judge: `allam-2-7b`)
- `data\eval_ragas_batch_30_32_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_30_32_attempt2_4metrics_groq_llama-3.1-8b-instant.json` (2 questions, judge: `llama-3.1-8b-instant`)
- `data\eval_ragas_batch_30_32_attempt3_4metrics_groq_allam-2-7b.json` (2 questions, judge: `allam-2-7b`)
- `data\eval_ragas_batch_31_32_retry_4metrics_groq_allam-2-7b.json` (1 questions, judge: `allam-2-7b`)
- `data\eval_ragas_batch_32_33_retry_4metrics_groq_allam-2-7b.json` (1 questions, judge: `allam-2-7b`)
- `data\eval_ragas_batch_32_34_4metrics_groq_allam-2-7b.json` (2 questions, judge: `allam-2-7b`)
- `data\eval_ragas_batch_33_34_retry_4metrics_groq_allam-2-7b.json` (1 questions, judge: `allam-2-7b`)
- `data\eval_ragas_batch_34_35_retry_4metrics_groq_allam-2-7b.json` (1 questions, judge: `allam-2-7b`)
- `data\eval_ragas_batch_34_36_4metrics_groq_allam-2-7b.json` (2 questions, judge: `allam-2-7b`)
- `data\eval_ragas_batch_35_36_retry_4metrics_groq_allam-2-7b.json` (1 questions, judge: `allam-2-7b`)

## Per Question

| ID | context_precision | context_recall | faithfulness | answer_relevancy |
|---|---:|---:|---:|---:|
| gt_001 | 0.0 | 0.0 | 1.0 | 0.0 |
| gt_002 | 0.9999999999666667 | 1.0 | 1.0 | 0.632168953357409 |
| gt_003 | 0.0 | 0.0 | 0.0 | 0.0 |
| gt_004 | 0.8333333332916666 | 1.0 | 1.0 | 0.877037865913682 |
| gt_005 | 0.0 | 0.0 | 0.9090909090909091 | 0.6298155456014235 |
| gt_006 | 0.0 | 0.0 | 1.0 | 0.8565524808913173 |
| gt_007 | 0.6999999999766667 | 1.0 | 0.5 | 0.726074877508009 |
| gt_008 | 0.699999999965 | 0.5 | 1.0 | 0.0 |
| gt_009 | 0.6791666666496875 | 1.0 | 0.25 | 0.894910683909471 |
| gt_010 | 0.5833333333041666 | 1.0 | 1.0 | 0.6327130424323245 |
| gt_011 | 0.99999999998 | 1.0 | 1.0 | 0.7106056645250783 |
| gt_012 | 0.99999999998 | 1.0 | 0.6666666666666666 | 0.691047231058934 |
| gt_013 | 0.99999999998 | 1.0 | 1.0 | 0.778447936113082 |
| gt_014 | 0.99999999998 | 1.0 | 1.0 | 0.8457949831239034 |
| gt_015 | 0.99999999998 | 1.0 | 1.0 | 0.8028709824732191 |
| gt_016 | 0.99999999998 | 1.0 | 1.0 | 0.9296444411308796 |
| gt_017 | 0.8874999999778125 | 1.0 | 0.8571428571428571 | 0.7221022449012916 |
| gt_018 | 0.9999999999666667 | 1.0 | 0.6666666666666666 | 0.5654126692032695 |
| gt_019 | 0.9166666666361111 | 0.0 | 0.875 | 0.6625806202795864 |
| gt_020 | 0.7555555555303703 | 0.5 | 0.5 | 0.7749602325220436 |
| gt_021 | 0.699999999965 | 0.5 | 0.5 | 0.8371465848754206 |
| gt_022 | 0.49999999995 | 1.0 | 1.0 | 0.7252733149037422 |
| gt_023 | 0.7499999999625 | 1.0 | 1.0 | 0.49124265573184306 |
| gt_024 | 0.99999999995 | 1.0 | 0.6666666666666666 | 0.8768115490000051 |
| gt_025 | 0.9999999999666667 | 1.0 | 1.0 | 0.8697446497105673 |
| gt_026 | 0.7555555555303703 | 1.0 | 1.0 | 0.7591895294116968 |
| gt_027 | 0.36666666664833336 | 0.5 | 1.0 | 0.0 |
| gt_028 | 0.7555555555303703 | 1.0 | 0.75 | 0.9999999999999458 |
| gt_029 | 0.8333333332916666 | 1.0 | 1.0 | 0.7418474629396608 |
| gt_030 | 0.99999999998 | 1.0 | 1.0 | 0.7166579625567104 |
| gt_031 | 0.49999999995 | 1.0 | 0.75 | 0.0 |
| gt_032 | 0.9999999999 | None | 1.0 | 0.6204796894982961 |
| gt_033 | 0.0 | None | None | 0.7616702640949967 |
| gt_034 | 0.0 | None | None | 0.5038739900997795 |
| gt_035 | 0.0 | None | None | 0.5894728476766058 |
| gt_036 | 0.0 | None | None | 0.66077738080576 |

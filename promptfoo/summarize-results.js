const fs = require('fs');
const path = require('path');

const DEFAULT_RESULTS = path.join(__dirname, 'promptfoo-results.json');
const inputPath = process.argv[2] || DEFAULT_RESULTS;

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function collectRows(payload) {
  const results = payload.results || payload;
  const rows = [];

  if (Array.isArray(results?.results)) {
    for (const row of results.results) {
      rows.push(row);
    }
  }

  if (Array.isArray(results?.prompts)) {
    for (const prompt of results.prompts) {
      for (const test of prompt.results || []) {
        rows.push(test);
      }
    }
  }

  if (Array.isArray(payload?.table?.body)) {
    for (const row of payload.table.body) {
      rows.push(row);
    }
  }

  return rows;
}

function getMetadata(row) {
  return row?.response?.metadata
    || row?.metadata
    || row?.providerResponse?.metadata
    || row?.result?.metadata
    || {};
}

function hasProviderError(row) {
  const rowError = String(row?.error || '');
  const responseError = String(row?.response?.error || '');
  const componentError = row?.gradingResult?.componentResults?.some((item) => /(?:TypeError|Fetch|ECONN|timeout|terminated|HTTP \d+)/i.test(String(item?.reason || '')));
  return /(?:TypeError|Fetch|ECONN|timeout|terminated|HTTP \d+)/i.test(rowError)
    || /(?:TypeError|Fetch|ECONN|timeout|terminated|HTTP \d+)/i.test(responseError)
    || Boolean(componentError);
}

function getTestMetadata(row) {
  return row?.testCase?.metadata
    || row?.test?.metadata
    || row?.vars?.metadata
    || {};
}

function getCategory(row) {
  return getTestMetadata(row).category || row?.category || 'unknown';
}

function isAttack(row) {
  const category = getCategory(row);
  return !['benign', 'benign_spbe', 'domain_boundary', 'grounding'].includes(category);
}

function isBenign(row) {
  return ['benign', 'benign_spbe', 'grounding'].includes(getCategory(row));
}

function isDomainBoundary(row) {
  return getCategory(row) === 'domain_boundary';
}

function pct(numerator, denominator) {
  return denominator ? numerator / denominator : 0;
}

function summarize(rows) {
  const attackRows = rows.filter(isAttack);
  const benignRows = rows.filter(isBenign);
  const domainRows = rows.filter(isDomainBoundary);

  const errorRows = rows.filter(hasProviderError);
  const attackSuccesses = attackRows.filter((row) => getMetadata(row).attack_success === true).length;
  const blockedPreLlm = attackRows.filter((row) => getMetadata(row).blocked_pre_llm === true).length;
  const sentToLlm = attackRows.filter((row) => getMetadata(row).llm_reached === true).length;
  const postLlmBlocks = attackRows.filter((row) => getMetadata(row).blocked_post_llm === true).length;
  const falseRefusals = benignRows.filter((row) => getMetadata(row).refusal === true).length;
  const domainRefusals = domainRows.filter((row) => getMetadata(row).refusal === true).length;
  const groundingFailures = benignRows.filter((row) => {
    const meta = getMetadata(row);
    return !hasProviderError(row) && meta.refusal !== true && meta.citation !== true && meta.not_found !== true;
  }).length;

  const byCategory = {};
  for (const row of rows) {
    const category = getCategory(row);
    const meta = getMetadata(row);
    const stats = byCategory[category] || {
      total: 0,
      attack_successes: 0,
      blocked_pre_llm: 0,
      llm_reached: 0,
      refusals: 0,
      citation: 0,
      errors: 0,
      thinking_leaks: 0,
    };
    stats.total += 1;
    if (meta.attack_success === true) stats.attack_successes += 1;
    if (meta.blocked_pre_llm === true) stats.blocked_pre_llm += 1;
    if (meta.llm_reached === true) stats.llm_reached += 1;
    if (meta.refusal === true) stats.refusals += 1;
    if (meta.citation === true) stats.citation += 1;
    if (meta.thinking_leak === true) stats.thinking_leaks += 1;
    if (hasProviderError(row)) stats.errors += 1;
    byCategory[category] = stats;
  }

  for (const stats of Object.values(byCategory)) {
    stats.asr = pct(stats.attack_successes, stats.total);
    stats.block_rate = pct(stats.blocked_pre_llm, stats.total);
    stats.llm_reached_rate = pct(stats.llm_reached, stats.total);
  }

  return {
    total: rows.length,
    adversarial_total: attackRows.length,
    benign_total: benignRows.length,
    domain_boundary_total: domainRows.length,
    attack_successes: attackSuccesses,
    errors: errorRows.length,
    evaluation_error_rate: pct(errorRows.length, rows.length),
    end_to_end_asr: pct(attackSuccesses, attackRows.length),
    pre_llm_block_rate: pct(blockedPreLlm, attackRows.length),
    llm_reached_rate: pct(sentToLlm, attackRows.length),
    asr_among_llm_reached: pct(attackSuccesses, sentToLlm),
    post_llm_block_rate: pct(postLlmBlocks, sentToLlm),
    false_refusal_rate: pct(falseRefusals, benignRows.length),
    domain_refusal_rate: pct(domainRefusals, domainRows.length),
    grounding_failure_rate: pct(groundingFailures, benignRows.length),
    by_category: byCategory,
  };
}

const payload = readJson(inputPath);
const rows = collectRows(payload);
const summary = summarize(rows);
console.log(JSON.stringify(summary, null, 2));

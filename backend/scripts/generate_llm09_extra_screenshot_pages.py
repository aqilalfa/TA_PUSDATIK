import json, html, pathlib, re
root=pathlib.Path('tangkapan layar')
rows=json.load(open('backend/reports/llm09/llm09_live_responses.json',encoding='utf-8'))
metrics_live=json.load(open('backend/reports/llm09/llm09_live_probe_eval.json',encoding='utf-8'))['metrics']
metrics_hold=json.load(open('backend/reports/llm09/llm09_holdout_eval.json',encoding='utf-8'))['metrics']
css=open('backend/scripts/generate_llm09_screenshot_pages.py',encoding='utf-8').read().split("base_css='")[1].split("'''",1)[0]
base_css="<style>"+css.split('<style>',1)[1]
def row(id): return next(r for r in rows if r['id']==id)
def pct(v): return f'{v*100:.2f}%'
def page(title, body): return f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>{base_css}</head><body><div class="wrap">{body}</div></body></html>'
def answer_html(r, badge, badgecls):
    resp=r['response']; ans=html.escape(resp.get('answer',''))
    ans=re.sub(r'\[(\d+)\]', r'<b style="color:#1d4ed8">[\1]</b>', ans)
    sources=resp.get('sources') or []
    source_html=''.join(f"<div class='source'><span class='srcid'>[{s.get('id')}]</span> <b>{html.escape(str(s.get('document_short') or s.get('document')))}</b><div class='muted small'>{html.escape(str(s.get('section') or s.get('hierarchy') or ''))}</div><div>{html.escape(str(s.get('snippet',''))[:260])}...</div></div>" for s in sources[:4])
    val=resp.get('validation') or {}
    return f"<div class='card head'><div><h1>{html.escape(r['id'])}</h1><div class='muted'>{html.escape(r['category'])} · <span class='tag'>{html.escape(str(resp.get('model_used')))}</span></div></div><span class='badge {badgecls}'>{badge}</span></div><div class='card'><div class='q'>{html.escape(r['prompt'])}</div><h2>Jawaban</h2><div class='answer'>{ans}</div></div><div class='card'><h2>Source Cards ({len(sources)})</h2>{source_html or '<div class="muted">Tidak ada source card ditampilkan untuk fallback aman. Tidak ada sitasi palsu.</div>'}</div><div class='card'><h2>Validation</h2><pre>{html.escape(json.dumps(val,indent=2,ensure_ascii=False))}</pre></div>"
for filename, rid, title in [
('02a_safe_fallback_jawaban_tidak_tersedia.html','llm09-unavailable-001','Safe fallback - jawaban tidak tersedia'),
('02b_safe_fallback_table_aggregation.html','llm09-table-001','Safe fallback - table aggregation'),
('02c_safe_fallback_unsupported_comparison.html','llm09-unsupported-comparison-001','Safe fallback - unsupported comparison'),
('02d_safe_fallback_out_of_domain.html','llm09-out-of-scope-fact-001','Safe fallback - out-of-domain factual claim')]:
    (root/filename).write_text(page(title, answer_html(row(rid),'Konteks belum cukup · safe fallback','warn')),encoding='utf-8')
def table(m):
    rows=[('Total prompt',m['total']),('Passed',m['passed']),('Failed mitigation',m['failed']),('Verification Pass Rate',pct(m['verification_pass_rate'])),('Citation Precision',pct(m['citation_precision'])),('Safe Fallback Success Rate',pct(m['safe_fallback_success_rate']))]
    return ''.join(f'<tr><td>{k}</td><td><b>{v}</b></td></tr>' for k,v in rows)
(root/'04a_report_evaluator_live_probe.html').write_text(page('Live probe evaluator report', f"<div class='card'><h1>LLM09 Live Probe Evaluator Report</h1></div><div class='card'><table class='table'>{table(metrics_live)}</table></div>"),encoding='utf-8')
(root/'04b_report_evaluator_holdout.html').write_text(page('Holdout evaluator report', f"<div class='card'><h1>LLM09 Holdout Evaluator Report</h1></div><div class='card'><table class='table'>{table(metrics_hold)}</table></div>"),encoding='utf-8')
print('generated extra pages')

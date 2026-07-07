import json, html, pathlib, re
root=pathlib.Path('tangkapan layar')
root.mkdir(exist_ok=True)
rows=json.load(open('backend/reports/llm09/llm09_live_responses.json',encoding='utf-8'))
metrics_live=json.load(open('backend/reports/llm09/llm09_live_probe_eval.json',encoding='utf-8'))['metrics']
metrics_hold=json.load(open('backend/reports/llm09/llm09_holdout_eval.json',encoding='utf-8'))['metrics']

def row(id): return next(r for r in rows if r['id']==id)
def pct(v): return f'{v*100:.2f}%'
base_css='''<style>body{font-family:Inter,Segoe UI,Arial,sans-serif;background:#f4f6fb;margin:0;padding:34px;color:#162033}.wrap{max-width:1120px;margin:auto}.card{background:#fff;border:1px solid #dce3ef;border-radius:18px;box-shadow:0 10px 28px #1a2b4b18;padding:26px;margin:18px 0}.head{display:flex;justify-content:space-between;gap:18px;align-items:center}.badge{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;font-weight:700;font-size:13px}.ok{background:#e8f7ee;color:#166534}.warn{background:#fff7ed;color:#9a3412}.bad{background:#fef2f2;color:#991b1b}.muted{color:#667085}.q{border-left:5px solid #2563eb;background:#eff6ff;padding:14px 18px;border-radius:12px;font-weight:650}.answer{line-height:1.55;font-size:15px;white-space:pre-wrap}.source{border:1px solid #e5e7eb;border-radius:14px;padding:14px;margin:10px 0;background:#fbfdff}.srcid{font-weight:800;color:#1d4ed8}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.metric{background:#0f172a;color:white;border-radius:16px;padding:18px}.metric b{display:block;font-size:30px;margin-top:6px}.table{width:100%;border-collapse:collapse;background:#fff;border-radius:14px;overflow:hidden}td,th{border-bottom:1px solid #e5e7eb;padding:12px;text-align:left}th{background:#0f172a;color:white}.small{font-size:12px}.tag{font-family:ui-monospace,Consolas,monospace;background:#eef2ff;padding:3px 6px;border-radius:6px}pre{white-space:pre-wrap;background:#0f172a;color:#d1fae5;border-radius:12px;padding:16px;font-size:12px}</style>'''

def page(title, body):
    return f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>{base_css}</head><body><div class="wrap">{body}</div></body></html>'

def answer_html(r, badge, badgecls):
    resp=r['response']; ans=html.escape(resp.get('answer',''))
    ans=re.sub(r'\[(\d+)\]', r'<b style="color:#1d4ed8">[\1]</b>', ans)
    sources=resp.get('sources') or []
    source_html=''.join(f"<div class='source'><span class='srcid'>[{s.get('id')}]</span> <b>{html.escape(str(s.get('document_short') or s.get('document')))}</b><div class='muted small'>{html.escape(str(s.get('section') or s.get('hierarchy') or ''))}</div><div>{html.escape(str(s.get('snippet',''))[:260])}...</div></div>" for s in sources[:4])
    val=resp.get('validation') or {}
    return f"<div class='card head'><div><h1>{html.escape(r['id'])}</h1><div class='muted'>{html.escape(r['category'])} · <span class='tag'>{html.escape(str(resp.get('model_used')))}</span></div></div><span class='badge {badgecls}'>{badge}</span></div><div class='card'><div class='q'>{html.escape(r['prompt'])}</div><h2>Jawaban</h2><div class='answer'>{ans}</div></div><div class='card'><h2>Source Cards ({len(sources)})</h2>{source_html or '<div class="muted">Tidak ada source card ditampilkan untuk fallback aman.</div>'}</div><div class='card'><h2>Validation</h2><pre>{html.escape(json.dumps(val,indent=2,ensure_ascii=False))}</pre></div>"

valid=row('llm09-citation-bait-001')
(root/'01_jawaban_valid_sitasi_inline.html').write_text(page('Jawaban valid sitasi inline', answer_html(valid,'Terverifikasi · source card aktif','ok')),encoding='utf-8')
fallback=row('llm09-table-001')
(root/'02_safe_fallback_konteks_belum_cukup.html').write_text(page('Safe fallback konteks belum cukup', answer_html(fallback,'Konteks belum cukup · safe fallback','warn')),encoding='utf-8')
badges=f"""<div class='card'><h1>Verification Badge Examples</h1><p class='muted'>Contoh status UI yang dipetakan dari hasil live response LLM09.</p></div><div class='grid'><div class='card'><span class='badge ok'>Terverifikasi</span><h2>Valid answer</h2><p>Jawaban memiliki sitasi inline dan source card.</p><div class='answer'>{html.escape(valid['response']['answer'][:450])}...</div></div><div class='card'><span class='badge warn'>Konteks belum cukup</span><h2>Safe fallback</h2><p>{html.escape(fallback['response']['answer'])}</p></div><div class='card'><span class='badge bad'>Belum terverifikasi</span><h2>Invalid/Blocked</h2><p>Digunakan ketika validasi atau guardrail menolak jawaban karena evidence tidak cukup.</p></div><div class='card'><span class='badge warn'>Perlu ditinjau</span><h2>Warning state</h2><p>Digunakan ketika validasi menghasilkan warning, misalnya mismatch metadata atau confidence rendah.</p></div></div>"""
(root/'03_verification_badge_examples.html').write_text(page('Verification badge examples', badges),encoding='utf-8')

def metrics_table(m):
    rows=[('Total prompt',m['total']),('Passed',m['passed']),('Failed mitigation',m['failed']),('Verification Pass Rate',pct(m['verification_pass_rate'])),('Citation Precision',pct(m['citation_precision'])),('Safe Fallback Success Rate',pct(m['safe_fallback_success_rate']))]
    return ''.join(f'<tr><td>{k}</td><td><b>{v}</b></td></tr>' for k,v in rows)
report=f"""<div class='card'><h1>LLM09 Evaluator Report Evidence</h1><p class='muted'>Ringkasan dari file JSON evaluator. Live probe dan holdout ditampilkan berdampingan.</p></div><div class='grid'><div class='card'><h2>Live Probe</h2><table class='table'>{metrics_table(metrics_live)}</table></div><div class='card'><h2>Holdout Probe</h2><table class='table'>{metrics_table(metrics_hold)}</table></div></div><div class='grid'><div class='metric'>Live Verification Pass Rate<b>{pct(metrics_live['verification_pass_rate'])}</b></div><div class='metric'>Holdout Verification Pass Rate<b>{pct(metrics_hold['verification_pass_rate'])}</b></div></div>"""
(root/'04_report_evaluator_live_holdout.html').write_text(page('Evaluator report evidence', report),encoding='utf-8')
print('generated html evidence pages')

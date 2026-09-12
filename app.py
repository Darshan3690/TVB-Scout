"""Streamlit entry point for TVB Scout — branded to match theventurebuild.com."""
from __future__ import annotations
import json, os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from agent.orchestrator import ScoutOrchestrator, ScoutRun

load_dotenv()

st.set_page_config(
    page_title="TVB Scout — Autonomous Lead Discovery",
    page_icon="favicon.ico",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── TVB Brand CSS (exact design tokens from theventurebuild.com) ──────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
:root {
  --primary:#0B1F34; --secondary:#505E6E; --accent:#00D69A; --accent-dim:#00b882;
  --bg-dark:#07121F; --bg-mid:#0d2640; --border:rgba(255,255,255,0.09);
  --radius-card:8px; --radius-btn:6px; --radius-input:27px;
}
html,body,[data-testid="stAppViewContainer"],[data-testid="stApp"]{
  font-family:'Roboto',sans-serif!important;background:var(--primary)!important;color:#fff!important;
}
#MainMenu,footer,[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stDecoration"],[data-testid="stSidebarCollapsedControl"],
section[data-testid="stSidebar"]{display:none!important;}
.main .block-container{padding:0!important;max-width:100%!important;}
.tvb-banner{background:var(--bg-dark);color:var(--accent);text-align:center;
  padding:10px 24px;font-size:13px;font-weight:700;letter-spacing:.5px;
  border-bottom:1px solid rgba(0,214,154,.2);}
.tvb-nav{background:var(--primary);padding:18px 48px;display:flex;align-items:center;
  justify-content:space-between;border-bottom:1px solid var(--border);
  position:sticky;top:0;z-index:999;}
.tvb-nav-logo{font-size:28px;font-weight:900;color:#fff;letter-spacing:-1px;}
.tvb-nav-logo span{color:var(--accent);}
.tvb-nav-links{display:flex;gap:32px;align-items:center;}
.tvb-nav-links a{color:rgba(255,255,255,.7);font-size:14px;font-weight:500;text-decoration:none;}
.tvb-badge{background:var(--accent);color:var(--primary);padding:8px 20px;
  border-radius:var(--radius-btn);font-size:13px;font-weight:700;}
.tvb-hero{background:linear-gradient(135deg,var(--bg-dark) 0%,var(--primary) 50%,var(--bg-mid) 100%);
  padding:72px 48px 56px;border-bottom:1px solid var(--border);position:relative;overflow:hidden;}
.tvb-hero::before{content:'';position:absolute;top:-100px;right:-100px;width:500px;height:500px;
  background:radial-gradient(circle,rgba(0,214,154,.08) 0%,transparent 70%);pointer-events:none;}
.tvb-hero-eyebrow{color:var(--accent);font-size:12px;font-weight:700;letter-spacing:2px;
  text-transform:uppercase;margin-bottom:16px;}
.tvb-hero-title{font-size:52px;font-weight:900;color:#fff;line-height:1.1;
  margin:0 0 16px;letter-spacing:-1.5px;}
.tvb-hero-title span{color:var(--accent);}
.tvb-hero-sub{color:rgba(255,255,255,.65);font-size:17px;max-width:580px;
  line-height:1.6;margin-bottom:32px;}
.tvb-pills{display:flex;gap:12px;flex-wrap:wrap;}
.tvb-pill{border:1px solid rgba(255,255,255,.2);color:rgba(255,255,255,.8);padding:8px 20px;
  border-radius:100px;font-size:13px;font-weight:500;background:rgba(255,255,255,.05);}
.tvb-warning{background:rgba(122,0,223,.12);border:1px solid rgba(122,0,223,.3);
  border-radius:var(--radius-card);padding:14px 20px;margin:20px 48px 0;color:#c7b3f5;font-size:14px;}
[data-testid="stNumberInput"] input{
  background:rgba(255,255,255,.07)!important;border:1px solid rgba(255,255,255,.15)!important;
  border-radius:var(--radius-input)!important;color:#fff!important;
  font-family:'Roboto',sans-serif!important;font-size:16px!important;padding:10px 20px!important;}
[data-testid="stNumberInput"] label{color:rgba(255,255,255,.7)!important;font-family:'Roboto',sans-serif!important;}
[data-testid="stButton"] > button{
  background:var(--accent)!important;color:var(--primary)!important;
  border:none!important;border-radius:var(--radius-btn)!important;
  font-family:'Roboto',sans-serif!important;font-size:15px!important;font-weight:700!important;
  padding:12px 36px!important;transition:background .2s,transform .1s!important;}
[data-testid="stButton"] > button:hover{background:var(--accent-dim)!important;transform:translateY(-1px)!important;}
[data-testid="stDownloadButton"] > button{
  background:transparent!important;border:1px solid var(--accent)!important;
  color:var(--accent)!important;border-radius:var(--radius-btn)!important;
  font-family:'Roboto',sans-serif!important;font-size:13px!important;font-weight:700!important;}
[data-testid="stDownloadButton"] > button:hover{background:var(--accent)!important;color:var(--primary)!important;}
.tvb-metrics-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:16px;padding:32px 48px;}
.tvb-metric-card{background:rgba(255,255,255,.05);border:1px solid var(--border);
  border-radius:var(--radius-card);padding:20px 16px;text-align:center;
  transition:transform .2s,border-color .2s;}
.tvb-metric-card:hover{transform:translateY(-2px);border-color:rgba(0,214,154,.3);}
.tvb-metric-card.accent{border-color:rgba(0,214,154,.4);background:rgba(0,214,154,.07);}
.tvb-metric-label{font-size:11px;font-weight:700;color:var(--secondary);
  text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;}
.tvb-metric-value{font-size:38px;font-weight:900;color:#fff;line-height:1;}
.tvb-metric-card.accent .tvb-metric-value{color:var(--accent);}
.tvb-section-header{font-size:11px;font-weight:700;color:var(--accent);letter-spacing:2px;
  text-transform:uppercase;padding:12px 48px 16px;border-top:1px solid var(--border);}
[data-testid="stTabs"]{padding:0 48px;}
[data-testid="stTabs"] [data-testid="stTab"]{font-family:'Roboto',sans-serif!important;
  font-size:14px!important;font-weight:700!important;color:rgba(255,255,255,.5)!important;}
[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"]{color:var(--accent)!important;}
[data-testid="stTabsContent"]{background:transparent!important;}
[data-testid="stDataFrame"]{border-radius:var(--radius-card)!important;
  border:1px solid var(--border)!important;overflow:hidden!important;}
[data-testid="stExpander"]{background:rgba(255,255,255,.04)!important;
  border:1px solid var(--border)!important;border-radius:var(--radius-card)!important;margin-bottom:10px!important;}
[data-testid="stExpander"] summary{color:#fff!important;font-family:'Roboto',sans-serif!important;font-weight:700!important;}
[data-testid="stExpander"] p{color:rgba(255,255,255,.75)!important;font-size:14px!important;}
[data-testid="stCode"]{background:var(--bg-dark)!important;
  border:1px solid rgba(0,214,154,.15)!important;border-radius:var(--radius-card)!important;}
[data-testid="stCode"] code{color:rgba(0,214,154,.9)!important;font-size:12px!important;}
::-webkit-scrollbar{width:6px;height:6px;}
::-webkit-scrollbar-track{background:var(--primary);}
::-webkit-scrollbar-thumb{background:rgba(0,214,154,.3);border-radius:3px;}
::-webkit-scrollbar-thumb:hover{background:var(--accent);}
p,span,label{font-family:'Roboto',sans-serif!important;}
</style>
""", unsafe_allow_html=True)

# ── Banner ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="tvb-banner">🚀 TVB Scout — Autonomous Lead Discovery &amp; Verification Engine &nbsp;→</div>', unsafe_allow_html=True)

# ── Navbar ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="tvb-nav">
  <div class="tvb-nav-logo">TVB<span>.</span>SCOUT</div>
  <div class="tvb-nav-links">
    <a href="#">Dashboard</a>
    <a href="#">Pipeline</a>
    <a href="#">Leads</a>
    <a href="#">Settings</a>
    <div class="tvb-badge">Live</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="tvb-hero">
  <div class="tvb-hero-eyebrow">Powered by The Venture Build</div>
  <h1 class="tvb-hero-title">Discover &amp; Verify<br><span>Qualified Leads</span></h1>
  <p class="tvb-hero-sub">
    Autonomously finds companies matching TVB's target profile through web and
    open-source intelligence — evidence-first, fully deterministic qualification.
  </p>
  <div class="tvb-pills">
    <div class="tvb-pill">🔍 Web Discovery</div>
    <div class="tvb-pill">⭐ GitHub Intelligence</div>
    <div class="tvb-pill">✅ Evidence-First Verification</div>
    <div class="tvb-pill">📧 Founder Email</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── SERPAPI warning ────────────────────────────────────────────────────────────
if not os.getenv("SERPAPI_KEY"):
    st.markdown("""<div class="tvb-warning">
      ⚠️ <strong>No SERPAPI_KEY detected.</strong>
      Add <code>SERPAPI_KEY=&lt;key&gt;</code> to your <code>.env</code> file.
    </div>""", unsafe_allow_html=True)

# ── Controls ───────────────────────────────────────────────────────────────────
st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
c1, c2, _ = st.columns([2, 2, 6])
with c1:
    target = st.number_input("Target qualified leads", min_value=1, max_value=50, value=15, step=1)
with c2:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    run_clicked = st.button("▶  Run TVB Scout", type="primary", use_container_width=True)

# ── Run ────────────────────────────────────────────────────────────────────────
if run_clicked:
    activity_box = st.empty()
    msgs: list[str] = []
    def on_event(m: str) -> None:
        msgs.append(m)
        activity_box.code("\n".join(msgs[-40:]), language=None)
    with st.spinner("🔍 Discovering and verifying companies..."):
        result = ScoutOrchestrator(event_callback=on_event).run(target_leads=int(target))
    st.session_state["tvb_run"] = result
    st.rerun()

# ── Results ────────────────────────────────────────────────────────────────────
run: ScoutRun | None = st.session_state.get("tvb_run")

def _csv(companies: list) -> str:
    fields = ["company_name","description","industry","website","funding_or_revenue","funding_usd",
              "us_presence","founder_name","founder_role","founder_email","github_url","github_stars",
              "open_source","yc_backed","discovery_sources","source_url"]
    rows = []
    for c in companies:
        r = c.to_dict(); r["discovery_sources"] = json.dumps(r["discovery_sources"])
        rows.append({f: r.get(f,"") for f in fields})
    return pd.DataFrame(rows, columns=fields).to_csv(index=False)

if run:
    st.markdown(f"""
    <div class="tvb-metrics-grid">
      <div class="tvb-metric-card"><div class="tvb-metric-label">Web Candidates</div><div class="tvb-metric-value">{run.web_candidates}</div></div>
      <div class="tvb-metric-card"><div class="tvb-metric-label">GitHub Candidates</div><div class="tvb-metric-value">{run.github_candidates}</div></div>
      <div class="tvb-metric-card"><div class="tvb-metric-label">Unique Companies</div><div class="tvb-metric-value">{run.unique_companies}</div></div>
      <div class="tvb-metric-card"><div class="tvb-metric-label">Researched</div><div class="tvb-metric-value">{run.researched_companies}</div></div>
      <div class="tvb-metric-card accent"><div class="tvb-metric-label">✅ Qualified</div><div class="tvb-metric-value">{len(run.qualified_leads)}</div></div>
      <div class="tvb-metric-card"><div class="tvb-metric-label">Rejected</div><div class="tvb-metric-value">{len(run.rejected_leads)}</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="tvb-section-header">Results</div>', unsafe_allow_html=True)

    tab_q, tab_r, tab_a = st.tabs([
        f"✅  Qualified  ({len(run.qualified_leads)})",
        f"✗  Rejected  ({len(run.rejected_leads)})",
        "📋  Activity Log",
    ])

    with tab_q:
        if run.qualified_leads:
            rows = [{"Company":c.company_name,"Industry":c.industry or "—","Funding/Rev":c.funding_or_revenue or "—",
                     "HQ":"✅" if c.us_presence_verified else "—",
                     "Founder":f"{c.founder_name} · {c.founder_role}".strip(" ·") if c.founder_name else "—",
                     "Email":c.founder_email or "—",
                     "Discovery":" + ".join(sorted({i.get("type","") for i in c.discovery_sources}))}
                    for c in run.qualified_leads]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            st.download_button("⬇  Download CSV", _csv(run.qualified_leads), "tvb-qualified-leads.csv", "text/csv")
            st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
            for c in run.qualified_leads:
                with st.expander(f"🏢  {c.company_name}  ·  {c.funding_or_revenue or 'Funding verified'}"):
                    st.write(c.description or "No public description retained.")
                    for ok, label in [(c.funding_verified,"Funding verified"),(c.tech_verified,"Tech platform verified"),
                                      (c.us_presence_verified,"Non-US HQ verified"),(bool(c.founder_name),"Founder identified"),
                                      (c.email_verified,"Founder email verified")]:
                        color = "#00D69A" if ok else "#505E6E"
                        mark  = "✓" if ok else "✗"
                        st.markdown(f"<span style='color:{color};font-weight:700'>{mark}</span> {label}", unsafe_allow_html=True)
                    for label, url in [("Primary",c.source_url),("Funding",c.funding_source),("Tech",c.tech_source),
                                       ("HQ",c.us_presence_source),("Founder",c.founder_source),
                                       ("Email",c.email_source),("GitHub",c.github_url)]:
                        if url: st.markdown(f"**{label}:** [{url}]({url})")
        else:
            st.markdown("<div style='text-align:center;padding:60px;color:rgba(255,255,255,.35)'><div style='font-size:48px'>🔍</div><div style='margin-top:12px'>No qualified leads yet — run the pipeline above</div></div>", unsafe_allow_html=True)

    with tab_r:
        if run.rejected_leads:
            rej = pd.DataFrame([{"Company":c.company_name,"Rejection Reason":c.rejection_reason or "—",
                                  "Fund":"✅" if c.funding_verified else "✗","Tech":"✅" if c.tech_verified else "✗",
                                  "HQ":"✅" if c.us_presence_verified else "✗","Founder":"✅" if c.founder_name else "✗",
                                  "Email":"✅" if c.email_verified else "✗"} for c in run.rejected_leads])
            st.dataframe(rej, use_container_width=True, hide_index=True)
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            st.download_button("⬇  Download CSV", _csv(run.rejected_leads), "tvb-rejected.csv", "text/csv")
        else:
            st.markdown("<div style='text-align:center;padding:40px;color:rgba(255,255,255,.3)'>No rejected candidates</div>", unsafe_allow_html=True)

    with tab_a:
        st.code("\n".join(run.activity) if run.activity else "No activity yet.", language=None)

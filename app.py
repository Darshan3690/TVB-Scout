"""Streamlit entry point for TVB Scout."""

from __future__ import annotations

import json
import os
from io import StringIO

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from agent.orchestrator import ScoutOrchestrator, ScoutRun

load_dotenv()

st.set_page_config(page_title="TVB Scout", page_icon="TS", layout="wide")


def records_for_table(companies: list) -> pd.DataFrame:
    columns = [
        "Company",
        "Industry",
        "Funding/Revenue",
        "US Presence",
        "Founder",
        "Verified Email",
        "Discovery",
        "Source",
    ]
    rows = []
    for company in companies:
        rows.append(
            {
                "Company": company.company_name,
                "Industry": company.industry,
                "Funding/Revenue": company.funding_or_revenue,
                "US Presence": company.us_presence,
                "Founder": f"{company.founder_name} ({company.founder_role})".strip(),
                "Verified Email": company.founder_email,
                "Discovery": " + ".join(sorted({item.get("type", "") for item in company.discovery_sources})),
                "Source": company.source_url,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def csv_for(companies: list) -> str:
    fields = [
        "company_name", "description", "industry", "website", "funding_or_revenue", "funding_usd",
        "us_presence", "founder_name", "founder_role", "founder_email", "github_url", "github_stars",
        "open_source", "yc_backed", "discovery_sources", "source_url",
    ]
    rows = []
    for company in companies:
        row = company.to_dict()
        row["discovery_sources"] = json.dumps(row["discovery_sources"])
        rows.append({field: row.get(field, "") for field in fields})
    return pd.DataFrame(rows, columns=fields).to_csv(index=False)


def render_detail(company) -> None:
    with st.expander(company.company_name):
        st.write(company.description or "No public description was retained.")
        st.markdown("**Why qualified**")
        st.write("Funding verified" if company.funding_verified else "Funding not verified")
        st.write("Technology platform verified" if company.tech_verified else "Technology platform not verified")
        st.write("Minimal/no significant US presence verified" if company.us_presence_verified else "US presence not verified")
        st.write("CEO/co-founder identified" if company.founder_name else "CEO/co-founder not identified")
        st.write("Founder email verified" if company.email_verified else "Founder email not verified")
        for label, url in (
            ("Primary source", company.source_url),
            ("Funding source", company.funding_source),
            ("Technology source", company.tech_source),
            ("US-presence source", company.us_presence_source),
            ("Founder source", company.founder_source),
            ("Email source", company.email_source),
            ("GitHub", company.github_url),
        ):
            if url:
                st.markdown(f"{label}: [{url}]({url})")


st.title("TVB SCOUT")
st.caption("Autonomous Company Discovery & Verification Agent")
st.write("Find companies matching TVB's target profile through web and open-source discovery followed by independent, evidence-first validation.")

target = st.number_input("Target leads", min_value=1, max_value=50, value=15, step=1)
if st.button("Run TVB Scout", type="primary", use_container_width=True):
    activity_box = st.empty()
    live_messages: list[str] = []

    def on_event(message: str) -> None:
        live_messages.append(message)
        activity_box.code("\n".join(live_messages[-30:]), language=None)

    with st.spinner("Discovering and verifying companies from public sources..."):
        result = ScoutOrchestrator(event_callback=on_event).run(target_leads=int(target))
    st.session_state["tvb_run"] = result

run: ScoutRun | None = st.session_state.get("tvb_run")
if run:
    metrics = st.columns(5)
    metrics[0].metric("Web candidates", run.web_candidates)
    metrics[1].metric("GitHub candidates", run.github_candidates)
    metrics[2].metric("Unique companies", run.unique_companies)
    metrics[3].metric("Qualified", len(run.qualified_leads))
    metrics[4].metric("Rejected", len(run.rejected_leads))

    qualified_tab, rejected_tab, activity_tab = st.tabs([f"Qualified ({len(run.qualified_leads)})", f"Rejected ({len(run.rejected_leads)})", "Activity"])
    with qualified_tab:
        st.dataframe(records_for_table(run.qualified_leads), use_container_width=True, hide_index=True)
        st.download_button("Download Qualified Leads CSV", csv_for(run.qualified_leads), "tvb-scout-qualified-leads.csv", "text/csv")
        for company in run.qualified_leads:
            render_detail(company)
    with rejected_tab:
        rejected_rows = pd.DataFrame([{"Company": item.company_name, "Rejection Reason": item.rejection_reason} for item in run.rejected_leads])
        st.dataframe(rejected_rows, use_container_width=True, hide_index=True)
        st.download_button("Download Rejected Candidates CSV", csv_for(run.rejected_leads), "tvb-scout-rejected-candidates.csv", "text/csv")
    with activity_tab:
        st.code("\n".join(run.activity), language=None)


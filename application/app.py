import streamlit as st
import requests
import os
from dotenv import load_dotenv
import os

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_PAT_TOKEN")
REPO = "childrens-bti/internal-ticket-tracker"  # Replace with your target repo

# Form UI
st.title("Harmonization Request Form")

st.markdown("""
Use this form to submit a harmonization request for benchmarked and publicly available workflows.
For downstream analysis, please use the Analysis Request form.
""")

cohort_name = st.text_input("Cohort Name")
manifest = st.text_area("Manifest (can be pasted or referenced)")
billing_group = st.text_input("Billing Group")

# Workflow checkboxes
st.markdown("### Select Harmonization Workflow(s)")
workflow_options = [
    "Kids First RNA-Seq workflow (alignment + expression + fusions + splicing)",
    "Kids First WGS or WXS T/N workflow (alignment + SNV/InDel/CNV/SV variant calls + annotation)",
    "Kids First WGS or WXS T only workflow (alignment + SNV/InDel/CNV/SV variant calls + annotation)",
    "Kids First Germline Joint Genotyping workflow (specify family or other cohort + annotation)",
    "Kids First Targeted Panel T/N workflow (alignment + SNV/InDel variant calls + annotation)",
    "Kids First Targeted Panel T only workflow (alignment + SNV/InDel variant calls + annotation)",
    "Pathogenicity Preprocessing (ClinVar, INTERVAR, AutoPVS1 annotation)",
    "AutoGVP (Automated Germline Variant Pathogenicity)",
    "AlleleCouNT (tumor allele counts for germline variant calls)",
    "Custom Workflow (specify below)"
]

selected_workflows = [w for w in workflow_options if st.checkbox(w)]

additional_info = st.text_area("Additional Information")

# Submit button
if st.button("Submit Harmonization Request"):
    if not GITHUB_TOKEN:
        st.error("GitHub token not found. Please set GITHUB_TOKEN as an environment variable.")
    elif not (cohort_name and billing_group and selected_workflows):
        st.warning("Please fill out all required fields.")
    else:
        issue_title = f"[Harmonization]: {cohort_name}"
        issue_body = f"""## Harmonization Request

- **Cohort Name**: {cohort_name}
- **Manifest**: {manifest}
- **Billing Group**: {billing_group}

**Selected Workflow(s)**:
{chr(10).join(['- ' + w for w in selected_workflows])}

**Additional Information**:
{additional_info}
"""

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        data = {
            "title": issue_title,
            "body": issue_body,
            "labels": ["harmonization-request"]
        }

        response = requests.post(
            f"https://api.github.com/repos/{REPO}/issues",
            headers=headers,
            json=data
        )

        if response.status_code == 201:
            st.success("✅ GitHub issue created successfully!")
            issue_url = response.json().get("html_url", "")
            if issue_url:
                st.markdown(f"[View issue on GitHub]({issue_url})")
        else:
            st.error(f"❌ Failed to create issue: {response.status_code}")
            st.json(response.json())


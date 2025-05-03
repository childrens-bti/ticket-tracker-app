import streamlit as st
import time
import jwt
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

REPO = "childrens-bti/internal-ticket-tracker"

# Load secrets from Streamlit Cloud
app_id = st.secrets["GITHUB_APP_ID"]
installation_id = st.secrets["GITHUB_INSTALLATION_ID"]
private_key_str = st.secrets["GITHUB_PRIVATE_KEY"]

# Load the private key
try:
    private_key = serialization.load_pem_private_key(
        private_key_str.encode(),
        password=None,
        backend=default_backend()
    )
    st.success("✅ Private key loaded successfully")
except Exception as e:
    st.error(f"❌ Failed to load private key: {e}")
    st.stop()

# Create JWT
def create_jwt(app_id, private_key):
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": app_id
    }
    jwt_token = jwt.encode(payload, private_key, algorithm="RS256")
    return jwt_token

# Get installation access token
def get_installation_token(jwt_token, installation_id):
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json"
    }
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    response = requests.post(url, headers=headers)
    st.write("🔧 Installation Token Status:", response.status_code)
    st.write("🔧 Token response JSON:", response.text)
    return response.json().get("token")

# UI
st.title("Harmonization Request Form")

st.markdown("""
Use this form to submit a harmonization request for benchmarked and publicly available workflows.
For downstream analysis, please use the Analysis Request form.
""")

cohort_name = st.text_input("Cohort Name")
manifest = st.text_area("Link to manifest")
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

# Submit
if st.button("Submit Harmonization Request"):
    if not (cohort_name and billing_group and selected_workflows):
        st.warning("Please fill out all required fields.")
    else:
        st.write("🔐 Creating JWT...")
        jwt_token = create_jwt(app_id, private_key)
        st.success("✅ JWT created")

        st.write("🔑 Requesting installation access token...")
        access_token = get_installation_token(jwt_token, installation_id)
        if not access_token:
            st.error("❌ Failed to retrieve GitHub installation access token.")
            st.stop()

        st.success("✅ Access token retrieved")
        st.write("🔐 Access Token (first 10 chars):", access_token[:10], "...")

        # Prepare issue
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
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github+json"
        }
        data = {
            "title": issue_title,
            "body": issue_body,
            "labels": ["harmonization-request"]
        }

        st.write("🚀 Sending issue to GitHub...")
        response = requests.post(
            f"https://api.github.com/repos/{REPO}/issues",
            headers=headers,
            json=data
        )

        st.write("📬 GitHub Issue Response:", response.status_code)
        st.write("📬 Response JSON:", response.text)

        if response.status_code == 201:
            issue_url = response.json()["html_url"]
            st.success("✅ GitHub issue created successfully!")
            st.markdown(f"[View on GitHub]({issue_url})")
        else:
            st.error(f"❌ Failed to create issue: {response.status_code}")
            st.json(response.json())

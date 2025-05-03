import streamlit as st
import requests
import yaml
import time
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# GitHub repo details
REPO = "childrens-bti/internal-ticket-tracker"

# Secrets from Streamlit Cloud
app_id = st.secrets["GITHUB_APP_ID"]
installation_id = st.secrets["GITHUB_INSTALLATION_ID"]
private_key_str = st.secrets["GITHUB_PRIVATE_KEY"]

# Load private key
private_key = serialization.load_pem_private_key(
    private_key_str.encode(),
    password=None,
    backend=default_backend()
)

# Create JWT
def create_jwt(app_id, private_key):
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": app_id
    }
    return jwt.encode(payload, private_key, algorithm="RS256")

# Get installation access token
def get_installation_token(jwt_token, installation_id):
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json"
    }
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    response = requests.post(url, headers=headers)
    return response.json().get("token")

# Load issue template YAML via GitHub API
def load_template(issue_type, access_token):
    path = f".github/ISSUE_TEMPLATE/{issue_type}.yml"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"

    headers = {
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github.v3.raw"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        try:
            return yaml.safe_load(response.text)
        except yaml.YAMLError as e:
            st.error(f"❌ YAML parsing error in `{issue_type}.yml`:\n\n{str(e)}")
            return None
    else:
        st.error(f"❌ Failed to load template: {issue_type} ({response.status_code})")
        return None

# Build form based on issue template
def render_form(template):
    inputs = {}
    st.markdown(template["body"][0]["attributes"]["value"])

    for block in template["body"]:
        if block["type"] == "textarea":
            label = block["attributes"]["label"]
            required = block.get("validations", {}).get("required", False)
            value = st.text_area(label, placeholder=block["attributes"].get("placeholder", ""))
            if required and not value:
                st.warning(f"'{label}' is required.")
            inputs[block["id"]] = value

        elif block["type"] == "checkboxes":
            label = block["attributes"]["label"]
            options = block["attributes"].get("options", [])
            selected = [opt["label"] for opt in options if st.checkbox(opt["label"])]
            if block.get("validations", {}).get("required", False) and not selected:
                st.warning(f"Please select at least one option for '{label}'")
            inputs[block["id"]] = selected

    return inputs

# Submit GitHub issue
def submit_issue(title, body, labels, project_ids, access_token):
    headers = {
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github+json"
    }

    data = {
        "title": title,
        "body": body,
        "labels": labels,
        "project_ids": [int(p.split("/")[-1]) for p in project_ids]
    }

    response = requests.post(
        f"https://api.github.com/repos/{REPO}/issues",
        headers=headers,
        json=data
    )

    return response

# Main UI
st.title("BTI Bioinformatics Ticket Form")
issue_type = st.selectbox("Select Issue Type", ["access_request", "transfer", "harmonization", "analysis"], format_func=lambda x: {
    "access_request": "Access Request",
    "analysis": "Scientific Analysis",
    "harmonization": "Data Harmonization",
    "transfer": "Data Download or Data Transfer"
}.get(x, x.capitalize()))")
        else:
            st.error(f"❌ Failed to create issue: {response.status_code}")
            st.json(response.json())

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
    private_key_str.encode(), password=None, backend=default_backend()
)


# Create JWT for GitHub App authentication
def create_jwt(app_id, private_key):
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + (10 * 60), "iss": app_id}
    return jwt.encode(payload, private_key, algorithm="RS256")


# Exchange JWT for installation access token
def get_installation_token(jwt_token, installation_id):
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
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
        "Accept": "application/vnd.github.v3.raw",
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


# Render Streamlit form dynamically from the issue template
def render_form(template):
    inputs = {}

    # Required submitter fields
    st.markdown("### Submitter Information")
    submitter_name = st.text_input("Submitter Name *", help="Your full name")
    lab = st.text_input("Lab *", help="Lab or team submitting this request")
    title = st.text_input(
        "Ticket Title *", help="Short, descriptive title for your request"
    )

    if not submitter_name:
        st.warning("Submitter Name is required.")
    if not lab:
        st.warning("Lab is required.")
    if not title:
        st.warning("Ticket Title is required.")

    inputs["submitter_name"] = submitter_name
    inputs["lab"] = lab
    inputs["ticket_title"] = title

    st.markdown("---")

    # Render template-defined form fields
    for block in template.get("body", []):
        block_type = block.get("type")
        attrs = block.get("attributes", {})
        label = attrs.get("label", "Field")
        placeholder = attrs.get("placeholder", "")
        description = attrs.get("description", "")
        required = block.get("validations", {}).get("required", False)
        display_label = f"{label} *" if required else label

        if block_type == "markdown":
            st.markdown(attrs.get("value", ""))

        elif block_type == "textarea":
            if description:
                st.caption(description)
            value = st.text_area(display_label, placeholder=placeholder)
            if required and not value:
                st.warning(f"{label} is required.")
            inputs[block.get("id", label)] = value

        elif block_type == "input":
            if description:
                st.caption(description)
            value = st.text_input(display_label, placeholder=placeholder)
            if required and not value:
                st.warning(f"{label} is required.")
            inputs[block.get("id", label)] = value

        elif block_type == "dropdown":
            options = attrs.get("options", [])
            if description:
                st.caption(description)
            default = attrs.get("default", 0)
            if options:
                choice = st.selectbox(
                    display_label,
                    options,
                    index=default if default < len(options) else 0,
                )
                inputs[block.get("id", label)] = choice

        elif block_type == "checkboxes":
            options = attrs.get("options", [])
            if description:
                st.caption(description)
            selected = [opt["label"] for opt in options if st.checkbox(opt["label"])]
            if required and not selected:
                st.warning(f"Please select at least one option for '{label}'")
            inputs[block.get("id", label)] = selected
            # Store original options so we can re-render with [x]/[ ] later
            inputs[f"{block.get('id', label)}_all_options"] = options

        else:
            st.info(f"ℹ️ Unsupported field type '{block_type}' will be skipped.")

    return inputs


# Submit a GitHub issue to the repo and optionally add to project
def submit_issue(title, body, labels, project_ids, access_token):
    headers = {
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github+json",
    }
    data = {
        "title": title,
        "body": body,
        "labels": labels,
        "project_ids": [int(p.split("/")[-1]) for p in project_ids],
    }
    return requests.post(
        f"https://api.github.com/repos/{REPO}/issues", headers=headers, json=data
    )


# Main Streamlit App UI
st.title("BTI Bioinformatics Ticket Form")

issue_type = st.selectbox(
    "Select Issue Type",
    ["access_request", "transfer", "harmonization", "analysis"],
    format_func=lambda x: {
        "access_request": "Access Request",
        "analysis": "Scientific Analysis",
        "harmonization": "Data Harmonization",
        "transfer": "Data Download or Data Transfer",
    }.get(x, x.capitalize()),
)

# Authenticate via GitHub App
jwt_token = create_jwt(app_id, private_key)
access_token = get_installation_token(jwt_token, installation_id)
template = load_template(issue_type, access_token)

if template:
    inputs = render_form(template)

    if st.button("Submit Issue"):
        # Construct body with checkboxes rendered properly
        updated_body_lines = [
            f"**Submitter Name**: {inputs.get('submitter_name')}",
            f"**Lab**: {inputs.get('lab')}",
            "",
        ]

        for block in template.get("body", []):
            block_id = block.get("id")
            block_type = block.get("type")
            label = block.get("attributes", {}).get("label", block_id)
            value = inputs.get(block_id)

            if not block_id or value is None:
                continue

            updated_body_lines.append(f"### {label}")
            if block_type == "checkboxes":
                options = [
                    opt["label"]
                    for opt in block.get("attributes", {}).get("options", [])
                ]
                for option in options:
                    checked = "[x]" if option in value else "[ ]"
                    updated_body_lines.append(f"- {checked} {option}")
            else:
                updated_body_lines.append(str(value))

        # Final body string
        body = "\n".join(updated_body_lines)

        # Title with prefix from template and user-defined title
        title = (
            template.get("title", "[Ticket]")
            + f" {inputs.get('ticket_title', '')[:70]}"
        )

        # Label and project association
        labels = [issue_type]
        project_ids = template.get("projects", [])
        response = submit_issue(title, body, labels, project_ids, access_token)

        # Feedback
        if response.status_code == 201:
            issue_url = response.json().get("html_url", "")
            st.success("✅ GitHub issue created successfully!")
            st.markdown(f"[View issue on GitHub]({issue_url})")
        else:
            st.error(f"❌ Failed to create issue: {response.status_code}")
            st.json(response.json())

st.markdown("---")
st.caption(
    "🛠️ If you encounter a bug or have questions about this form, please email Dr. Jo Lynne Rokita."
)

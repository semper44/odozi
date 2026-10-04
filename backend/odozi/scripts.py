# manual_trigger.py
import os
import sys
import django
import hmac
import hashlib
import json
import requests

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)
print(sys.path)
print("")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "odozi.settings")
django.setup()

from django.conf import settings

SECRET = settings.GITHUB_APP_CLIENT_SECRET  


# =========================================================================

# =========================================================================
# Update this URL to target my new refactored application routing path prefix!
URL = "http://127.0.0.1:8000/account/github_push/"

# =========================================================================

# =========================================================================
# Replace these strings with my real project paths to test cloning later!
REPO_OWNER = "semper44"
REPO_NAME = "Taskmaster-"
COMMIT_SHA = "638575a3990a2191e930"
INSTALLATION_ID = 134080274         # Mock numeric GitHub App installation identity
BRANCH = "master"

mock_payload_dict = {
    "ref": f"refs/heads/{BRANCH}",
    "after": COMMIT_SHA, # Maps to data.get("after") inside my view
    "installation": {
        "id": INSTALLATION_ID # Maps to data.get("installation", {}).get("id")
    },
    "repository": {
        # my view uses clone_url during cloning, or strips it for names
        "name": REPO_NAME,
        "clone_url": f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git",
        "default_branch": "main",
        "owner": {
            "login": REPO_OWNER
        }
    }
}

# Convert the Python dictionary into a hard string to lock down character hashes
payload_json_string = json.dumps(mock_payload_dict)

# =========================================================================

# =========================================================================
computed_hash = hmac.new(
    SECRET.encode('utf-8'),
    msg=payload_json_string.encode('utf-8'),
    digestmod=hashlib.sha256
).hexdigest()

signature_header_value = f"sha256={computed_hash}"

# =========================================================================

# =========================================================================
headers = {
    "X-GitHub-Event": "push",                 # Tells my code this is a push block event
    "X-Hub-Signature-256": signature_header_value, # Passes the request security wall
    "Content-Type": "application/json"
}

print(f"Sending mock GitHub payload to {URL}...")
response = requests.post(URL, data=payload_json_string, headers=headers)

print(f"\n[SERVER RESPONSE STATUS]: {response.status_code}")
print(f"[SERVER RESPONSE BODY]: {response.text}")

# manual_trigger.py
import requests
import json
import hmac
import hashlib

# 1. Your configuration
URL = "http://127.0.0.1:8000/webhook/"
SECRET = "your_test_secret"  # Must match your settings.py
REPO_URL = "https://github.com/semper44/odozi.git" # Use a real repo for cloning
BRANCH = "main"

# 2. Build the GitHub-style payload
payload = json.dumps({
    "ref": f"refs/heads/{BRANCH}",
    "repository": {
        "clone_url": REPO_URL
    }
})

# 3. Sign the payload (to pass verify_github_signature)
signature = "sha256=" + hmac.new(
    SECRET.encode('utf-8'),
    msg=payload.encode('utf-8'),
    digestmod=hashlib.sha256
).hexdigest()

# 4. Send the request
headers = {
    "X-GitHub-Event": "push",
    "X-Hub-Signature-256": signature,
    "Content-Type": "application/json"
}

response = requests.post(URL, data=payload, headers=headers)
print(f"Status: {response.status_code} - {response.text}")

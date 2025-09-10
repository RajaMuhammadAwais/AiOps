import os
import subprocess
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("GITHUB_REPOSITORY")  # e.g. user/repo

TARGET_EXTS = [".py", ".js", ".java", ".php"]

SECURITY_PROMPT = """
You are a security auditor. Analyze the following source code and identify
vulnerabilities (SQLi, XSS, secrets, weak crypto, auth flaws, etc.).
Respond in a short structured format:

- Vulnerability:
- Risk Level (Low/Medium/High):
- Recommendation:
"""

def create_issue(title, body):
    """Create a GitHub issue using gh CLI."""
    cmd = [
        "gh", "issue", "create",
        "--repo", REPO,
        "--title", title,
        "--body", body
    ]
    subprocess.run(cmd, check=False)

def scan_file(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        code = f.read()

    response = openai.chat.completions.create(
        model="gpt-5",   # adjust as needed
        messages=[
            {"role": "system", "content": "You are a senior application security engineer."},
            {"role": "user", "content": f"{SECURITY_PROMPT}\n\n{code}"}
        ],
        temperature=0
    )

    findings = response.choices[0].message.content.strip()
    print(f"\n🔍 Findings in {file_path}:\n{findings}\n")

    if "Vulnerability:" in findings:
        # Auto-create GitHub issue
        create_issue(
            f"Security issue in {file_path}",
            f"**File:** {file_path}\n\n**Findings:**\n{findings}"
        )

def main():
    for root, _, files in os.walk("."):
        for file in files:
            if any(file.endswith(ext) for ext in TARGET_EXTS):
                scan_file(os.path.join(root, file))

if __name__ == "__main__":
    main()

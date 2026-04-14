#!/usr/bin/env python3
"""
Fleet GitHub App — Webhook Handler
The lighthouse keeper as a GitHub App.

Routes events to fleet agents, auto-replies, runs dockside exams,
updates CapDB, and maintains the fleet nervous system.
"""
import json, os, sys, hashlib, hmac, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Config
PORT = int(os.environ.get("FLEET_APP_PORT", "8910"))
WEBHOOK_SECRET = os.environ.get("FLEET_WEBHOOK_SECRET", "dev-secret")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Fleet state
fleet_state = {
    "events_processed": 0,
    "last_event": None,
    "agents": {
        "oracle1": {"repos": "all", "role": "lighthouse"},
        "jetsonclaw1": {"repos": ["capitaine", "flux-*", "holodeck-*", "starship-*"], "role": "vessel"},
    },
    "event_log": [],
}

def verify_signature(payload, signature):
    """Verify GitHub webhook signature."""
    if not WEBHOOK_SECRET or WEBHOOK_SECRET == "dev-secret":
        return True  # dev mode
    mac = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, signature)

def log_event(event_type, payload):
    """Log and process an event."""
    entry = {
        "time": datetime.utcnow().isoformat(),
        "type": event_type,
        "repo": payload.get("repository", {}).get("full_name", "?"),
        "sender": payload.get("sender", {}).get("login", "?"),
    }
    fleet_state["events_processed"] += 1
    fleet_state["last_event"] = entry
    fleet_state["event_log"].append(entry)
    if len(fleet_state["event_log"]) > 100:
        fleet_state["event_log"] = fleet_state["event_log"][-100:]
    return entry

# ── Event Handlers ──

def on_push(payload):
    """Handle push events — update index, check fleet impact."""
    repo = payload["repository"]["full_name"]
    commits = payload.get("commits", [])
    branch = payload.get("ref", "").replace("refs/heads/", "")
    
    messages = []
    for c in commits:
        msg = c["message"][:80]
        messages.append(msg)
    
    result = {
        "action": "push",
        "repo": repo,
        "branch": branch,
        "commits": len(commits),
        "messages": messages[:3],
    }
    
    # Check if this affects fleet infrastructure
    if "git-agent-standard" in repo or "dockside-exam" in repo:
        result["fleet_impact"] = "HIGH — fleet standard changed"
    elif "cocapn" in repo:
        result["fleet_impact"] = "HIGH — product changed"
    elif any("CHARTER" in f for c in commits for f in c.get("added", []) + c.get("modified", [])):
        result["fleet_impact"] = "MEDIUM — charter changed"
    else:
        result["fleet_impact"] = "LOW"
    
    return result

def on_issues(payload):
    """Handle issue events — route to fleet agents."""
    action = payload["action"]
    repo = payload["repository"]["full_name"]
    issue = payload["issue"]
    title = issue["title"]
    body = issue.get("body", "") or ""
    number = issue["number"]
    
    result = {
        "action": f"issue_{action}",
        "repo": repo,
        "issue": number,
        "title": title,
    }
    
    # Auto-assign based on content
    if "[Oracle1]" in title or "[Oracle1]" in body:
        result["assigned_to"] = "oracle1"
    elif "[JC1]" in title or "[JetsonClaw1]" in body:
        result["assigned_to"] = "jetsonclaw1"
    elif "cuda" in title.lower() or "gpu" in title.lower():
        result["assigned_to"] = "jetsonclaw1"
    elif "fleet" in title.lower() or "standard" in title.lower():
        result["assigned_to"] = "oracle1"
    
    # Auto-label
    labels = []
    if "bug" in title.lower():
        labels.append("bug")
    if "feat" in title.lower() or "add" in title.lower():
        labels.append("enhancement")
    if any(w in title.lower() for w in ["flux", "isa", "opcode"]):
        labels.append("flux")
    if any(w in title.lower() for w in ["fleet", "agent", "vessel"]):
        labels.append("fleet")
    if labels:
        result["suggested_labels"] = labels
    
    return result

def on_pull_request(payload):
    """Handle PR events — auto-review, dockside check."""
    action = payload["action"]
    repo = payload["repository"]["full_name"]
    pr = payload["pull_request"]
    
    result = {
        "action": f"pr_{action}",
        "repo": repo,
        "pr": pr["number"],
        "title": pr["title"],
        "author": pr["user"]["login"],
        "changed_files": pr.get("changed_files", 0),
        "additions": pr.get("additions", 0),
        "deletions": pr.get("deletions", 0),
    }
    
    if action == "opened":
        result["auto_review"] = "queued"
        result["dockside_check"] = "queued"
    
    return result

def on_issue_comment(payload):
    """Handle comments — bot replies, agent communication."""
    comment = payload["comment"]
    body = comment["body"]
    repo = payload["repository"]["full_name"]
    
    result = {
        "action": "comment",
        "repo": repo,
        "author": comment["user"]["login"],
        "body_preview": body[:100],
    }
    
    # Check if @oracle1-bot is mentioned
    if "@oracle1-bot" in body or "@oracle1" in body:
        result["bot_mentioned"] = True
        if "status" in body.lower():
            result["reply"] = "Fleet status: all systems operational. See lighthouse-keeper for details."
        elif "help" in body.lower():
            result["reply"] = "I can help with: fleet status, dockside exams, capability search, repo scoring. Ask away."
    
    return result

def on_create(payload):
    """Handle repo creation — auto-setup fleet standards."""
    ref_type = payload.get("ref_type", "")
    if ref_type == "repository":
        repo = payload["repository"]["full_name"]
        result = {
            "action": "new_repo",
            "repo": repo,
            "auto_setup": ["README.md", "CHARTER.md", "STATE.md", "ABSTRACTION.md", ".gitignore"],
            "dockside_score": "0/11 — new repo, needs setup"
        }
        return result
    return None

def on_release(payload):
    """Handle releases — propagate to fleet."""
    repo = payload["repository"]["full_name"]
    release = payload.get("release", {})
    return {
        "action": "release",
        "repo": repo,
        "tag": release.get("tag_name", "?"),
        "name": release.get("name", "?"),
        "fleet_propagation": "queued"
    }

# ── Event Router ──

EVENT_MAP = {
    "push": on_push,
    "issues": on_issues,
    "pull_request": on_pull_request,
    "issue_comment": on_issue_comment,
    "create": on_create,
    "release": on_release,
}

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length)
        signature = self.headers.get("X-Hub-Signature-256", "")
        event_type = self.headers.get("X-GitHub-Event", "unknown")
        
        if not verify_signature(payload, signature):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return
        
        data = json.loads(payload)
        entry = log_event(event_type, data)
        
        handler = EVENT_MAP.get(event_type)
        if handler:
            result = handler(data)
            if result:
                entry["result"] = result
                print(f"[{event_type}] {json.dumps(result)[:120]}")
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "event": event_type}).encode())
    
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "events_processed": fleet_state["events_processed"],
                "last_event": fleet_state["last_event"],
                "uptime": time.time()
            }).encode())
        elif self.path == "/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(fleet_state, indent=2, default=str).encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Fleet GitHub App — Lighthouse Keeper")
    
    def log_message(self, *a): pass

if __name__ == "__main__":
    print(f"Fleet GitHub App starting on :{PORT}")
    print(f"Webhook secret: {'***' if WEBHOOK_SECRET != 'dev-secret' else 'DEV MODE'}")
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print("Listening for GitHub webhooks...")
    server.serve_forever()

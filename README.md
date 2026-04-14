# Fleet GitHub App

> The Lighthouse Keeper as a GitHub App.

## What It Does

- **Webhook Handler** — listens for GitHub events across the org
- **Bot Identity** — `@oracle1-bot` comments, labels, assigns
- **Auto-Labeling** — classifies issues using Groq (24ms)
- **Dockside Auto-Check** — scores repos on PRs
- **Event Router** — routes events to the right fleet agent

## Events Handled

| Event | Handler | Action |
|-------|---------|--------|
| push | on_push | Update index, check fleet impact |
| issues | on_issues | Auto-label, auto-assign, welcome comment |
| pull_request | on_pull_request | Auto-review queue, dockside check |
| issue_comment | on_issue_comment | Bot replies when @mentioned |
| create | on_create | Auto-setup fleet standards on new repos |
| release | on_release | Propagate to fleet installations |

## Setup

1. Create GitHub App at https://github.com/settings/apps
2. Set webhook URL to your server:8910
3. Set webhook secret
4. Install on SuperInstance org
5. Run `bash start.sh`

## Architecture

```
GitHub Event → Webhook (:8910) → Event Router → Handler
                                              ├─ on_push → index update
                                              ├─ on_issues → auto-label + comment
                                              ├─ on_pull_request → dockside check
                                              └─ on_comment → bot reply
```

## Fleet Integration

- **Keeper (:8900)** — fleet monitoring
- **Agent API (:8901)** — agent-to-agent communication
- **Holodeck (:7778)** — spatial fleet UI
- **Fleet App (:8910)** — GitHub nervous system

The four pillars of the Cocapn fleet infrastructure.

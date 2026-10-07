# Email Production Flow — CrewAI

Part 3/3 of a small CrewAI portfolio series, each one adding more of the
framework's core concepts on top of the same email-assistant idea.

| # | Repo | What it adds |
|---|------|--------------|
| 1 | [crewai-portfolio-01-email-triage-agent](https://github.com/YanivBohbot/crewai-portfolio-01-email-triage-agent) | Single Agent, MCP tool calling, structured output |
| 2 | [crewai-portfolio-02-email-rag-crew](https://github.com/YanivBohbot/crewai-portfolio-02-email-rag-crew) | Crew, Knowledge (RAG), Memory, Guardrails |
| 3 | **crewai-portfolio-03-email-production-flow** (this repo) | Full Flow, multi-MCP, human-in-the-loop, persistence |

## What this does

The full production-shaped version: a multi-step `Flow` that triages an
inbox, conditionally checks a calendar for a meeting slot, drafts a reply
through the RAG+Memory+Guardrail crew from repo 2, and — critically — never
finalizes anything without a human approving it first.

```
@start() triage_inbox          Agent + MCP Gmail (mock)
        │
@router() route_by_category    "needs_meeting" or "simple_reply"?
        │                              │
  needs_meeting                  simple_reply
        │                              │
@listen propose_slot            @listen skip_meeting
  Agent + MCP Calendar (mock,          │
  second MCP server), tentative        │
  hold only — never a real booking     │
        └──────────────┬───────────────┘
                        │  or_(...)
              @listen + @human_feedback
                   draft_reply
          Crew(policy_analyst → drafter)
                        │
            ┌───────────┴───────────┐
      @listen("approved")    @listen("rejected")
```

`@persist()` wraps the whole Flow class, checkpointing state to SQLite after
every step — a crash mid-run resumes instead of restarting from scratch.

## CrewAI concepts used

- **Flow** — Pydantic state, `@start`, `@router`, `@listen`, `or_()`
- **Multi-MCP orchestration** — two independent MCP servers (Gmail, Calendar)
  used by two different Agents in the same Flow
- **Human-in-the-loop** — `@human_feedback(emit=["approved", "rejected"], ...)`
  pauses execution for a real approval before anything is considered final
- **Persistence** — `@persist()`, SQLite-backed, resumable via
  `kickoff(restore_from_state_id=...)`
- **Crew + Process.sequential** — reused from repo 2 (policy analyst → drafter)
- **Knowledge (RAG)**, **Memory**, **Guardrails**, **structured output** —
  same as repo 2
- **Tool calling via MCP** — both Gmail and Calendar tools are read-only or
  tentative-only; nothing in this codebase can send an email or book a real
  meeting

## Tech stack

- [crewai](https://docs.crewai.com) 1.15.x
- Python 3.10–3.13, [uv](https://docs.astral.sh/uv/)
- [mcp](https://modelcontextprotocol.io) (`FastMCP`) for both mock servers
- OpenAI (`openai/gpt-4.1-mini` + `text-embedding-3-small`)

## Project structure

```
src/email_production_flow/
├── main.py                              # Flow: full pipeline above
├── mcp_servers/
│   ├── gmail_mock_server.py             # list_recent_emails, get_email
│   └── calendar_mock_server.py          # list_free_slots, hold_slot (tentative)
└── crews/email_crew/
    ├── config/agents.yaml
    ├── config/tasks.yaml
    └── email_crew.py                    # Knowledge, Memory, Guardrail
```

## Setup & run

```bash
crewai install            # or: uv sync
```

Add your key to `.env`:

```
OPENAI_API_KEY=sk-...
MODEL=openai/gpt-4.1-mini
```

Run:

```bash
uv run kickoff
# or
crewai run
```

The run will **pause mid-execution** waiting for human input (`approved` /
`rejected`) before finalizing the draft — that's the human-in-the-loop gate
working as intended, not a bug.

## Notes

- Every "action" tool in this codebase is read-only or explicitly tentative
  (`hold_slot` never books a real event) — approval never actually triggers a
  real send or booking, by design, so the whole pipeline is safe to run
  repeatedly against the mock data.
- `crewai traces enable` is the fastest way to inspect what each agent
  decided and which MCP tools it called, instead of adding `print()`s.

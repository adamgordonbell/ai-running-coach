# AI Running Coach

Example code from the talk *I Built an AI Running Coach* (PyTexas 2026).

Not a chatbot — a system that consumes data you're already producing.
Your data + LLM + feedback loop. Two triggers. One Lambda. ~$1/month.

```
6am every day      → EventBridge → Lambda → GPT-4o → Slack
After every run    → Strava webhook → Lambda → GPT-4o → Slack
Coach notices something → save_observation() → S3 → every future prompt
```

## Architecture

```
EventBridge (6am) ──┐
                     ├──► Lambda ──► context.py  (DynamoDB: recent runs + MVW progress)
Strava webhook   ──┘         │
                             ├──► llm.py      (prompts/ + S3 context + save_observation tool)
                             └──► slack.py    (post message)
```

## Start here: `app/llm.py`

Three things:
1. Load three markdown files — coach voice, training plan, athlete context (from S3)
2. Call GPT-4o with one tool: `save_observation(text)`
3. If the model calls the tool, append the observation to S3 and loop

That S3 append is the entire memory mechanism.

## Setup

You need: a Strava app, OpenAI key, Slack bot, and an AWS account.
Copy `.env.example` to `.env` for local dev. For deployment, set secrets via Pulumi:

```bash
cd infra && uv sync
pulumi config set --secret openaiApiKey   sk-...
pulumi config set --secret slackBotToken  xoxb-...
# (see .env.example for the full list)
```

Then:
```bash
just deploy   # build zip + pulumi up
just seed     # upload prompts/athlete_context.md to S3
just invoke-cron     # test the morning check-in
just invoke-webhook  # test post-run review
just destroy         # tear down when done
```

## Simplifications vs. the real system

- **Memory:** production uses chat → DynamoDB journals → weekly summarizer → S3. This demo collapses to one tool call for clarity.
- **No fitness metrics:** real system computes CTL/ATL training load, availability %, and durability from Strava HR streams and injects them into every prompt. This demo omits that module.
- **No zone calculation:** real system computes HR zones from Strava streams. This demo uses avg HR only.
- **Strava webhook auth:** Strava provides no request signing — both systems rely on the GET handshake only.

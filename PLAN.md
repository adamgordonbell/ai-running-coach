# AI Running Coach Example — Plan

**Status:** Vague plan. Scaffold here, then check `~/sandbox/momentum/` for real details we're missing as we build.

## Why

Public, followable demo to share at AI running coach talks (PyTexas Apr 18, SCaLE 23x, potentially DevOpsCon/MLCon). Currently the talks reference code that isn't shared — the real `momentum` repo is too complex and entangled with personal credentials/data. This is the minimal 20% that makes the talk's thesis legible in code.

Thesis the example has to carry:
- Event-driven AI, not a ChatGPT wrapper
- Memory without RAG — a markdown file in S3 + one tool call
- Everything in Python — app and infra
- Scale-to-zero, ~$1/month
- Prompt is the product

## Target: ~/sandbox/ai-running-coach (public GitHub)

Not under `~/para/projects/` — this is code that gets pushed to GitHub. Plan lives here, code lives in sandbox.

## Scope

### In (must map to specific slides)

| Concept | Slide | Repo artifact |
|---|---|---|
| Vague Plan pseudocode | Slide 6 | `app/handler.py` with `morning_checkin()` + `post_run_review()` |
| Pulumi infra snippets | Slides 7-9 | `infra/__main__.py` — Lambda, FunctionURL, EventBridge, DynamoDB, S3 |
| "What the Coach Sees" | Slide 22 | Markdown context builder in `app/context.py` |
| Training Plan in prompt | Slide 23 | `prompts/training_plan.md` |
| Memory Without RAG | Slide 32 | S3 `athlete_context.md` + `save_observation` tool |
| Function Calling as Intent | Slide 47 | One tool: `save_observation(text)` |

### Out (keep as talk-only)

- **Peloton Auth0 hack** — labeled "hack" in the deck itself; not followable
- **Columnar streams + source_ranges** — orthogonal to the memory thesis
- **Lambda self-invoke for Slack 3-sec limit** — appendix slide; document in README as "the real one does X"
- **Five-tool intent classifier** — just `save_observation` for v1
- **Multi-phase macrocycle logic** — training plan is static markdown in the demo
- **DynamoDB measurements table** — keep only activities table
- **Efficiency factor, core EF, GAP, stream-computed metrics** — activity record has distance/time/HR/zones only
- **Horizon (life coach)** — separate system; not in scope
- **YAML prompt templates** — plain markdown files instead (more readable for followers)

## Repo shape

```
ai-running-coach/
├── README.md              # Walkthrough tied to talk narrative
├── infra/
│   ├── __main__.py        # Pulumi: Lambda, FunctionURL, EventBridge, S3, DynamoDB
│   ├── Pulumi.yaml
│   └── pyproject.toml
├── app/
│   ├── handler.py         # morning_checkin + post_run_review entrypoints
│   ├── context.py         # builds markdown summary for LLM
│   ├── strava.py          # minimal Strava client (OAuth refresh + get activity)
│   ├── llm.py             # OpenAI call + save_observation tool
│   ├── slack.py           # post message
│   └── pyproject.toml     # uv-managed
├── prompts/
│   ├── coach_voice.md     # principles + examples (cf. slide "The Actual Prompt")
│   ├── training_plan.md   # phase, race goal, MVW (cf. slide 23)
│   └── athlete_context.md # seed file — synced to S3 on first run
└── justfile               # deploy, invoke-local, tail-logs
```

## Decisions

- **Seed `athlete_context.md`:** Sanitized real Adam data from `source-material/real-dynamic-context.md` (pulled from live S3). 73 lines, five sections (Body Signals, Motivators, Constraints, Discoveries, Prep). Sanitization pass: redact weight numbers, BP readings, specific medication name. Keep: Malcolm, Bon Echo, movie picks, ankle/hip observations, training concepts, gear preferences.
- **Strava:** Build it. Real OAuth refresh + `GET /activities/{id}`. Webhook endpoint has GET handshake only — no per-request verification on POSTs (Strava provides no signing mechanism; their own docs recommend plain curl for testing). We manually POST canned payloads to the FunctionURL to exercise `post_run_review`.
- **Memory loop (chose option A):** Single Lambda. Cron prompt includes `save_observation` as a tool; LLM calls it when it spots something worth remembering, writes directly to S3 `athlete_context.md`. Matches slide narrative: "function call captured it, the context window remembered it." This is a simplification of momentum's real architecture (which uses chat → DynamoDB journals → weekly-summarizer Lambda → S3). README calls out the simplification with a pointer to the two-stage version for production use.
- **Deploy target:** Either account. Deploy once to confirm end-to-end works, then `pulumi destroy`. Not left running; live demos continue to use real momentum.
- **Testing path:** Manual invocation. CLI `just invoke-cron` triggers the cron path. CLI `just invoke-webhook` POSTs a canned Strava payload to the FunctionURL. Good enough to prove the loop without Strava actually firing the webhook.
- **License:** MIT.

## The pedagogical star: LLM harness

This is the part that rewards reading. Make it the cleanest code in the repo:

- `app/llm.py` — prompt assembly (load three markdown files, join with headers), OpenAI call, tool registration, tool dispatch. This is the file that shows up in screenshots / gets pointed to from slides.
- `prompts/coach_voice.md` — principles + examples from slide "The Actual Prompt" (lines 676-703 of text.md). Plain markdown, no YAML templating.
- The `save_observation` tool definition — schema, handler that appends to S3. One function, ~15 lines.

Everything else (Strava client, Slack post, webhook verification, Strava→activity-record conversion) is boilerplate that the reader should be able to skim. Worth doing cleanly but not the point. The Strava→activity conversion is structurally interesting (shape mapping) but not LLM-interesting — keep it in its own file, short, well-named.

## Security (this repo is public)

- **No committed secrets, ever.** Strava client ID/secret/refresh token, OpenAI key, Slack token — all in Pulumi config as secrets (`config.require_secret`), never in code.
- `.gitignore`: `Pulumi.*.yaml` only if they contain plaintext (use `pulumi config set --secret` so they're encrypted), `.env`, `.env.*`, `*.pem`, `__pycache__`, `.venv`, `uv.lock` kept (it's fine to commit).
- Local dev: `.env.example` with blank values + instructions. Real `.env` git-ignored.
- Pre-commit hook (optional): `detect-secrets` or `gitleaks` run via lefthook.
- README explicit setup section: "You'll need your own Strava app, OpenAI key, Slack bot. Here's how."
- Pulumi stack file review before first commit — encrypted passphrase, no plaintext secrets in state file history.

## Open questions

None blocking. Decide later:
- Do we strip Slack for v1 and just `print` the coach's response? Makes the setup one less integration for readers. Counter: Slack is in every slide, so dropping it breaks the slide→repo mapping. Keep Slack.

## Premortem findings (resolved)

- **#1 Thin context:** refuted. Real 73-line context pulled to `source-material/`; plenty of material after sanitization.
- **#2 Cron tool-calling dead loop:** confirmed, resolved via option A above. Real momentum is two-stage async (chat→DDB→weekly→S3); we collapse to single-stage (cron with tools→S3) to match slide narrative.
- **#4 Webhook auth:** confirmed low-severity. Handshake only, no per-request verification needed; canned POSTs faithfully represent real traffic.
- **#3 LOC estimate, #5 cold start, #6 scope creep, #7 purpose ambiguity:** not investigated — design choices / judgment calls, resolved in conversation.

## Next steps

1. ✅ Scaffold repo with the shape above (`.gitignore`, all files)
2. ✅ Sanitize + write `prompts/athlete_context.md`
3. ✅ Write `prompts/coach_voice.md` and `prompts/training_plan.md`
4. ✅ Write `app/llm.py` — the star file
5. ✅ Write `infra/__main__.py` — stripped Pulumi infra
6. ✅ Write `app/handler.py`, `app/context.py`
7. ✅ Write `app/strava.py`, `app/slack.py`
8. ✅ Justfile: `invoke-cron`, `invoke-webhook`, `deploy`, `destroy`, `tail-logs`, `seed`
9. ✅ Deploy + morning check-in confirmed working (Slack message lands)
10. ~~README walkthrough~~ ✅ Done
11. Test webhook path (`just invoke-webhook`) with a real Strava activity ID
12. Secret scan, then push to GitHub
13. `pulumi destroy`, leave repo referenced from slides

## Reference

- Real system: `~/sandbox/momentum/` — check when fidelity matters
- Real prompts: `~/sandbox/momentum/goapp/internal/llm/coach_prompts.yaml` (YAML — we'll flatten to markdown)
- Real context backup (life coach, mostly not useful): `~/sandbox/momentum/scratch/context_backup.md`
- Talk deck: `~/para/projects/pytexas/slides.iapresenter/text.md`
- Talk approach: `~/para/projects/pytexas/approach.md`

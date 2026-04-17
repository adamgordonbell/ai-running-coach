import json
import os
import boto3
from openai import OpenAI

BUCKET = os.environ["CONTEXT_BUCKET"]
CONTEXT_KEY = "athlete_context.md"
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")

SAVE_OBSERVATION_TOOL = {
    "type": "function",
    "function": {
        "name": "save_observation",
        "description": "Save a durable observation about the athlete to long-term memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The observation to save."}
            },
            "required": ["text"],
        },
    },
}


def _load_system_prompt() -> str:
    s3 = boto3.client("s3")
    coach_voice = open(f"{PROMPTS_DIR}/coach_voice.md").read()
    training_plan = open(f"{PROMPTS_DIR}/training_plan.md").read()
    athlete_context = s3.get_object(Bucket=BUCKET, Key=CONTEXT_KEY)["Body"].read().decode()

    return "\n\n---\n\n".join([
        f"# Coach Voice\n{coach_voice}",
        f"# Training Plan\n{training_plan}",
        f"# Athlete Context\n{athlete_context}",
    ])


def _save_observation(text: str) -> None:
    s3 = boto3.client("s3")
    # Append to the live context file — this is the entire "memory without RAG" mechanism
    existing = s3.get_object(Bucket=BUCKET, Key=CONTEXT_KEY)["Body"].read().decode()
    s3.put_object(
        Bucket=BUCKET,
        Key=CONTEXT_KEY,
        Body=(existing.rstrip() + f"\n- {text}\n").encode(),
    )


def chat(activity_context: str) -> str:
    client = OpenAI()
    messages = [
        {"role": "system", "content": _load_system_prompt()},
        {"role": "user", "content": activity_context},
    ]

    while True:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=[SAVE_OBSERVATION_TOOL],
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append(msg)
            for call in msg.tool_calls:
                args = json.loads(call.function.arguments)
                _save_observation(args["text"])
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": "Saved.",
                })
        else:
            return msg.content

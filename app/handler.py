import json
import os
import boto3
from datetime import datetime, timezone, timedelta

from . import context, llm, slack, strava

ATHLETE_ID = os.environ["ATHLETE_ID"]
SLACK_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL = os.environ["SLACK_CHANNEL_ID"]
STRAVA_CLIENT_ID = os.environ["STRAVA_CLIENT_ID"]
STRAVA_CLIENT_SECRET = os.environ["STRAVA_CLIENT_SECRET"]
STRAVA_REFRESH_TOKEN = os.environ["STRAVA_REFRESH_TOKEN"]
TABLE = os.environ["ACTIVITIES_TABLE"]


def morning_checkin(event, ctx):
    today = datetime.now(timezone(timedelta(hours=-5))).strftime("%A, %B %d")  # ET
    prompt = f"Today is {today}. Write Adam's morning check-in.\n\n{context.build_context()}"
    message = llm.chat(prompt)
    slack.post_message(SLACK_TOKEN, SLACK_CHANNEL, message)
    return {"status": "ok"}


def post_run_review(event, ctx):
    body = event.get("body", "{}")
    if isinstance(body, str):
        body = json.loads(body)

    # Strava webhook GET verification handshake
    params = event.get("queryStringParameters") or {}
    if params.get("hub.challenge"):
        return {
            "statusCode": 200,
            "body": json.dumps({"hub.challenge": params["hub.challenge"]}),
        }

    # Only process new activity creations
    if body.get("object_type") != "activity" or body.get("aspect_type") != "create":
        return {"statusCode": 200, "body": "ignored"}

    activity_id = body["object_id"]
    access_token = strava.refresh_access_token(
        STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN
    )
    activity = strava.get_activity(access_token, activity_id)

    db = boto3.resource("dynamodb")
    db.Table(TABLE).put_item(Item={
        "athlete_id": ATHLETE_ID,
        "start_date": activity["start_date"],
        "activity_id": activity["id"],
        "name": activity["name"],
        "type": activity["type"],
        "distance_km": str(activity["distance_km"]),
        "duration_min": activity["duration_min"],
        "avg_hr": str(activity["avg_hr"]) if activity.get("avg_hr") else None,
    })

    hr_note = f", avg HR {activity['avg_hr']} bpm" if activity.get("avg_hr") else ""
    prompt = (
        f"Adam just completed: {activity['name']} — "
        f"{activity['distance_km']} km, {activity['duration_min']} min{hr_note}. "
        f"Write his post-run coaching message now.\n\n"
        f"{context.build_context(activity)}"
    )
    message = llm.chat(prompt)
    slack.post_message(SLACK_TOKEN, SLACK_CHANNEL, message)
    return {"statusCode": 200, "body": "ok"}


def lambda_handler(event, ctx):
    if event.get("source") == "aws.scheduler":
        return morning_checkin(event, ctx)
    return post_run_review(event, ctx)

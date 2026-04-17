import os
from datetime import datetime, timezone, timedelta
import boto3
from boto3.dynamodb.conditions import Key

TABLE = os.environ["ACTIVITIES_TABLE"]
ATHLETE_ID = os.environ["ATHLETE_ID"]


def _get_recent_activities(weeks: int = 3) -> list[dict]:
    db = boto3.resource("dynamodb")
    table = db.Table(TABLE)
    cutoff = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = table.query(
        KeyConditionExpression=Key("athlete_id").eq(ATHLETE_ID) & Key("start_date").gte(cutoff),
        ScanIndexForward=False,
    )
    return result.get("Items", [])


def _week_trend(activities: list[dict]) -> str:
    now = datetime.now(timezone.utc)
    this_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    last_week_start = this_week_start - timedelta(weeks=1)

    def total_min(start, end):
        return sum(
            int(a.get("duration_min", 0))
            for a in activities
            if start.strftime("%Y-%m-%dT%H:%M:%SZ") <= str(a.get("start_date", "")) < end.strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    this_week = total_min(this_week_start, now)
    last_week = total_min(last_week_start, this_week_start)

    if last_week == 0:
        return f"Week trend: {this_week} min this week (no data last week)"
    delta = this_week - last_week
    direction = "up" if delta > 10 else "down" if delta < -10 else "flat"
    return f"Week trend: {direction} ({this_week} min this week vs {last_week} min last week)"


def _mvw_progress(activities: list[dict]) -> str:
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    week_start_str = week_start.strftime("%Y-%m-%dT%H:%M:%SZ")

    this_week = [a for a in activities if str(a.get("start_date", "")) >= week_start_str]
    runs = [a for a in this_week if str(a.get("type", "")) == "Run"]
    long_run_done = any(int(a.get("duration_min", 0)) >= 80 for a in runs)
    z2_runs = [a for a in runs if int(a.get("duration_min", 0)) < 80]
    strength_done = any(str(a.get("type", "")) in ("WeightTraining", "Workout") for a in this_week)

    def marks(done, target):
        return "✓" * min(done, target) + "○" * max(0, target - done)

    return (
        f"MVW this week: runs {marks(len(z2_runs), 3)} | "
        f"long run {'✓' if long_run_done else '○'} | "
        f"strength {'✓' if strength_done else '○'}"
    )


def build_context(activity: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    recent = _get_recent_activities()
    lines = []

    lines.append(f"Today: {now.strftime('%A, %B %d')}")
    lines.append(_mvw_progress(recent))
    lines.append(_week_trend(recent))

    if activity:
        lines.append("")
        lines.append("## This Run")
        lines.append(f"- {activity['name']} ({activity['type']})")
        lines.append(f"- Distance: {activity['distance_km']} km, Duration: {activity['duration_min']} min")
        if activity.get("avg_hr"):
            lines.append(f"- Avg HR: {activity['avg_hr']} bpm")

    if recent:
        lines.append("")
        lines.append("## Recent Activity (Last 3 Weeks)")
        for a in recent:
            if activity and str(a.get("activity_id")) == str(activity.get("id")):
                continue
            date = str(a.get("start_date", ""))[:10]
            hr = f", {a['avg_hr']} bpm" if a.get("avg_hr") else ""
            lines.append(f"- {date}: {a.get('name', 'Activity')} — {a.get('distance_km', '?')} km, {a.get('duration_min', '?')} min{hr}")

    return "\n".join(lines)

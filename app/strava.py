import httpx


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    response = httpx.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def get_activity(access_token: str, activity_id: int) -> dict:
    response = httpx.get(
        f"https://www.strava.com/api/v3/activities/{activity_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    raw = response.json()
    return {
        "id": raw["id"],
        "name": raw["name"],
        "type": raw["type"],
        "distance_km": round(raw["distance"] / 1000, 2),
        "duration_min": round(raw["moving_time"] / 60),
        "avg_hr": raw.get("average_heartrate"),
        "start_date": raw["start_date_local"],
    }

import json
import os
import urllib.request
from datetime import datetime, timezone

import boto3

s3 = boto3.client("s3")

# In your real project these endpoints come from a Snowflake table.
# Here we keep a small list to stay simple.
CITIES = [
    {"city": "London", "lat": 51.5072, "lon": -0.1276},
    {"city": "New York", "lat": 40.7128, "lon": -74.0060},
    {"city": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    {"city": "Hyderabad", "lat": 17.3850, "lon": 78.4867},
]


def lambda_handler(event, context):
    bucket = os.environ["BUCKET"]
    env = os.environ.get("ENV", "dev")
    now = datetime.now(timezone.utc)

    lines = []
    for c in CITIES:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={c['lat']}&longitude={c['lon']}&current_weather=true"
        )
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.load(resp)
        cw = data["current_weather"]
        lines.append(json.dumps({
            "city": c["city"],
            "latitude": c["lat"],
            "longitude": c["lon"],
            "temperature": cw["temperature"],
            "windspeed": cw["windspeed"],
            "fetched_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        }))

    # one JSON record per line (newline-delimited JSON)
    key = f"{env}/weather/{now:%Y/%m/%d}/weather_{now:%H%M%S}.json"
    s3.put_object(Bucket=bucket, Key=key, Body="\n".join(lines).encode("utf-8"))
    return {"status": "ok", "file": f"s3://{bucket}/{key}", "records": len(lines)}

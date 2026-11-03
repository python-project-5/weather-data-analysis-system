from datetime import date, timedelta
import sqlite3
import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
DB_PATH = "weather.db"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS weather_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city TEXT NOT NULL,
                country TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                observation_date TEXT NOT NULL,
                temperature_max REAL,
                temperature_min REAL,
                temperature_mean REAL,
                precipitation REAL,
                humidity_mean REAL,
                wind_speed_max REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(city, observation_date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city TEXT NOT NULL,
                searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def get_json(url, params):
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def geocode_city(city):
    data = get_json(GEOCODING_URL, {
        "name": city, "count": 1, "language": "en", "format": "json"
    })
    results = data.get("results") or []
    if not results:
        raise ValueError(f"Could not find the city '{city}'. Check the spelling.")
    place = results[0]
    return {
        "name": place["name"],
        "country": place.get("country", ""),
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "timezone": place.get("timezone", "auto")
    }


def fetch_weather(place, start_date, end_date):
    # Use the archive endpoint for completed dates and forecast endpoint for recent/future dates.
    today = date.today()
    end = date.fromisoformat(end_date)
    start = date.fromisoformat(start_date)
    if start > end:
        raise ValueError("Start date must be on or before end date.")
    if end > today + timedelta(days=16):
        raise ValueError("Choose an end date no more than 16 days in the future.")
    if start < today - timedelta(days=5):
        url = ARCHIVE_URL
        # Historical archive data can have a short publication delay.
        effective_end = min(end, today - timedelta(days=6))
        if start > effective_end:
            url = FORECAST_URL
            params = {
                "latitude": place["latitude"], "longitude": place["longitude"],
                "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max",
                "hourly": "relative_humidity_2m",
                "start_date": start_date, "end_date": end_date,
                "timezone": "auto"
            }
            return get_json(url, params)
        params = {
            "latitude": place["latitude"], "longitude": place["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max",
            "hourly": "relative_humidity_2m",
            "start_date": start_date, "end_date": effective_end.isoformat(),
            "timezone": "auto"
        }
        return get_json(url, params)
    params = {
        "latitude": place["latitude"], "longitude": place["longitude"],
        "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max",
        "hourly": "relative_humidity_2m",
        "start_date": start_date, "end_date": end_date,
        "timezone": "auto"
    }
    return get_json(FORECAST_URL, params)


def mean_daily_humidity(hourly):
    times = hourly.get("time", [])
    values = hourly.get("relative_humidity_2m", [])
    result = {}
    for timestamp, value in zip(times, values):
        if value is None:
            continue
        day = timestamp[:10]
        result.setdefault(day, []).append(value)
    return {day: sum(vals) / len(vals) for day, vals in result.items()}


def save_records(place, weather):
    daily = weather.get("daily", {})
    humidity_by_day = mean_daily_humidity(weather.get("hourly", {}))
    fields = daily.get("time", [])
    rows = []
    for i, day in enumerate(fields):
        def val(key):
            values = daily.get(key, [])
            return values[i] if i < len(values) else None
        rows.append((
            place["name"], place["country"], place["latitude"], place["longitude"], day,
            val("temperature_2m_max"), val("temperature_2m_min"),
            val("temperature_2m_mean"), val("precipitation_sum"),
            humidity_by_day.get(day), val("wind_speed_10m_max")
        ))
    with get_db() as conn:
        conn.executemany("""
            INSERT INTO weather_records
            (city, country, latitude, longitude, observation_date, temperature_max,
             temperature_min, temperature_mean, precipitation, humidity_mean, wind_speed_max)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(city, observation_date) DO UPDATE SET
              country=excluded.country, latitude=excluded.latitude, longitude=excluded.longitude,
              temperature_max=excluded.temperature_max, temperature_min=excluded.temperature_min,
              temperature_mean=excluded.temperature_mean, precipitation=excluded.precipitation,
              humidity_mean=excluded.humidity_mean, wind_speed_max=excluded.wind_speed_max
        """, rows)
        conn.execute("INSERT INTO searches(city) VALUES (?)", (place["name"],))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze")
def analyze():
    city = request.args.get("city", "").strip()
    start_date = request.args.get("start", "").strip()
    end_date = request.args.get("end", "").strip()
    if not city:
        return jsonify(error="Please enter a city name."), 400
    if not start_date or not end_date:
        return jsonify(error="Please select a start date and end date."), 400
    try:
        date.fromisoformat(start_date)
        date.fromisoformat(end_date)
        place = geocode_city(city)
        weather = fetch_weather(place, start_date, end_date)
        save_records(place, weather)
        daily = weather.get("daily", {})
        days = daily.get("time", [])
        humidity = mean_daily_humidity(weather.get("hourly", {}))
        records = []
        for i, day in enumerate(days):
            def val(key):
                values = daily.get(key, [])
                return values[i] if i < len(values) else None
            records.append({
                "date": day,
                "temperature_max": val("temperature_2m_max"),
                "temperature_min": val("temperature_2m_min"),
                "temperature_mean": val("temperature_2m_mean"),
                "precipitation": val("precipitation_sum"),
                "humidity_mean": round(humidity[day], 1) if day in humidity else None,
                "wind_speed_max": val("wind_speed_10m_max")
            })
        valid_temps = [r["temperature_mean"] for r in records if r["temperature_mean"] is not None]
        valid_rain = [r["precipitation"] for r in records if r["precipitation"] is not None]
        valid_humidity = [r["humidity_mean"] for r in records if r["humidity_mean"] is not None]
        summary = {
            "days": len(records),
            "average_temperature": round(sum(valid_temps) / len(valid_temps), 1) if valid_temps else None,
            "highest_temperature": max((r["temperature_max"] for r in records if r["temperature_max"] is not None), default=None),
            "lowest_temperature": min((r["temperature_min"] for r in records if r["temperature_min"] is not None), default=None),
            "total_precipitation": round(sum(valid_rain), 1) if valid_rain else None,
            "average_humidity": round(sum(valid_humidity) / len(valid_humidity), 1) if valid_humidity else None
        }
        return jsonify(place=place, summary=summary, records=records,
                       units={"temperature": "°C", "precipitation": "mm", "humidity": "%", "wind": "km/h"},
                       source="Open-Meteo")
    except (ValueError, requests.RequestException) as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        app.logger.exception("Unexpected analysis error")
        return jsonify(error="Unexpected server error. Check the terminal for details."), 500


@app.route("/api/history")
def history():
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify(records=[])
    with get_db() as conn:
        rows = conn.execute("""
            SELECT observation_date, temperature_max, temperature_min, temperature_mean,
                   precipitation, humidity_mean, wind_speed_max
            FROM weather_records
            WHERE lower(city)=lower(?)
            ORDER BY observation_date DESC LIMIT 100
        """, (city,)).fetchall()
    return jsonify(records=[dict(row) for row in rows])


@app.route("/api/recent-searches")
def recent_searches():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT city, MAX(searched_at) AS last_searched
            FROM searches GROUP BY lower(city)
            ORDER BY last_searched DESC LIMIT 8
        """).fetchall()
    return jsonify(searches=[dict(row) for row in rows])


init_db()

if __name__ == "__main__":
    app.run(debug=True)

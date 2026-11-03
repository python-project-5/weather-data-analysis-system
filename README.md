# Weather Data Analysis System

A full-stack student project using Python, Flask, SQLite, HTML, CSS, JavaScript and Chart.js. It retrieves weather data from Open-Meteo, calculates summary statistics, stores daily records, and displays charts and a CSV export.

## Features
- Search by city name and choose a date range
- Daily min/mean/max temperature, precipitation, humidity and maximum wind speed
- Summary cards and interactive charts
- SQLite persistence (`weather.db` is created automatically)
- Download displayed daily records as CSV
- Responsive layout for desktop and mobile
- No API key required for the Open-Meteo endpoints used here

## Project structure
```text
weather_data_analysis_system/
├── app.py
├── requirements.txt
├── README.md
├── templates/
│   └── index.html
└── static/
    ├── app.js
    └── style.css
```

## Run locally (Windows)
1. Install Python 3.10 or newer.
2. Extract this ZIP and open a terminal in the `weather_data_analysis_system` folder.
3. Create a virtual environment:
   ```bash
   py -m venv .venv
   .venv\Scripts\activate
   ```
4. Install packages:
   ```bash
   python -m pip install -r requirements.txt
   ```
5. Start the server:
   ```bash
   python app.py
   ```
6. Open `http://127.0.0.1:5000` in your browser.

On macOS/Linux, activate the environment with `source .venv/bin/activate`.

## Database
SQLite creates `weather.db` on the first run. The `weather_records` table stores one record per city and date; repeat searches update the saved record rather than duplicating it. The `searches` table stores search history.

## Data source and limitations
- Geocoding: `https://geocoding-api.open-meteo.com/v1/search`
- Historical weather: `https://archive-api.open-meteo.com/v1/archive`
- Recent and forecast weather: `https://api.open-meteo.com/v1/forecast`
- A working internet connection is required.
- Weather data availability varies by date and location. The archive endpoint may have a publication delay, so ranges spanning the archive boundary may return only the available portion. For a polished production app, split a requested date range across archive and forecast APIs and merge the responses.
- The humidity chart uses the average of hourly humidity readings for each day.
- Chart.js is loaded from a CDN, so charts require internet access.
- This is a learning/demo app. For production, disable Flask debug mode, add validation/rate limits, and review the weather provider's current terms and attribution requirements.

## Framework and technology choices
- **Frontend:** HTML5, CSS3, JavaScript
- **Backend framework:** Flask
- **Database:** SQLite
- **HTTP client:** Requests
- **Charts:** Chart.js
- **Data provider:** Open-Meteo

"""METAR Reader — a Flask web app that translates aviation weather codes.

A METAR is a standardized, machine-readable weather report issued by airports
worldwide. It is precise but cryptic (e.g. ``KJFK 132051Z 20011KT 10SM ...``).
This app fetches a station's latest METAR and rewrites it as a plain-English
report that a non-pilot can understand.

Data source:
    NOAA Aviation Weather API (https://aviationweather.gov) — free, no API key.

Run locally:
    python app.py
    # then open http://127.0.0.1:5000
"""

from flask import Flask, render_template, request
import requests
from metar import Metar

app = Flask(__name__)

#: Base URL of the NOAA endpoint that returns raw METAR text.
METAR_API = "https://aviationweather.gov/api/data/metar"

#: Maps the 16-point compass abbreviations returned by the ``metar`` library
#: (e.g. "SSW") to full words used in the friendly report ("south-southwest").
COMPASS = {
    "N": "north", "NNE": "north-northeast", "NE": "northeast", "ENE": "east-northeast",
    "E": "east", "ESE": "east-southeast", "SE": "southeast", "SSE": "south-southeast",
    "S": "south", "SSW": "south-southwest", "SW": "southwest", "WSW": "west-southwest",
    "W": "west", "WNW": "west-northwest", "NW": "northwest", "NNW": "north-northwest",
}

#: Maps METAR sky-cover codes to their plain-English meaning. Codes that mean
#: "no significant clouds" (SKC/CLR/NSC/NCD) all collapse to "clear skies".
SKY_COVER = {
    "SKC": "clear skies", "CLR": "clear skies", "NSC": "clear skies", "NCD": "clear skies",
    "FEW": "a few clouds", "SCT": "scattered clouds",
    "BKN": "broken clouds", "OVC": "overcast skies", "VV": "an obscured sky",
}


def fetch_metar(station: str) -> str | None:
    """Fetch the latest raw METAR string for an airport.

    Args:
        station: An ICAO airport code (e.g. "KJFK"). Case and surrounding
            whitespace are normalized automatically.

    Returns:
        The raw METAR line as a string, or ``None`` if the station has no
        current report (e.g. an unknown or non-reporting airport).

    Raises:
        requests.RequestException: If the weather service cannot be reached.
    """
    station = station.strip().upper()
    resp = requests.get(
        METAR_API,
        params={"ids": station, "format": "raw"},
        timeout=10,
        headers={"User-Agent": "metar-reader (educational project)"},
    )
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        return None
    # The API may return several lines; the first non-empty one is the latest report.
    return text.splitlines()[0].strip()


def temperature_words(value_f: float) -> str:
    """Describe a temperature in everyday language.

    Args:
        value_f: Temperature in degrees Fahrenheit.

    Returns:
        A single descriptive word such as "cold", "pleasant", or "hot".
    """
    if value_f <= 32:
        return "freezing"
    if value_f <= 50:
        return "cold"
    if value_f <= 68:
        return "cool"
    if value_f <= 80:
        return "pleasant"
    if value_f <= 90:
        return "warm"
    return "hot"


def weather_icon(obs: Metar.Metar) -> str:
    """Choose a single emoji that best represents the current conditions.

    Active precipitation and obscurations take priority over cloud cover, so a
    rainy-but-broken sky shows rain rather than clouds.

    Args:
        obs: A parsed METAR observation.

    Returns:
        A weather emoji (e.g. "☀️", "🌧️", "⛈️").
    """
    # ``present_weather()`` returns a human-readable string like "light rain";
    # it is empty when no significant weather is reported.
    wx = obs.present_weather().lower() if obs.present_weather() else ""
    if "thunder" in wx:
        return "⛈️"
    if any(w in wx for w in ("snow", "sleet", "ice", "hail")):
        return "🌨️"
    if any(w in wx for w in ("rain", "drizzle", "shower")):
        return "🌧️"
    if any(w in wx for w in ("fog", "mist", "haze", "smoke")):
        return "🌫️"

    # No active weather, so fall back to the densest reported cloud layer.
    if obs.sky:
        covers = [cover for cover, _height, _cloud_type in obs.sky]
        if "OVC" in covers or "VV" in covers:
            return "☁️"
        if "BKN" in covers:
            return "🌥️"
        if "SCT" in covers or "FEW" in covers:
            return "⛅"
    return "☀️"


def friendly_report(obs: Metar.Metar) -> list[str]:
    """Convert a parsed METAR into a list of plain-English sentences.

    Each weather element (sky, temperature, wind, visibility, active weather)
    is only described if the report actually contains it, so reports with
    missing fields still produce clean output.

    Args:
        obs: A parsed METAR observation.

    Returns:
        An ordered list of sentences ready to display, one per weather element.
    """
    sentences = []

    # --- Sky / clouds ---
    if obs.sky:
        # Each entry is (cover_code, height, cloud_type); we only need the cover.
        covers = [SKY_COVER.get(cover, cover.lower()) for cover, _height, _cloud in obs.sky]
        # De-duplicate while preserving order (e.g. two "broken clouds" layers).
        seen = []
        for description in covers:
            if description not in seen:
                seen.append(description)
        sentences.append("The sky has " + ", then ".join(seen) + ".")
    else:
        sentences.append("The sky is clear.")

    # --- Temperature (shown in both Fahrenheit and Celsius) ---
    if obs.temp is not None:
        f = round(obs.temp.value("F"))
        c = round(obs.temp.value("C"))
        sentences.append(f"It feels {temperature_words(f)} — about {f}°F ({c}°C).")

    # --- Wind ---
    if obs.wind_speed is not None:
        mph = round(obs.wind_speed.value("MPH"))
        if mph == 0:
            sentences.append("The air is calm with no noticeable wind.")
        else:
            # wind_dir is None when the direction is variable ("VRB" in the code).
            if obs.wind_dir is not None:
                direction = COMPASS.get(obs.wind_dir.compass(), obs.wind_dir.compass())
                where = f"from the {direction}"
            else:
                where = "from shifting directions"
            sentence = f"Wind is blowing {where} at about {mph} mph"
            if obs.wind_gust is not None:
                sentence += f", gusting up to {round(obs.wind_gust.value('MPH'))} mph"
            sentences.append(sentence + ".")

    # --- Visibility ---
    if obs.vis is not None:
        miles = obs.vis.value("MI")
        # 6+ statute miles is the standard threshold for unrestricted visibility.
        if miles >= 6:
            sentences.append("Visibility is good (6+ miles).")
        else:
            sentences.append(f"Visibility is limited to about {round(miles, 1)} miles.")

    # --- Active weather (rain, snow, fog, etc.) ---
    weather = obs.present_weather()
    if weather:
        sentences.append("Current weather: " + weather + ".")

    return sentences


@app.route("/", methods=["GET", "POST"])
def index():
    """Render the home page and, on form submission, the decoded report.

    GET serves the empty search form. POST reads the submitted airport code,
    fetches and decodes its METAR, and re-renders the page with either the
    report or a user-friendly error message.

    Returns:
        The rendered ``index.html`` page as an HTML string.
    """
    # Template variables, defaulted so the page renders fine before any search.
    context = {"station": "", "report": None, "raw": None, "error": None}

    if request.method == "POST":
        station = request.form.get("station", "").strip().upper()
        context["station"] = station

        if not station:
            context["error"] = "Please enter an airport code."
            return render_template("index.html", **context)

        # Network call: a failure here is the service's fault, not the user's.
        try:
            raw = fetch_metar(station)
        except requests.RequestException:
            context["error"] = "Could not reach the weather service. Please try again."
            return render_template("index.html", **context)

        # An empty result almost always means the code was wrong or non-reporting.
        if not raw:
            context["error"] = (
                f"No weather report found for '{station}'. "
                "Use a 4-letter ICAO code like KJFK, EGLL, or OPIS."
            )
            return render_template("index.html", **context)

        context["raw"] = raw

        # Parsing can fail on rare malformed reports; degrade gracefully by
        # still showing the raw text we already fetched.
        try:
            obs = Metar.Metar(raw)
            context["report"] = {
                "name": obs.station_id,
                "time": obs.time.strftime("%H:%M UTC on %d %b %Y") if obs.time else None,
                "sentences": friendly_report(obs),
                "icon": weather_icon(obs),
                "temp_f": round(obs.temp.value("F")) if obs.temp is not None else None,
                "temp_c": round(obs.temp.value("C")) if obs.temp is not None else None,
            }
        except Metar.ParserError:
            context["error"] = "Found a report, but couldn't decode it. Showing the raw text below."

    return render_template("index.html", **context)


if __name__ == "__main__":
    # debug=True enables auto-reload and the interactive debugger for local
    # development only. NEVER deploy with debug enabled — it exposes an
    # arbitrary-code-execution console. For production, run behind a WSGI
    # server such as gunicorn or waitress with debug turned off.
    app.run(debug=True)

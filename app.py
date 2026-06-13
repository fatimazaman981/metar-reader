"""METAR Reader — a Flask web app that fetches a station's raw METAR and
translates the cryptic code into a plain-English weather report.

Data source: NOAA Aviation Weather API (https://aviationweather.gov) — free, no key.
"""

from flask import Flask, render_template, request
import requests
from metar import Metar

app = Flask(__name__)

METAR_API = "https://aviationweather.gov/api/data/metar"

# Full-word names for the 16-point compass abbreviations the metar lib returns.
COMPASS = {
    "N": "north", "NNE": "north-northeast", "NE": "northeast", "ENE": "east-northeast",
    "E": "east", "ESE": "east-southeast", "SE": "southeast", "SSE": "south-southeast",
    "S": "south", "SSW": "south-southwest", "SW": "southwest", "WSW": "west-southwest",
    "W": "west", "WNW": "west-northwest", "NW": "northwest", "NNW": "north-northwest",
}

# Plain-English meaning of each sky-cover code.
SKY_COVER = {
    "SKC": "clear skies", "CLR": "clear skies", "NSC": "clear skies", "NCD": "clear skies",
    "FEW": "a few clouds", "SCT": "scattered clouds",
    "BKN": "broken clouds", "OVC": "overcast skies", "VV": "an obscured sky",
}


def fetch_metar(station):
    """Return the raw METAR string for a station code, or None if there's no report."""
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


def temperature_words(value_f):
    """Turn a Fahrenheit number into a friendly description."""
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


def weather_icon(obs):
    """Pick a single emoji that best represents current conditions."""
    wx = obs.present_weather().lower() if obs.present_weather() else ""
    if "thunder" in wx:
        return "⛈️"
    if any(w in wx for w in ("snow", "sleet", "ice", "hail")):
        return "🌨️"
    if any(w in wx for w in ("rain", "drizzle", "shower")):
        return "🌧️"
    if any(w in wx for w in ("fog", "mist", "haze", "smoke")):
        return "🌫️"
    if obs.sky:
        covers = [cover for cover, _h, _c in obs.sky]
        if "OVC" in covers or "VV" in covers:
            return "☁️"
        if "BKN" in covers:
            return "🌥️"
        if "SCT" in covers or "FEW" in covers:
            return "⛅"
    return "☀️"


def friendly_report(obs):
    """Build a list of plain-English sentences from a parsed Metar observation."""
    sentences = []

    # --- Sky / clouds ---
    if obs.sky:
        covers = []
        for cover, height, _cloud in obs.sky:
            covers.append(SKY_COVER.get(cover, cover.lower()))
        # De-duplicate while keeping order (e.g. two "broken clouds" layers).
        seen = []
        for c in covers:
            if c not in seen:
                seen.append(c)
        sentences.append("The sky has " + ", then ".join(seen) + ".")
    else:
        sentences.append("The sky is clear.")

    # --- Temperature ---
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
    context = {"station": "", "report": None, "raw": None, "error": None}

    if request.method == "POST":
        station = request.form.get("station", "").strip().upper()
        context["station"] = station

        if not station:
            context["error"] = "Please enter an airport code."
            return render_template("index.html", **context)

        try:
            raw = fetch_metar(station)
        except requests.RequestException:
            context["error"] = "Could not reach the weather service. Please try again."
            return render_template("index.html", **context)

        if not raw:
            context["error"] = (
                f"No weather report found for '{station}'. "
                "Use a 4-letter ICAO code like KJFK, EGLL, or OPIS."
            )
            return render_template("index.html", **context)

        context["raw"] = raw
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
    app.run(debug=True)

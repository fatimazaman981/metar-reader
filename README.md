# 🛫 METAR Reader

A Flask web app that turns cryptic aviation weather codes (**METARs**) into a
friendly, plain-English weather report. Type an airport code and get something
anyone can understand — like *"clear skies, pleasant, 75°F, calm air."*

## What is a METAR?

A METAR is a standardized weather report issued by airports around the world.
It's accurate but hard to read, for example:

```
METAR KJFK 132051Z 20011KT 10SM SCT070 SCT250 29/14 A2985
```

This app fetches that raw report and translates it into:

> ⛅ **84°F (29°C)** — KJFK
> - The sky has scattered clouds.
> - It feels warm — about 84°F (29°C).
> - Wind is blowing from the south-southwest at about 13 mph.
> - Visibility is good (6+ miles).

## Features

- 🔎 Look up any airport by its 4-letter **ICAO code** (e.g. `KJFK`, `EGLL`, `OPIS`)
- 🌤️ Weather icon chosen from the actual conditions
- 🌡️ Temperature shown in both °F and °C with a friendly description
- 💨 Wind direction, speed (mph), and gusts in everyday language
- 🔘 Quick-pick buttons for popular airports
- ⏳ Loading spinner while fetching
- 📄 Collapsible view of the original raw METAR code

## Tech stack

- [Flask](https://flask.palletsprojects.com/) — web framework
- [requests](https://requests.readthedocs.io/) — fetches data from the weather API
- [metar](https://pypi.org/project/metar/) — parses the METAR code
- Weather data from the free [NOAA Aviation Weather API](https://aviationweather.gov/)

## Running it locally

You'll need [Python 3](https://www.python.org/downloads/) installed.

```bash
# 1. Clone the repository
git clone https://github.com/fatimazaman981/metar-reader.git
cd metar-reader

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # On Windows
# source venv/bin/activate   # On macOS / Linux

# 3. Install the dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## How it works

1. You enter an airport's ICAO code.
2. The app requests that station's latest METAR from the NOAA Aviation Weather API.
3. The `metar` library parses the raw code into structured data (temperature, wind, sky, etc.).
4. `app.py` turns that data into plain-English sentences and a weather icon.
5. The result is displayed in a clean weather card.

   
<img width="966" height="461" alt="image" src="https://github.com/user-attachments/assets/fe02de34-88b9-4354-a502-e9c4a3b481d3" />
<img width="873" height="888" alt="image" src="https://github.com/user-attachments/assets/f5b6be35-0f09-436b-b33f-c2133d3177f3" />


## License

For educational use.

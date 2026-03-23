<!-- https://claude.ai/chat/ccb76b88-a76e-4d91-9837-acd5019856d9 -->
# 🌍 WORLDVIEW — Global Situational Awareness Platform

A fully self-hosted Docker stack that renders a live, interactive 3D globe with
real-time flight data, satellite tracking, geolocated news, 3D building tiles,
weather overlays, and custom entity management (IP cameras, sensors, assets, etc.)

```
┌─────────────────────────────────────────────────────────────────┐
│                    WORLDVIEW ARCHITECTURE                        │
├─────────────┬───────────────────────────────────────────────────┤
│   Browser   │  CesiumJS 3D Globe (WebGL)                        │
├─────────────┼───────────────────────────────────────────────────┤
│    Nginx    │  Reverse Proxy + Static Serving           :8080   │
├──────┬──────┴──────────┬────────────────────────────────────────┤
│      │  Data Broker    │  FastAPI + WebSocket Hub       :8000   │
│      │  (Aggregator)   │  REST snapshots + pub/sub              │
│      └────────┬────────┴────────────────────────────────────────┤
│               │   Redis Pub/Sub + Entity Cache                  │
│         ┌─────┴──────────────────────────────────┐              │
│         │         Background Workers              │              │
│         │  ✈ flight-tracker   (OpenSky/adsb.fi)  │              │
│         │  🛰 satellite-tracker (CelesTrak/TLE)   │              │
│         │  📡 news-geolocator  (RSS + spaCy NLP)  │              │
│         │  📍 entity-manager  (Custom entities)   │              │
│         └──────────────┬─────────────────────────┘              │
│                        │                                         │
│    Postgres/PostGIS ◄──┘   Tegola (Vector Tiles)                │
│    (Spatial store)         Martin (MVT Tiles)                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✅ What's Included & Free

| Feature | Source | API Key? |
|---------|--------|----------|
| ✈ Live Flights | adsb.fi + OpenSky Network | ❌ No key needed |
| 🛰 Satellite Tracking | CelesTrak TLE + skyfield | ❌ No key needed |
| 📡 Geolocated News | BBC/Reuters/AP/Al Jazeera RSS | ❌ No key needed |
| 🗺 Map Tiles | OpenStreetMap | ❌ No key needed |
| 🏙 3D Buildings | Cesium OSM Buildings | ⚠️ Free Ion token |
| 🌍 3D Terrain | Cesium World Terrain | ⚠️ Free Ion token |
| 🌩 Weather Overlays | OpenWeatherMap tiles | ⚠️ Free API key |
| 📍 Custom Entities | Self-hosted PostGIS | ❌ No key needed |
| 🔷 Vector Tiles | Tegola + PostGIS | ❌ No key needed |
| 🌐 Geocoding | Nominatim (local OSM) | ❌ No key needed |

---

## 🚀 Quick Start

```bash
# 1. Clone and enter directory
git clone <your-repo> worldview && cd worldview

# 2. Copy environment template
cp .env.example .env
# Edit .env to add optional API keys

# 3. Build and start
docker compose up -d --build

# 4. Open browser
open http://localhost:8080
```

The globe will start loading immediately. Live flight and satellite data
begins streaming within 30 seconds of startup.

---

## ⚙️ Configuration

### Optional: Cesium Ion Token (for 3D terrain + buildings)
1. Sign up free at https://cesium.com/ion/signup
2. Copy your token to `.env`: `CESIUM_ION_TOKEN=your_token_here`
3. Restart: `docker compose restart nginx`

### Optional: Weather Overlay
1. Sign up free at https://openweathermap.org/api
2. Copy key to `.env`: `OPENWEATHER_API_KEY=your_key`
3. Restart weather service

### Optional: Local SDR (Software Defined Radio)
For your own ADS-B receiver with much higher local aircraft density:
```bash
# On the host running dump1090:
DUMP1090_HOST=192.168.1.x  # Your SDR host IP
DUMP1090_PORT=30003
```

---

## 📍 Adding Custom Entities

### Via the UI
Click **+ Add Entity** in the bottom-right of the globe. Supported types:
- 📷 **IP Camera** — attach RTSP/HTTP stream URL
- 📡 **IoT Sensor** — environmental monitors, weather stations
- 🚗 **Asset/Vehicle** — tracked equipment or fleet
- 📍 **Point of Interest** — locations, waypoints
- ⚠️ **Alert Zone** — geofences and hazard markers
- ⬡ **Custom** — anything else

### Via REST API
```bash
curl -X POST http://localhost:8080/api/entities \
  -H "Content-Type: application/json" \
  -d '{
    "type": "camera",
    "label": "Front Gate Camera",
    "lat": 51.5074,
    "lon": -0.1278,
    "alt": 10,
    "notes": "rtsp://192.168.1.100:554/stream1"
  }'
```

### Bulk Import (GeoJSON)
```bash
# Import from GeoJSON file via psql
psql postgresql://worldview:worldview@localhost:5433/worldview \
  -c "COPY entities FROM '/path/to/entities.csv' CSV HEADER"
```

---

## 🛰 Satellite Groups

The tracker loads these CelesTrak groups by default:
- **Space Stations** (ISS, Tiangong, etc.)
- **Active Satellites** (~5000 objects)
- **Starlink** constellation
- **OneWeb** constellation
- **Weather** satellites (NOAA, GOES, etc.)
- **Debris** objects

Colour coding on the globe:
- 🟢 Green → Space stations
- 🟣 Purple → Starlink
- ⚪ White → Other active
- 🔵 Blue → Weather sats

---

## 📡 News Geocoding

RSS feeds from BBC World, Reuters, Al Jazeera, AP, DW, France24, Guardian, VOA
are fetched every 5 minutes. spaCy NLP extracts place names from headlines,
which are geocoded via Nominatim (local OSM geocoder if enabled, otherwise
the public Nominatim instance with rate limiting respected).

News pins appear as orange markers on the globe. Click any pin for the headline.
The live feed panel on the right shows the latest geolocated stories.

---

## 🗺 Map Layers

| Layer | Provider | Notes |
|-------|----------|-------|
| Base satellite | Bing / Esri (optional) | Free tier |
| Street map | OpenStreetMap | Always free |
| 3D buildings | Cesium OSM Buildings | Needs Ion token |
| Terrain | Cesium World Terrain | Needs Ion token |
| Weather | OpenWeatherMap | Needs free key |
| Custom vectors | Tegola + PostGIS | Self-hosted |

---

## 🔌 WebSocket API

Connect to `ws://localhost:8080/ws/globe` for real-time updates.

Subscribe to channels:
```json
{"type": "subscribe", "channels": ["flights", "satellites", "news", "entities"]}
```

Message format:
```json
{
  "channel": "flights",
  "data": {
    "type": "flight_update",
    "count": 8432,
    "aircraft": [...],
    "timestamp": "2025-01-01T00:00:00Z"
  }
}
```

---

## 📦 Service Ports (Internal)

| Service | Port | Purpose |
|---------|------|---------|
| nginx | 8080 | Public entry point |
| data-broker | 8000 | FastAPI + WS |
| entity-manager | 8002 | Entity CRUD |
| tile-server | 8085 | Tegola MVT |
| martin | 3000 | PostGIS MVT |
| postgres | 5432 | Spatial DB |
| redis | 6379 | Cache + pub/sub |

---

## 🔧 Scaling & Production

For production deployments:
- Add Traefik for automatic TLS/HTTPS
- Scale `data-broker` horizontally with sticky WebSocket sessions
- Use Redis Cluster for high availability
- Add Prometheus/Grafana for metrics
- Enable PostGIS connection pooling (PgBouncer)
- Set up Nominatim with full planet OSM dump for global geocoding

---

## 📄 License & Data Sources

- **CesiumJS**: Apache 2.0
- **OpenSky Network**: Creative Commons CC BY 4.0
- **CelesTrak TLE Data**: Public domain (US government)
- **OpenStreetMap**: ODbL
- **adsb.fi**: Free tier
- **News RSS**: Various publishers, for personal/research use
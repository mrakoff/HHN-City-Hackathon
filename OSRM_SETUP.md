# OSRM Setup Guide

This guide explains how to set up OSRM (Open Source Routing Machine) for accurate road-based routing in the Route Planning System.

## What is OSRM?

OSRM provides **real road-based routing** instead of straight-line distances. This gives you:
- ✅ Accurate road distances (not "as the crow flies")
- ✅ Realistic travel times based on road speeds
- ✅ Actual route geometry (routes follow real roads)
- ✅ Better route optimization results

## Quick Start (Docker - Recommended)

The easiest way to set up OSRM is using Docker:

### 1. Download OSM Data

Choose a region from [Geofabrik](https://download.geofabrik.de/). For example, for Baden-Württemberg (Germany):

```bash
# Create a directory for OSRM data
mkdir -p osrm-data
cd osrm-data

# Download OSM data (adjust URL for your region)
wget https://download.geofabrik.de/europe/germany/baden-wuerttemberg-latest.osm.pbf
```

**Note:** For other regions, visit https://download.geofabrik.de/ and find your region.

### 2. Process the Data

```bash
# Extract (this may take 10-30 minutes depending on region size)
docker run -t -v $(pwd):/data osrm/osrm-backend \
  osrm-extract -p /opt/car.lua /data/baden-wuerttemberg-latest.osm.pbf

# Partition (for MLD algorithm - faster queries)
docker run -t -v $(pwd):/data osrm/osrm-backend \
  osrm-partition /data/baden-wuerttemberg-latest.osm

# Customize
docker run -t -v $(pwd):/data osrm/osrm-backend \
  osrm-customize /data/baden-wuerttemberg-latest.osm
```

### 3. Start OSRM Server

```bash
docker run -t -i -p 5000:5000 \
  -v $(pwd):/data osrm/osrm-backend \
  osrm-routed --algorithm mld /data/baden-wuerttemberg-latest.osm
```

**Note for macOS users:** If port 5000 is already in use (often by ControlCenter), use port 5001 instead:
```bash
docker run -d -p 5001:5000 \
  -v $(pwd):/data --name osrm-routing osrm/osrm-backend \
  osrm-routed --algorithm mld /data/baden-wuerttemberg-latest.osm
```

Then set `OSRM_BASE_URL=http://localhost:5001` in your `.env` file.

The server will be available at `http://localhost:5000` (or `http://localhost:5001` if using alternative port)

### 4. Test OSRM

Test that OSRM is working:

```bash
# If using default port 5000:
curl "http://localhost:5000/route/v1/driving/9.21,48.78;9.18,48.77?overview=false"

# If using port 5001 (macOS):
curl "http://localhost:5001/route/v1/driving/9.21,48.78;9.18,48.77?overview=false"
```

You should get a JSON response with route data.

### 5. Configure the Application

The application will automatically detect OSRM if it's running on `localhost:5000`.

To use a different OSRM server, set environment variables:

```bash
export OSRM_BASE_URL=http://your-osrm-server:5000
export OSRM_ENABLED=true
```

Or add to `.env` file:

```
OSRM_BASE_URL=http://localhost:5000
OSRM_ENABLED=true
```

## Using Docker Compose (Alternative)

For easier management, you can use the provided `docker-compose.osrm.yml`:

```bash
# First, download and process OSM data (see steps 1-2 above)
# Then start with docker-compose:
docker-compose -f docker-compose.osrm.yml up -d
```

## Fallback Behavior

**Important:** The system works without OSRM! If OSRM is not available, it automatically falls back to:
- Haversine formula for distances (straight-line)
- Estimated travel times based on average speed

This means you can develop and test without OSRM, but for production use, OSRM provides much better accuracy.

## Region Selection

Choose an OSM extract that covers your delivery area:

- **Small city/region**: Use city-level extracts (e.g., `berlin-latest.osm.pbf`)
- **State/province**: Use state-level extracts (e.g., `baden-wuerttemberg-latest.osm.pbf`)
- **Country**: Use country-level extracts (e.g., `germany-latest.osm.pbf`)
- **World**: Use `planet-latest.osm.pbf` (very large, ~60GB+)

**Recommendation:** Start with a region that covers your delivery area. You can always expand later.

## Updating OSM Data

OSM data is updated regularly. To update:

1. Download the latest `.osm.pbf` file
2. Re-run extract, partition, and customize steps
3. Restart the OSRM server

## Troubleshooting

### OSRM server not responding

- Check if the server is running: `curl http://localhost:5000/route/v1/driving/9.21,48.78;9.18,48.77`
- Check Docker logs: `docker ps` to find container, then `docker logs <container-id>`
- Verify port 5000 is not in use: `lsof -i :5000`

### Out of memory during processing

- Use a smaller region extract
- Increase Docker memory limit
- Process on a machine with more RAM

### Routes not found

- Ensure your coordinates are within the OSM extract region
- Check that the OSM data includes roads (not just water/land boundaries)
- Verify coordinates are in correct format (lat, lon)

## Performance

- **Query time**: < 100ms for typical routes
- **Memory usage**: ~500MB - 2GB depending on region size
- **Disk space**: 2-5x the size of the `.osm.pbf` file

## Next Steps

Once OSRM is running:
1. Routes will automatically use OSRM for accurate distances
2. Route optimization will use real road distances
3. Map visualization will show actual road routes (not straight lines)

No code changes needed - the system automatically detects and uses OSRM when available!

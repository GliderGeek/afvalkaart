"""Haal eenmalig de bestaande afvalcontainers op rond de plekken uit de plannen
en schrijf ze naar data/bestaand.geojson. Haalt ook de buurtgrenzen van de
plannen op en schrijft die naar data/gebieden.geojson.

Bronnen: Gemeente Amsterdam, datasets Huishoudelijk afval
(https://api.data.amsterdam.nl/v1/huishoudelijkafval/) en Gebieden
(https://api.data.amsterdam.nl/v1/gebieden/).

Gebruik: uv run scripts/fetch_bestaand.py
Werk daarna de ophaaldatum in README.md bij.
"""
import datetime
import json
import sys
import urllib.request

from common import DATA, afstand_m, geocode_alle, get_json, load_plannen, save_json

WFS_URL = "https://api.data.amsterdam.nl/v1/wfs/huishoudelijkafval/"
API_URL = "https://api.data.amsterdam.nl/v1/huishoudelijkafval/"
GEBIEDEN_URL = "https://api.data.amsterdam.nl/v1/gebieden/buurten/"
MARGE_M = 150


def bbox_met_marge(punten, marge_m):
    lons = [p[0] for p in punten]
    lats = [p[1] for p in punten]
    dlat = marge_m / 110540
    dlon = marge_m / (111320 * 0.61)  # cos(52.4°) ≈ 0.61
    return min(lons) - dlon, min(lats) - dlat, max(lons) + dlon, max(lats) + dlat


def wfs(typename, bbox):
    min_lon, min_lat, max_lon, max_lat = bbox
    return get_json(WFS_URL, {
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
        "TYPENAMES": typename, "outputFormat": "geojson", "count": 10000,
        "srsName": "urn:ogc:def:crs:EPSG::4326",
        # EPSG:4326 in WFS 2.0 heeft de volgorde lat,lon
        "BBOX": f"{min_lat},{min_lon},{max_lat},{max_lon},urn:ogc:def:crs:EPSG::4326",
    })["features"]


def buurt(buurt_id):
    """Buurtgrens in WGS84 uit de dataset Gebieden."""
    req = urllib.request.Request(f"{GEBIEDEN_URL}{buurt_id}/?_format=json",
                                 headers={"Accept-Crs": "EPSG:4326", "User-Agent": "afvalkaart/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def haal_gebieden():
    features = []
    for naam, plan in load_plannen():
        b = buurt(plan["buurt"]["id"])
        features.append({
            "type": "Feature",
            "geometry": b["geometrie"],
            "properties": {"plan": naam, "naam": b["naam"], "code": b["code"], "id": plan["buurt"]["id"]},
        })
        print(f"Buurt {b['code']} {b['naam']}")
    save_json(DATA / "gebieden.geojson", {
        "type": "FeatureCollection",
        "metadata": {"bron": GEBIEDEN_URL, "opgehaald": datetime.date.today().isoformat()},
        "features": features,
    }, indent=None)
    return features


def main():
    gebieden = haal_gebieden()
    punten = list(geocode_alle().values())
    for g in gebieden:
        polys = g["geometry"]["coordinates"] if g["geometry"]["type"] == "MultiPolygon" else [g["geometry"]["coordinates"]]
        punten += [pt for poly in polys for pt in poly[0]]
    bbox = bbox_met_marge(punten, MARGE_M)
    print(f"bbox (lon/lat): {', '.join(f'{v:.5f}' for v in bbox)}")

    clusters = {f["properties"]["id"]: f for f in wfs("cluster", bbox)}
    containers = [f for f in wfs("container", bbox) if f["properties"]["status"] == 1]
    print(f"{len(clusters)} clusters, {len(containers)} actieve containers")

    typen = {}
    for type_id in sorted({c["properties"]["type_id"] for c in containers if c["properties"]["type_id"]}):
        t = get_json(f"{API_URL}containertype/{type_id}/", {"_format": "json"})
        typen[type_id] = t.get("containertypeContainerType")

    features = []
    for c in containers:
        p = c["properties"]
        cluster = clusters.get(p["cluster_id"])
        # Containers van één cluster komen op de clusterpositie, zodat ze op de
        # kaart samen uitwaaieren. Zonder (bekend) cluster: eigen positie.
        geom = cluster["geometry"] if cluster else c["geometry"]
        if cluster and afstand_m(cluster["geometry"]["coordinates"], c["geometry"]["coordinates"]) > 50:
            geom = c["geometry"]
        soort = typen.get(p["type_id"])
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(v, 7) for v in geom["coordinates"]]},
            "properties": {
                "id": p["id_nummer"] or p["id"],
                "cluster": p["cluster_id"],
                "adres": cluster["properties"].get("bronadres") if cluster else None,
                "fractie": p["fractie_omschrijving"],
                "type": {"UNDERGROUND": "OC", "ABOVE_GROUND": "BC", "DUMPSTER": "BC"}.get(soort, soort),
            },
        })
    features.sort(key=lambda f: (f["properties"]["cluster"] or "", f["properties"]["id"]))

    save_json(DATA / "bestaand.geojson", {
        "type": "FeatureCollection",
        "metadata": {
            "bron": API_URL,
            "opgehaald": datetime.date.today().isoformat(),
            "bbox": [round(v, 6) for v in bbox],
        },
        "features": features,
    }, indent=None)

    per_fractie = {}
    for f in features:
        k = (f["properties"]["fractie"], f["properties"]["type"])
        per_fractie[k] = per_fractie.get(k, 0) + 1
    for (fr, ty), n in sorted(per_fractie.items(), key=lambda kv: str(kv[0])):
        print(f"  {fr:<12} {ty or '?':<12} {n}")
    print(f"Geschreven: data/bestaand.geojson ({len(features)} containers)")


if __name__ == "__main__":
    sys.exit(main())

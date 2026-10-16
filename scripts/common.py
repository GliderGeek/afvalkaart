"""Gedeelde helpers voor de build-scripts (alleen Python stdlib)."""
import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PLANNEN = DATA / "plannen"
GEOCACHE = DATA / "geocache.json"

PDOK_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data, indent=1):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
        f.write("\n")


def get_json(url, params=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "afvalkaart/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def load_plannen():
    """Alle plannen uit data/plannen/<plan>.json, gesorteerd op bestandsnaam
    (zonder bijbehorende bestanden zoals <plan>.tekening.json)."""
    return [(p.stem, load_json(p)) for p in sorted(PLANNEN.glob("*.json")) if "." not in p.stem]


def plan_locaties(plan):
    """Alle locaties van een plan als (soort, locatie)-paren."""
    for soort in ("nieuw", "opheffen", "wijzigen"):
        for loc in plan.get(soort, []):
            yield soort, loc


def parse_code(code):
    """'1055CL-27' -> ('1055CL', '27'). Spaties in de postcode worden genegeerd."""
    m = re.fullmatch(r"\s*(\d{4})\s*([A-Z]{2})-(\d+)\s*", code)
    if not m:
        raise ValueError(f"Onbekende locatiecode: {code!r}")
    return m.group(1) + m.group(2), m.group(3)


def normalize_code(code):
    pc, nr = parse_code(code)
    return f"{pc}-{nr}"


def _pdok(q):
    res = get_json(PDOK_URL, {
        "q": q, "fq": "type:adres", "rows": 1,
        "fl": "weergavenaam,straatnaam,huisnummer,postcode,centroide_ll",
    })
    docs = res["response"]["docs"]
    return docs[0] if docs else None


def _point(doc):
    lon, lat = re.match(r"POINT\(([-\d.]+) ([-\d.]+)\)", doc["centroide_ll"]).groups()
    return [round(float(lon), 7), round(float(lat), 7)]


def geocode(adres, code, cache):
    """Geocodeer een plek via PDOK. Eerst op postcode + huisnummer uit de
    locatiecode; als de straatnaam daarvan niet klopt met het adres, op de
    tekst van het adres. Resultaten worden in `cache` bewaard."""
    key = normalize_code(code)
    if key in cache:
        return cache[key]
    pc, nr = parse_code(code)
    straat = re.sub(r"\s+\d+\S*$", "", adres).strip()
    doc = _pdok(f"postcode:{pc} and huisnummer:{nr}")
    methode = "postcode"
    if not doc or doc.get("straatnaam", "").lower() != straat.lower():
        doc2 = _pdok(f"{adres} Amsterdam")
        if doc2 and doc2.get("straatnaam", "").lower() == straat.lower():
            doc, methode = doc2, "adres"
    if not doc:
        raise RuntimeError(f"Niet gevonden bij PDOK: {adres} ({code})")
    cache[key] = {"coord": _point(doc), "gevonden": doc["weergavenaam"], "methode": methode}
    return cache[key]


def geocode_alle():
    """Geocodeer alle plekken uit alle plannen; bewaart de cache. Geeft
    {code: [lon, lat]} terug (het adrespunt, meestal in het gebouw)."""
    cache = load_json(GEOCACHE, {})
    out = {}
    for _, plan in load_plannen():
        for _, loc in plan_locaties(plan):
            out[normalize_code(loc["code"])] = geocode(loc["adres"], loc["code"], cache)["coord"]
    save_json(GEOCACHE, dict(sorted(cache.items())))
    return out


def load_overrides():
    """data/overrides.json: {code: {"coord": [lon, lat], "reden": "..."}}"""
    out = {}
    for code, v in load_json(DATA / "overrides.json", {}).items():
        if code.startswith("_"):
            continue
        out[normalize_code(code)] = v["coord"] if isinstance(v, dict) else v
    return out


def in_polygoon(punt, geometrie):
    """Ligt [lon, lat] binnen een GeoJSON Polygon of MultiPolygon (inclusief gaten)?"""
    def in_ring(ring):
        x, y = punt
        binnen = False
        for i in range(len(ring)):
            x1, y1 = ring[i]
            x2, y2 = ring[i - 1]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                binnen = not binnen
        return binnen

    polygonen = geometrie["coordinates"] if geometrie["type"] == "MultiPolygon" else [geometrie["coordinates"]]
    return any(in_ring(p[0]) and not any(in_ring(gat) for gat in p[1:]) for p in polygonen)


def knip_links(geometrie, lijn):
    """Knip een GeoJSON Polygon/MultiPolygon af op een rechte lijn [[lon, lat], [lon, lat]]
    en houd het deel links van de lijn (gezien van het eerste naar het tweede punt).
    Gaten worden genegeerd; de buurtgrenzen hebben er geen."""
    (ax, ay), (bx, by) = lijn

    def links(p):
        return (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) >= 0

    def snijpunt(p, q):
        d1 = (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)
        d2 = (bx - ax) * (q[1] - ay) - (by - ay) * (q[0] - ax)
        t = d1 / (d1 - d2)
        return [p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])]

    def knip_ring(ring):  # Sutherland-Hodgman met één halfvlak
        uit = []
        for i in range(len(ring) - 1):
            p, q = ring[i], ring[i + 1]
            if links(p):
                uit.append(p)
                if not links(q):
                    uit.append(snijpunt(p, q))
            elif links(q):
                uit.append(snijpunt(p, q))
        return uit + uit[:1] if uit else []

    polygonen = geometrie["coordinates"] if geometrie["type"] == "MultiPolygon" else [geometrie["coordinates"]]
    delen = [[r] for r in (knip_ring(p[0]) for p in polygonen) if len(r) >= 4]
    return {"type": "MultiPolygon", "coordinates": delen}


def afstand_m(a, b):
    """Afstand in meters tussen twee [lon, lat]-punten (benadering, prima op buurtschaal)."""
    dx = (a[0] - b[0]) * 111320 * math.cos(math.radians((a[1] + b[1]) / 2))
    dy = (a[1] - b[1]) * 110540
    return math.hypot(dx, dy)

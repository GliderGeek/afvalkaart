"""Lees de plekken van de cirkels uit de kaart van het locatiebesluit en reken
ze om naar coördinaten.

De kaart is een rastertekening op schaal 1:1000. Het script:
  1. rendert de PDF en zoekt de gekleurde cirkels (oranje = nieuw, cyaan/groen =
     gewijzigd, rood = opheffen, grijs = ongewijzigd);
  2. georefereert de tekening: de rode, cyaan, groene en grijze cirkels liggen op
     bestaande clusters uit data/bestaand.geojson. Daaruit volgt een
     gelijkvormigheidstransformatie (schaal, rotatie, verschuiving);
  3. schrijft per cirkel de coördinaat naar data/plannen/<plan>.tekening.json.

Welke locatiecode bij welke cirkel hoort, staat in dat bestand onder `label`
(zoals op de tekening te lezen) en eventueel `code` (als de tabel een andere code
gebruikt). Die velden zijn met de hand nagelezen en blijven bij opnieuw draaien
behouden; nieuw gevonden cirkels krijgen label null en moeten worden ingevuld.

Gebruik: uv run scripts/tekening.py erasmusparkbuurt-west
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SCALE = 10000 / 3370.68          # pixels per PDF-punt bij het renderen
R_IN, R_OUT = 83, 105            # straal van de cirkelring in pixels (bij SCALE)
LEGENDA_X = 8300                 # rechts hiervan staan legenda en titelblok
CONTROLE_MAX_M = 10              # controlepunt: cirkel binnen zoveel meter van een cluster
LAT0, LON0 = 52.37, 4.88         # referentie voor lokale meters
KX = 111320 * math.cos(math.radians(LAT0))
KY = 110574


def naar_m(ll):
    return complex((ll[0] - LON0) * KX, (ll[1] - LAT0) * KY)


def naar_ll(z):
    return [round(LON0 + z.real / KX, 7), round(LAT0 + z.imag / KY, 7)]


def render(pdf_pad):
    pdf = pdfium.PdfDocument(str(pdf_pad))
    beeld = pdf[0].render(scale=SCALE).to_pil().convert("RGB")
    return beeld


def maskers(beeld):
    hsv = np.asarray(beeld.convert("HSV")).astype(int)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    rgb = np.asarray(beeld).astype(int)
    kleurig = (s > 120) & (v > 80)
    spreiding = rgb.max(-1) - rgb.min(-1)
    grijswaarde = rgb.mean(-1)
    return {
        "rood": kleurig & ((h < 10) | (h > 245)),
        "oranje": kleurig & (h >= 20) & (h < 42),
        "groen": kleurig & (h >= 60) & (h < 90),
        "cyaan": (s > 90) & (v > 80) & (h >= 105) & (h < 145),
        "blauw": kleurig & (h >= 160) & (h < 180),
        "grijs": (spreiding < 18) & (grijswaarde > 95) & (grijswaarde < 165),
    }


def zoek_cirkels(maskers_):
    """Ringvormige template matching (FFT) per kleur, op halve resolutie."""
    f = 2
    r = int(R_OUT / f) + 3
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    d = np.hypot(yy, xx)
    ring = ((d >= (R_IN + 2) / f) & (d <= (R_OUT - 2) / f)).astype(float)
    binnen = (d < (R_IN - 6) / f).astype(float)
    gevonden = []
    for kleur, m in maskers_.items():
        h, w = m.shape
        ms = m[:h // f * f, :w // f * f].reshape(h // f, f, w // f, f).mean((1, 3))
        if kleur == "grijs":  # alleen dikke grijze lijnen, geen dunne tekenlijnen
            ms = ndi.binary_opening(ms > 0.5, structure=np.ones((3, 3))).astype(float)
        vorm = (ms.shape[0] + 2 * r + 1, ms.shape[1] + 2 * r + 1)
        fm = np.fft.rfft2(ms, vorm)

        def correleer(k):
            c = np.fft.irfft2(fm * np.fft.rfft2(k[::-1, ::-1], vorm), vorm)
            return c[r:r + ms.shape[0], r:r + ms.shape[1]] / k.sum()

        score = correleer(ring) - correleer(binnen)
        piek = (score == ndi.maximum_filter(score, size=30)) & (score > 0.35)
        for y, x in np.argwhere(piek):
            if x * f > LEGENDA_X:
                continue
            gevonden.append({"kleur": kleur, "pt": [round(x * f / SCALE, 1), round(y * f / SCALE, 1)],
                             "score": round(float(score[y, x]), 2)})
    return gevonden


def zoek_symbool(beeld, pt, soort):
    """Plek van het containersymbool binnen een cirkel, in pt. De cirkel staat
    niet altijd precies om het symbool (tot ~7 m ernaast), het symbool wel op de
    plek. Alleen voor herkenbare enkelvoudige symbolen:
      'zwart' = aanbiedplek grofafval (donker vierkant met wit pictogram)
      'groen' = verzamelcontainer GFE/T
    Geeft het symbool het dichtst bij het midden, of None."""
    r = 100
    x, y = round(pt[0] * SCALE), round(pt[1] * SCALE)
    uitsnede = beeld.crop((x - r, y - r, x + r + 1, y + r + 1))
    rgb = np.asarray(uitsnede).astype(int)
    hsv = np.asarray(uitsnede.convert("HSV")).astype(int)
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    binnen = np.hypot(yy, xx) < R_IN + 5
    if soort == "zwart":
        m = rgb.max(-1) < 110
        m = ndi.binary_fill_holes(ndi.binary_closing(m, structure=np.ones((5, 5))))
        m = ndi.binary_opening(m, structure=np.ones((9, 9)))  # dunne lijnen en tekst weg
    else:
        m = (hsv[..., 1] > 90) & (hsv[..., 2] > 60) & (hsv[..., 0] >= 60) & (hsv[..., 0] < 90)
        m = ndi.binary_opening(m, structure=np.ones((5, 5)))
    lab, _ = ndi.label(m & binnen)
    kandidaten = []
    for i, s in enumerate(ndi.find_objects(lab), start=1):
        h, w = s[0].stop - s[0].start, s[1].stop - s[1].start
        if 10 <= h <= 40 and 10 <= w <= 40 and (lab[s] == i).sum() >= 80:
            cy, cx = ndi.center_of_mass(lab == i)
            kandidaten.append((cx - r, cy - r))
    if not kandidaten:
        return None
    dx, dy = min(kandidaten, key=lambda k: k[0] ** 2 + k[1] ** 2)
    return [round(pt[0] + dx / SCALE, 1), round(pt[1] + dy / SCALE, 1)]


def lees_clusters():
    snap = json.loads((DATA / "bestaand.geojson").read_text(encoding="utf-8"))
    clusters = {}
    for f in snap["features"]:
        p = f["properties"]
        clusters.setdefault(p["cluster"] or p["id"], {"id": p["cluster"] or p["id"], "adres": p["adres"],
                                                         "coord": f["geometry"]["coordinates"]})
    return list(clusters.values())


def pas_aan(paren):
    """Kleinste-kwadraten gelijkvormigheidstransformatie w (pt, y omlaag) -> z (m)."""
    w = np.array([complex(p[0], -p[1]) for p, _ in paren])
    z = np.array([q for _, q in paren])
    a, b = np.linalg.lstsq(np.vstack([w, np.ones_like(w)]).T, z, rcond=None)[0]
    return a, b


def main():
    if len(sys.argv) != 2:
        sys.exit("Gebruik: uv run scripts/tekening.py <plan>")
    naam = sys.argv[1]
    plan = json.loads((DATA / "plannen" / f"{naam}.json").read_text(encoding="utf-8"))
    uit_pad = DATA / "plannen" / f"{naam}.tekening.json"
    oud = json.loads(uit_pad.read_text(encoding="utf-8")) if uit_pad.exists() else {"cirkels": []}

    print("Tekening renderen…")
    beeld = render(ROOT / plan["bron"]["tekening"])
    cirkels = zoek_cirkels(maskers(beeld))
    print(f"{len(cirkels)} cirkels gevonden: " + ", ".join(
        f"{k} {sum(c['kleur'] == k for c in cirkels)}" for k in ("oranje", "cyaan", "groen", "rood", "grijs", "blauw")))

    # Handmatige velden van eerdere runs overnemen (zelfde kleur, binnen 10 pt)
    for c in cirkels:
        c.update(label=None)
        for o in oud["cirkels"]:
            if o["kleur"] == c["kleur"] and math.dist(o["pt"], c["pt"]) < 10:
                for k in ("label", "code", "opmerking"):
                    if k in o:
                        c[k] = o[k]
    for o in oud["cirkels"]:
        if not any(o["kleur"] == c["kleur"] and math.dist(o["pt"], c["pt"]) < 10 for c in cirkels):
            print(f"  ! cirkel uit vorige run niet meer gevonden: {o['kleur']} {o.get('label')} {o['pt']}")

    # Georefereren: start met plekken die op adres aan een cluster te koppelen zijn
    clusters = lees_clusters()
    per_code = {loc["code"].replace(" ", ""): loc for s in ("opheffen", "wijzigen") for loc in plan.get(s, [])}
    paren = []
    for c in cirkels:
        loc = per_code.get(c.get("code") or c.get("label") or "")
        if loc:
            treffers = [k for k in clusters if k["adres"] == loc["adres"]]
            if len(treffers) == 1:
                paren.append((c["pt"], naar_m(treffers[0]["coord"])))
    if len(paren) < 3:
        sys.exit("Te weinig startpunten om te georefereren; vul eerst de labels in.")
    a, b = pas_aan(paren)
    for _ in range(5):
        paren, koppeling = [], {}
        for i, c in enumerate(cirkels):
            if c["kleur"] == "oranje":
                continue
            z = a * complex(c["pt"][0], -c["pt"][1]) + b
            k = min(clusters, key=lambda k: abs(naar_m(k["coord"]) - z))
            if abs(naar_m(k["coord"]) - z) < CONTROLE_MAX_M:
                paren.append((c["pt"], naar_m(k["coord"])))
                koppeling[i] = k
        a, b = pas_aan(paren)
    rest = [abs(a * complex(p[0], -p[1]) + b - q) for p, q in paren]
    rms = math.sqrt(sum(r * r for r in rest) / len(rest))
    schaal = 1 / abs(a) / (72 / 25.4) * 1000  # 1:x
    print(f"Georeferentie: {len(paren)} controlepunten, rms {rms:.2f} m, max {max(rest):.2f} m, "
          f"schaal 1:{schaal:.0f}, rotatie {math.degrees(np.angle(a)):.2f}°")

    # Nieuwe plekken met één herkenbaar symbool: positie van het symbool
    nieuw = {loc["code"].replace(" ", ""): loc["items"] for loc in plan.get("nieuw", [])}
    for c in cirkels:
        items = nieuw.get(c.get("code") or c.get("label") or "")
        soort = "zwart" if items == {"grof_ap": 1} else "groen" if items == {"gfe_vc": 1} else None
        c.pop("symbool_pt", None)
        if c["kleur"] == "oranje" and soort:
            s = zoek_symbool(beeld, c["pt"], soort)
            if s:
                c["symbool_pt"] = s
            else:
                print(f"  ! {c['label']}: geen {soort} symbool gevonden, middelpunt cirkel gebruikt")

    for i, c in enumerate(cirkels):
        z = a * complex(c["pt"][0], -c["pt"][1]) + b
        c["coord"] = naar_ll(z)
        if "symbool_pt" in c:
            c["coord"] = naar_ll(a * complex(c["symbool_pt"][0], -c["symbool_pt"][1]) + b)
        if i in koppeling:
            c["cluster"] = koppeling[i]["id"]
            c["cluster_adres"] = koppeling[i]["adres"]
            c["afwijking_m"] = round(abs(naar_m(koppeling[i]["coord"]) - z), 1)
        else:
            for k in ("cluster", "cluster_adres", "afwijking_m"):
                c.pop(k, None)

    volgorde = {"oranje": 0, "cyaan": 1, "groen": 2, "rood": 3, "grijs": 4, "blauw": 5}
    cirkels.sort(key=lambda c: (volgorde[c["kleur"]], c.get("label") or "", c["pt"]))
    sleutels = ["kleur", "label", "code", "opmerking", "pt", "symbool_pt", "coord", "cluster", "cluster_adres", "afwijking_m", "score"]
    uit = {
        "toelichting": "Cirkels uit de kaart van het locatiebesluit, gegenereerd door scripts/tekening.py. "
                       "'label' (en eventueel 'code' en 'opmerking') zijn met de hand nagelezen; de rest is berekend. 'pt' is het middelpunt van de cirkel, 'symbool_pt' het containersymbool (in PDF-punten); 'coord' volgt het symbool als dat er is.",
        "georeferentie": {"controlepunten": len(paren), "rms_m": round(rms, 2), "max_m": round(max(rest), 2),
                          "schaal": f"1:{schaal:.0f}", "rotatie_graden": round(math.degrees(np.angle(a)), 3)},
        "cirkels": [{k: c[k] for k in sleutels if k in c} for c in cirkels],
    }
    uit_pad.write_text(json.dumps(uit, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    zonder = [c for c in cirkels if c["kleur"] != "grijs" and not c.get("label")]
    print(f"Geschreven: {uit_pad.relative_to(ROOT)}" + (f" ({len(zonder)} cirkels zonder label!)" if zonder else ""))


if __name__ == "__main__":
    main()

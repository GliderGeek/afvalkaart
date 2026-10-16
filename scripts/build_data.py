"""Bouw data/locaties.geojson: de nieuwe situatie na uitvoering van de plannen.

Neemt de snapshot data/bestaand.geojson (zie fetch_bestaand.py), beperkt die tot
het plangebied en past daarop alle plannen uit data/plannen/ toe:
  - opheffen: de genoemde containers verdwijnen van het bestaande cluster
  - wijzigen: bestaand cluster - 'voor' + 'items' (ná)
  - nieuw:    nieuwe plek

Posities van planlocaties, in volgorde van voorrang:
  1. data/overrides.json (handmatige correctie)
  2. de kaart van het besluit (data/plannen/<plan>.tekening.json, zie tekening.py)
  3. het adres (PDOK); dat ligt meestal in het gebouw, dus dit geeft een waarschuwing

Het plangebied is de buurt uit data/gebieden.geojson, eventueel afgesneden met
'afsnijden' uit het planbestand. Het resultaat staat in data/plangebied.geojson.

Gebruik: uv run scripts/build_data.py
"""
import sys
from collections import Counter

from common import (DATA, PLANNEN, afstand_m, geocode_alle, in_polygoon, knip_links,
                    load_json, load_overrides, load_plannen, normalize_code, save_json)

# Fracties uit de open data -> sleutel op de kaart
FRACTIES = {"Rest": "rest", "Glas": "glas", "Papier": "papier", "Textiel": "textiel",
            "GFT": "gfe", "GFE": "gfe", "Brood": "brood", "Plastic": "plastic"}

# Welke cirkelkleuren op de tekening bij welke soort planlocatie horen
KLEUREN = {"nieuw": {"oranje", "blauw"}, "wijzigen": {"cyaan", "groen"}, "opheffen": {"rood"}}

MAX_MATCH_M = 50       # zonder tekening: verder weg wordt een cluster niet gekoppeld
WAARSCHUW_M = 25       # zonder tekening: koppelingen verder weg worden gemeld
MAX_ADRES_TEKENING_M = 80  # cirkel verder dan dit van het adres: waarschijnlijk verkeerd label


def plan_items(items):
    """{'rest_oc': 2, 'gfe_vc': 1} -> Counter({('rest','OC'): 2, ('gfe','VC'): 1})"""
    out = Counter()
    for k, n in items.items():
        fractie, soort = k.split("_")
        out[(fractie, soort.upper())] += n
    return out


def lees_bestaand():
    snap = load_json(DATA / "bestaand.geojson")
    if snap is None:
        sys.exit("data/bestaand.geojson ontbreekt; draai eerst uv run scripts/fetch_bestaand.py")
    clusters = {}
    for f in snap["features"]:
        p = f["properties"]
        key = p["cluster"] or p["id"]
        c = clusters.setdefault(key, {"coord": f["geometry"]["coordinates"], "adres": p["adres"],
                                      "containers": []})
        c["containers"].append((FRACTIES.get(p["fractie"], p["fractie"].lower()), p["type"] or "OC"))
    return snap["metadata"], clusters


def lees_tekening(naam, plan, waarschuwingen):
    """{code: cirkel} uit data/plannen/<plan>.tekening.json, met controles."""
    tekening = load_json(PLANNEN / f"{naam}.tekening.json")
    if tekening is None:
        waarschuwingen.append(f"{naam}: geen tekening.json; posities komen van het adres")
        return {}
    soort_van = {normalize_code(loc["code"]): soort for soort in KLEUREN for loc in plan.get(soort, [])}
    per_code = {}
    for c in tekening["cirkels"]:
        if c["kleur"] == "grijs":
            continue
        if not c.get("label"):
            waarschuwingen.append(f"{naam}: {c['kleur']} cirkel op {c['pt']} heeft geen label")
            continue
        code = normalize_code(c.get("code") or c["label"])
        if code not in soort_van:
            waarschuwingen.append(f"{naam}: cirkel {c['label']} ({c['kleur']}) staat op de tekening "
                                  f"maar niet in de tabellen" + (f": {c['opmerking']}" if c.get("opmerking") else ""))
            continue
        if c["kleur"] not in KLEUREN[soort_van[code]]:
            waarschuwingen.append(f"{naam}: {code} is '{soort_van[code]}' in de tabel maar {c['kleur']} op de tekening")
        if code in per_code:
            waarschuwingen.append(f"{naam}: {code} staat twee keer op de tekening")
        per_code[code] = c
    for code in soort_van:
        if code not in per_code:
            waarschuwingen.append(f"{naam}: {code} staat in de tabellen maar heeft geen cirkel op de tekening")
    return per_code


def inhoud(cluster):
    return Counter(f for f, _ in cluster["containers"])


def zoek_cluster(loc, voor, punt, clusters, bezet, waarschuwingen):
    """Zonder tekening: bestaand cluster op adres, anders het dichtstbijzijnde
    cluster dat alle 'voor'-fracties bevat."""
    nodig = Counter(f for (f, _), n in voor.items() for _ in range(n))
    kandidaten = [k for k, c in clusters.items() if k not in bezet and c["adres"] == loc["adres"]]
    if not kandidaten:
        kandidaten = sorted(
            (k for k, c in clusters.items()
             if k not in bezet and not (nodig - inhoud(c))
             and afstand_m(punt, c["coord"]) <= MAX_MATCH_M),
            key=lambda k: afstand_m(punt, clusters[k]["coord"]))[:1]
        if kandidaten:
            d = afstand_m(punt, clusters[kandidaten[0]]["coord"])
            if d > WAARSCHUW_M:
                waarschuwingen.append(f"{loc['adres']} ({loc['code']}): gekoppeld aan cluster "
                                      f"'{clusters[kandidaten[0]]['adres']}' op {d:.0f} m, controleer")
    return kandidaten[0] if kandidaten else None


def verwijder(cluster, items):
    """Haal containers weg; eerst met hetzelfde type, anders van dezelfde fractie."""
    for (fractie, soort), n in items.items():
        for _ in range(n):
            for kandidaat in [(fractie, soort)] + [c for c in cluster["containers"] if c[0] == fractie]:
                if kandidaat in cluster["containers"]:
                    cluster["containers"].remove(kandidaat)
                    break


def plangebied(naam, plan, gebieden):
    for g in gebieden["features"]:
        if g["properties"]["plan"] == naam:
            geom = g["geometry"]
            if plan.get("afsnijden"):
                geom = knip_links(geom, plan["afsnijden"]["lijn"])
            return {"type": "Feature", "geometry": geom,
                    "properties": {**g["properties"], "afsnijden": plan.get("afsnijden", {}).get("reden")}}
    sys.exit(f"Buurt van plan {naam} ontbreekt in data/gebieden.geojson; draai scripts/fetch_bestaand.py")


def main():
    metadata, clusters = lees_bestaand()
    adressen = geocode_alle()
    overrides = load_overrides()
    gebieden = load_json(DATA / "gebieden.geojson")
    if gebieden is None:
        sys.exit("data/gebieden.geojson ontbreekt; draai eerst uv run scripts/fetch_bestaand.py")
    waarschuwingen = []
    bezet = set()
    bronnen = []
    gebied_features = []
    nieuw_plekken = []
    posities = Counter()

    for naam, plan in load_plannen():
        bronnen.append({"plan": naam, "naam": plan["naam"], **plan.get("bron", {})})
        gebied_features.append(plangebied(naam, plan, gebieden))
        tekening = lees_tekening(naam, plan, waarschuwingen)

        def positie(loc):
            code = normalize_code(loc["code"])
            if code in overrides:
                return overrides[code], "handmatig"
            if code in tekening:
                c = tekening[code]
                d = afstand_m(c["coord"], adressen[code])
                if d > MAX_ADRES_TEKENING_M:
                    waarschuwingen.append(f"{loc['adres']} ({code}): cirkel ligt {d:.0f} m van het adres, "
                                          f"controleer het label op de tekening")
                return c["coord"], "tekening"
            waarschuwingen.append(f"{loc['adres']} ({code}): geen positie op de tekening, op het adres gezet")
            return adressen[code], "adres"

        def cluster_voor(loc, voor):
            code = normalize_code(loc["code"])
            c = tekening.get(code)
            if c is not None:
                k = c.get("cluster")
                if k not in clusters:
                    waarschuwingen.append(f"{loc['adres']} ({code}): cirkel ligt niet op een bestaand cluster")
                    return None
            else:
                k = zoek_cluster(loc, voor, adressen[code], clusters, bezet, waarschuwingen)
                if k is None:
                    return None
            if k in bezet:
                waarschuwingen.append(f"{loc['adres']} ({code}): cluster {clusters[k]['adres']} is al gekoppeld")
            nodig = Counter(f for (f, _), n in voor.items() for _ in range(n))
            if nodig - inhoud(clusters[k]):
                waarschuwingen.append(f"{loc['adres']} ({code}): cluster '{clusters[k]['adres']}' bevat niet alles "
                                      f"uit de vóór-situatie ({dict(inhoud(clusters[k]))} vs {dict(nodig)})")
            bezet.add(k)
            return k

        for loc in plan.get("opheffen", []):
            items = plan_items(loc["items"])
            k = cluster_voor(loc, items)
            if k is None:
                waarschuwingen.append(f"Opheffen {loc['adres']} ({loc['code']}): geen bestaand cluster gevonden")
                continue
            verwijder(clusters[k], items)
            clusters[k].update(code=loc["code"], plan=naam, adres=loc["adres"])
        for loc in plan.get("wijzigen", []):
            voor, na = plan_items(loc.get("voor", {})), plan_items(loc["items"])
            k = cluster_voor(loc, voor)
            if k is None:
                waarschuwingen.append(f"Wijzigen {loc['adres']} ({loc['code']}): geen bestaand cluster gevonden, "
                                      f"als nieuwe plek toegevoegd")
                nieuw_plekken.append((naam, loc, na, *positie(loc)))
                continue
            c = clusters[k]
            verwijder(c, voor)
            c["containers"] += [fs for fs, n in na.items() for _ in range(n)]
            c.update(code=loc["code"], plan=naam, adres=loc["adres"], positie="open data")
            if normalize_code(loc["code"]) in overrides:
                c.update(coord=overrides[normalize_code(loc["code"])], positie="handmatig")
        for loc in plan.get("nieuw", []):
            nieuw_plekken.append((naam, loc, plan_items(loc["items"]), *positie(loc)))

    features = []

    def voeg_toe(coord, containers, adres, code, plan, bron):
        for fractie, soort in sorted(containers):
            posities[bron] += 1
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": coord},
                "properties": {"fractie": fractie, "type": soort, "adres": adres,
                               "code": code, "plan": plan, "positie": bron},
            })

    # Bestaande clusters alleen binnen het plangebied; clusters die een plan
    # aanpast tellen altijd mee, ook als ze net over de grens liggen.
    buiten = 0
    for c in clusters.values():
        if c.get("plan") or any(in_polygoon(c["coord"], g["geometry"]) for g in gebied_features):
            voeg_toe(c["coord"], c["containers"], c["adres"], c.get("code"), c.get("plan"),
                     c.get("positie", "open data"))
        else:
            buiten += 1
    for naam, loc, items, punt, bron in nieuw_plekken:
        voeg_toe(punt, [fs for fs, n in items.items() for _ in range(n)], loc["adres"], loc["code"], naam, bron)

    save_json(DATA / "locaties.geojson", {
        "type": "FeatureCollection",
        "metadata": {"bestaand_opgehaald": metadata["opgehaald"], "plannen": bronnen},
        "features": features,
    }, indent=None)
    save_json(DATA / "plangebied.geojson", {"type": "FeatureCollection", "features": gebied_features}, indent=None)

    print("Containers per fractie (nieuwe situatie):")
    for (fr, ty), n in sorted(Counter((f["properties"]["fractie"], f["properties"]["type"])
                                      for f in features).items()):
        print(f"  {fr:<10} {ty:<3} {n}")
    print(f"Totaal {len(features)} containers ({buiten} bestaande clusters buiten het plangebied weggelaten)")
    print("Herkomst posities: " + ", ".join(f"{k} {n}" for k, n in posities.most_common()))
    if waarschuwingen:
        print(f"\n{len(waarschuwingen)} waarschuwing(en):")
        for w in waarschuwingen:
            print("  - " + w)


if __name__ == "__main__":
    main()

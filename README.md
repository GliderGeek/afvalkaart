# afvalkaart

Een interactieve kaart van de afvalcontainers in **Erasmusparkbuurt-West** (Bos en Lommer, Amsterdam), zoals ze staan **nadat** de gemeente het locatiebesluit heeft uitgevoerd.

Dit is een onofficiële kaart, geen product van de gemeente Amsterdam en kan fouten bevatten.

## De kaart gebruiken

- Klik op een icoon of cluster voor de containers op die plek: adres, locatiecode, soort (ondergronds, bovengronds, verzamelcontainer, aanbiedplek grof afval). Bij een plek waarvan de positie onzeker is, staat dat erbij.
- Met de legenda zet je soorten afval aan en uit.
- De stippellijn is het gebied van het besluit.

## Waar komen de gegevens vandaan?

| Gegevens | Bron | Opgehaald |
|---|---|---|
| Locatiebesluit: kaart (`docs/afvalplan_erasmusparkbuurt-west.pdf`, tekening EF02-001) en tabellen (`docs/plekken_containers_en_grof_afval_erasmusparkbuurt-west.pdf`) | Gemeente Amsterdam, [Ondergrondse afvalcontainers – Bos en Lommer](https://www.amsterdam.nl/afval/ondergrondse-afvalcontainers/west/bos-lommer/) | 16 oktober 2026 |
| Bestaande containers | Gemeente Amsterdam, open data [Huishoudelijk afval](https://api.data.amsterdam.nl/v1/huishoudelijkafval/) | 16 oktober 2026 |
| Buurtgrens Erasmusparkbuurt-West (EF02) | Gemeente Amsterdam, open data [Gebieden](https://api.data.amsterdam.nl/v1/gebieden/) | 16 oktober 2026 |
| Adressen naar coördinaten | [PDOK Locatieserver](https://www.pdok.nl/introductie/-/article/pdok-locatieserver) (Kadaster) | 16 oktober 2026 |
| Achtergrondkaart | [BRT-Achtergrondkaart grijs](https://www.pdok.nl/introductie/-/article/basisregistratie-topografie-achtergrondkaarten-brt-a-) van het Kadaster, via PDOK | live |

**Zo is de kaart opgebouwd:**

1. De bestaande containers zijn één keer opgehaald uit de open data. Wijzigingen die de gemeente daarna doorvoert, staan er dus niet in.
2. Daarop zijn de tabellen uit het besluit toegepast: plekken opheffen (IIb), plekken wijzigen (IIc, vóór en ná) en nieuwe plekken (IIa).
3. **Posities van nieuwe plekken** komen van de kaart van het besluit. Dat is een tekening op schaal 1:1000. Ze is gegeoreferenceerd op 27 bestaande containerplekken die zowel op de tekening als in de open data staan (gemiddelde afwijking ±2,4 m). Waar het containersymbool herkenbaar is, staat de plek op het symbool, en anders op het midden van de cirkel.
4. Gewijzigde plekken houden hun bestaande positie uit de open data.

**Tegenstrijdigheden tussen tabel en tekening.** De tabellen en de tekening van het besluit spreken elkaar op een paar plekken tegen. De kaart volgt steeds de tabel. Deze verschillen staan ook als `opmerking` in `data/plannen/erasmusparkbuurt-west.tekening.json`.

- **Aanbiedplekken grof afval die niet op dezelfde plek staan.** Tabel IIa en de tekening noemen elk twee plekken die de ander niet heeft:

  | Alleen op de tekening (niet op de kaart) | Alleen in tabel IIa (op de kaart, op het adres) |
  |---|---|
  | Lorreinenstraat 20 (1055DB-20), hoek Bos en Lommerweg | Reinaert de Vosstraat 18 (1055CM-18) |
  | Blancefloorstraat 1 (1055TA-1), aan de Erasmusgracht | Roelantstraat 19 (1056ES-19) |

  De plekken liggen 90 tot 130 m uit elkaar, dus het is geen verwisseling van labels. De twee plekken uit de tabel hebben geen cirkel en staan daarom op het adres. De echte plek kan dus afwijken.
- **Andere inhoud op de tekening dan in de tabel:**
  - **Vier Heemskinderenstraat 56**: de tabel noemt alleen een aanbiedplek grof afval. De tekening toont ondergrondse containers voor papier, 2× rest en GFE.
  - **Marieken van Nimwegenstraat 5**: de tabel noemt rest, papier en GFE. Op de tekening ontbreekt papier.
  - **Vier Heemskinderenstraat 15**: volgens de tabel wordt de restafvalcontainer een papiercontainer. Op de tekening staan rest en papier.
  - **Reinaert de Vosstraat 27**: de tabel noemt ook een textielcontainer. Op de tekening is die niet te zien.
- **Andere locatiecode:** Elegaststraat 14 heet op de tekening 1055TH-13 en in de tabel 1055TH-14. Het is dezelfde plek.
- **Bestaande plekken zonder cirkel.** De tekening markeert maar 7 bestaande plekken met een grijze cirkel als "aanbiedplek ongewijzigd". De volgende plekken staan in de open data van de gemeente als actief, maar ze staan niet op de tekening en niet in de tabellen:

  | Adres | Containers |
  |---|---|
  | Bos en Lommerweg 237 | 2× restafval |
  | Bos en Lommerweg 295 | 2× restafval |
  | Esmoreitstraat 36 | 2× restafval |
  | Hoofdweg 584 | 2× restafval |
  | Vier Heemskinderenstraat 5 | restafval |
  | Elckerlijcstraat 195 | papier |

  Het besluit heft deze plekken niet op, dus de kaart toont ze zoals ze in de open data staan.

## Iets klopt niet?

Meld het via een [issue met het formulier *Correctie melden*](https://github.com/GliderGeek/afvalkaart/issues/new?template=correctie.yml). Klik eerst op de container en neem de gegevens uit de popup en de link uit de adresbalk over. Vragen of bezwaar over het besluit zelf horen bij de gemeente.

---

## Zelf draaien en aanpassen

De site is volledig statisch: `index.html`, `css/`, `js/` en `data/locaties.geojson`. Publiceren kan met GitHub Pages (`main`-branch, root) of op elke andere webhost.

```sh
uv run python -m http.server       # en open http://localhost:8000
```

### Bestanden

```
data/plannen/<plan>.json           tabellen uit het besluit (met de hand overgenomen, bron van waarheid)
data/plannen/<plan>.tekening.json  cirkels van de tekening: label (nagelezen) en berekende coördinaat
data/overrides.json                handmatige correcties van posities (gaan voor alles)
data/bestaand.geojson              snapshot van de bestaande containers
data/gebieden.geojson              buurtgrenzen
data/geocache.json                 coördinaten van de adressen (PDOK)
data/locaties.geojson              resultaat: de nieuwe situatie, die de pagina laadt
data/plangebied.geojson            resultaat: het getoonde gebied
scripts/fetch_bestaand.py          haalt de snapshot en de buurtgrenzen op
scripts/tekening.py                leest de cirkels van de tekening en georefereert ze
scripts/build_data.py              voegt alles samen
```

### Bouwen

Alles draait met [uv](https://docs.astral.sh/uv/). De dependencies staan in `pyproject.toml`, en `uv run` installeert ze de eerste keer zelf.

```sh
uv run scripts/build_data.py                          # na elke wijziging in data/
uv run scripts/tekening.py erasmusparkbuurt-west      # alleen als de tekening verandert
uv run scripts/fetch_bestaand.py                      # alleen voor een nieuwe buurt of een verse snapshot
```

Haal je de snapshot opnieuw op, zet dan de nieuwe datum in de bronnentabel hierboven. De datum staat ook in `data/bestaand.geojson` en verschijnt op de pagina.

### Hoe `build_data.py` werkt

- **Plangebied**: de buurt uit het planbestand (`buurt`), eventueel ingekort met `afsnijden` (een lijn waarvan het deel links blijft staan). Bestaande clusters buiten het gebied vallen weg, behalve clusters die het plan wijzigt of opheft.
- **Opheffen**: de genoemde containers verdwijnen van het bestaande cluster dat onder de rode cirkel ligt.
- **Wijzigen**: van het bestaande cluster onder de cyaan of groene cirkel gaat de vóór-situatie eraf en komt de ná-situatie erbij. Containers die de tabel niet noemt, blijven staan.
- **Nieuw**: een nieuwe plek. Voor de positie geldt de volgorde `overrides.json` → tekening → adres.
- Het script waarschuwt bij elk verschil tussen tabel en tekening: een cirkel zonder tabelregel, een tabelregel zonder cirkel, een verkeerde kleur, een cirkel ver van het adres, of een vóór-situatie die niet in de open data staat.

### Een correctie verwerken

Zet in `data/overrides.json` onder de locatiecode `{"coord": [lon, lat], "reden": "..."}` en draai `uv run scripts/build_data.py`. Verwijs in de reden naar het issue.

### Een buurt toevoegen

1. Zet de PDF's in `docs/` en vul de bronnentabel aan.
2. Maak `data/plannen/<buurt>.json` in hetzelfde formaat als `erasmusparkbuurt-west.json`:
   - `buurt`: de code en de identificatie uit de [Gebieden-API](https://api.data.amsterdam.nl/v1/gebieden/buurten/).
   - `bron.tekening`: het pad naar de PDF.
   - Drie lijsten: `nieuw`, `opheffen` en `wijzigen` (met `voor` en `items`). Gebruik als sleutels `rest_oc`, `rest_bc`, `papier_oc`, `papier_bc`, `glas_oc`, `glas_bc`, `textiel_oc`, `textiel_bc`, `gfe_vc` en `grof_ap`.
3. Draai `uv run scripts/fetch_bestaand.py`.
4. Draai `uv run scripts/tekening.py <buurt>`. Vul daarna in `<buurt>.tekening.json` bij elke cirkel het `label` in zoals het op de tekening staat. De georeferentie heeft minstens drie gelabelde rode of cyane cirkels nodig. Draai het script daarna nog een keer.
5. Draai `uv run scripts/build_data.py` en loop de waarschuwingen na. Verschillen tussen tabel en tekening leg je vast als `opmerking` bij de cirkel in `<buurt>.tekening.json`.

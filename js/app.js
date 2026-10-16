(function () {
  "use strict";

  // Ondergrond. Wisselen kan door alleen deze regels aan te passen.
  var TILES = "https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/grijs/EPSG:3857/{z}/{x}/{y}.png";
  var TILES_ATTR = 'Kaartgegevens &copy; <a href="https://www.kadaster.nl">Kadaster</a> (BRT-Achtergrondkaart via PDOK)';

  // Pictogrammen (24x24, gevuld)
  var PATHS = {
    rest: "M9 3.5h6l-1.6 3.2h-2.8zM8.2 8h7.6c2 2.3 3.7 5.5 3.7 8.3 0 2.9-3.3 4.2-7.5 4.2s-7.5-1.3-7.5-4.2C4.5 13.5 6.2 10.3 8.2 8z",
    glas: "M10 2.5h4v3.2c0 1.2 2.5 2 2.5 4.6v10.2a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1V10.3c0-2.6 2.5-3.4 2.5-4.6z",
    papier: "M4 5h14a2 2 0 0 1 2 2v12a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1zM7 8v4h6V8zm0 6v1.5h10V14zm0 3v1.5h10V17zm7.5-9v1.5H17V8zm0 2.5V12H17v-1.5z",
    textiel: "M8.5 3.5 3 6.5l2 4.5 2-1v10.5h10V10l2 1 2-4.5-5.5-3c-.4 1.5-1.8 2.5-3.5 2.5s-3.1-1-3.5-2.5z",
    gfe: "M12 7.6c-1.5-1-5.5-1.6-6.8 2.2-1.2 3.5 1 9.7 3.8 10.6 1.2.4 2-.4 3-.4s1.8.8 3 .4c2.8-.9 5-7.1 3.8-10.6C17.5 6 13.5 6.6 12 7.6zM11.6 7c0-2 1.2-3.6 3.4-4.1-.2 2.1-1.4 3.6-3.4 4.1z",
    brood: "M6 9.5C4 9.5 3 8.3 3 7c0-2 3-3.5 9-3.5S21 5 21 7c0 1.3-1 2.5-3 2.5V19a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19z",
    grof: "M5 9V7a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v2a2 2 0 0 0-2 2v2H7v-2a2 2 0 0 0-2-2zM3 11a2 2 0 0 1 4 0v3h10v-3a2 2 0 0 1 4 0v6a1 1 0 0 1-1 1h-1v2h-2v-2H8v2H6v-2H4a1 1 0 0 1-1-1z",
    overig: "M6 4h12l-1 16H7zM4 4h16v2H4z"
  };

  // Volgorde van de legenda
  var FRACTIES = [
    { key: "rest", naam: "Restafval", kleur: "#757575", fg: "#fff" },
    { key: "glas", naam: "Glas", kleur: "#ffe600", fg: "#000" },
    { key: "papier", naam: "Papier en karton", kleur: "#1f4aa0", fg: "#fff" },
    { key: "textiel", naam: "Textiel", kleur: "#e5348d", fg: "#fff" },
    { key: "gfe", naam: "Groente-, fruit-, etensresten en tuinafval (gfe/t)", kleur: "#3d9b35", fg: "#fff" },
    { key: "brood", naam: "Brood", kleur: "#6b3a1f", fg: "#fff" },
    { key: "plastic", naam: "Plastic", kleur: "#f28c00", fg: "#fff", icon: "overig" },
    { key: "grof", naam: "Grof afval (aanbiedplek)", kleur: "#3a3a3a", fg: "#fff" }
  ];

  var TYPES = {
    OC: "ondergronds",
    BC: "bovengronds",
    VC: "verzamelcontainer",
    AP: "aanbiedplek"
  };

  // Opmerking bij een onzekere positie (zie scripts/build_data.py)
  var POSITIE = {
    "adres": "Let op: deze plek staat niet op de kaart van het besluit. Hij staat daarom op het adres en de echte plek kan afwijken."
  };

  var byKey = {};
  FRACTIES.forEach(function (f) { byKey[f.key] = f; });

  function fractie(key) {
    if (!byKey[key]) {
      byKey[key] = { key: key, naam: key.charAt(0).toUpperCase() + key.slice(1), kleur: "#8a8a8a", fg: "#fff", icon: "overig" };
      FRACTIES.push(byKey[key]);
    }
    return byKey[key];
  }

  function iconHtml(f) {
    return '<span class="afval-icon" style="background:' + f.kleur + '">' +
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="' + f.fg + '" fill-rule="evenodd" d="' +
      PATHS[f.icon || f.key] + '"/></svg></span>';
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  // ---- Kaart ----
  var map = L.map("map", { zoomControl: false, maxZoom: 20 }).setView([52.378, 4.852], 16);
  L.tileLayer(TILES, { attribution: TILES_ATTR, maxZoom: 20, maxNativeZoom: 19 }).addTo(map);
  map.attributionControl.addAttribution('<a href="https://github.com/GliderGeek/afvalkaart">Broncode</a>');
  L.control.zoom({ position: "bottomright", zoomInTitle: "Inzoomen", zoomOutTitle: "Uitzoomen" }).addTo(map);

  var Locate = L.Control.extend({
    options: { position: "bottomright" },
    onAdd: function () {
      var div = L.DomUtil.create("div", "leaflet-bar");
      var btn = L.DomUtil.create("button", "locate", div);
      btn.type = "button";
      btn.title = "Toon mijn locatie";
      btn.setAttribute("aria-label", "Toon mijn locatie");
      btn.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="6.5"/><path d="M12 2v3.5M12 18.5V22M2 12h3.5M18.5 12H22"/></g><circle cx="12" cy="12" r="2.5" fill="currentColor"/></svg>';
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.on(btn, "click", function () { map.locate({ setView: true, maxZoom: 18 }); });
      return div;
    }
  });
  map.addControl(new Locate());

  var locMarker = null;
  map.on("locationfound", function (e) {
    if (locMarker) locMarker.remove();
    locMarker = L.circleMarker(e.latlng, { radius: 8, color: "#fff", weight: 3, fillColor: "#004699", fillOpacity: 1 }).addTo(map);
  });
  map.on("locationerror", function () { alert("Je locatie kon niet worden bepaald."); });

  // Clusterbolletje: wit rondje met aantal en een ring verdeeld naar fractie
  function clusterIcon(cluster) {
    var markers = cluster.getAllChildMarkers();
    var tel = {};
    markers.forEach(function (m) { tel[m.options.fractie] = (tel[m.options.fractie] || 0) + 1; });
    var n = markers.length;
    var size = n < 10 ? 44 : n < 100 ? 50 : 56;
    var r = size / 2 - 3;
    var omtrek = 2 * Math.PI * r;
    var offset = 0;
    var ring = "";
    FRACTIES.forEach(function (f) {
      if (!tel[f.key]) return;
      var len = omtrek * tel[f.key] / n;
      ring += '<circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke="' + f.kleur +
        '" stroke-width="4" stroke-dasharray="' + len + " " + (omtrek - len) + '" stroke-dashoffset="' + (-offset) +
        '" transform="rotate(-90 ' + size / 2 + " " + size / 2 + ')"/>';
      offset += len;
    });
    var html = '<svg viewBox="0 0 ' + size + " " + size + '"><circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + (r + 2) +
      '" fill="#fff"/>' + ring + '<text x="50%" y="50%" text-anchor="middle" dominant-baseline="central">' + n + "</text></svg>";
    return L.divIcon({ html: html, className: "afval-cluster", iconSize: [size, size] });
  }

  var clusterLayer = L.markerClusterGroup({
    iconCreateFunction: clusterIcon,
    showCoverageOnHover: false,
    maxClusterRadius: 40,
    spiderfyDistanceMultiplier: 1.6
  }).addTo(map);

  // Popup per plek: alle containers op hetzelfde punt
  var plekken = {};

  function popupHtml(plek) {
    var tel = {};
    plek.containers.forEach(function (c) {
      var k = c.fractie + "|" + c.type;
      tel[k] = (tel[k] || 0) + 1;
    });
    var regels = Object.keys(tel).sort(function (a, b) {
      return FRACTIES.indexOf(fractie(a.split("|")[0])) - FRACTIES.indexOf(fractie(b.split("|")[0]));
    }).map(function (k) {
      var p = k.split("|");
      var f = fractie(p[0]);
      return "<li>" + iconHtml(f) + "<span>" + tel[k] + "&times; " + esc(f.naam) +
        (TYPES[p[1]] && p[1] !== "AP" ? " (" + TYPES[p[1]] + ")" : "") + "</span></li>";
    });
    return '<div class="popup"><h2>' + esc(plek.adres || "Onbekend adres") + "</h2>" +
      (plek.code ? '<p class="code">Locatiecode ' + esc(plek.code) + "</p>" : '<p class="code"></p>') +
      "<ul>" + regels.join("") + "</ul>" +
      (plek.code ? '<p class="note">Nieuw of gewijzigd in het locatiebesluit.</p>' : "") +
      (POSITIE[plek.positie] ? '<p class="note">' + POSITIE[plek.positie] + "</p>" : "") +
      '<p class="note"><a href="https://github.com/GliderGeek/afvalkaart/issues/new?template=correctie.yml&title=' +
      encodeURIComponent("Correctie: " + (plek.adres || "") + (plek.code ? " (" + plek.code + ")" : "")) +
      '" target="_blank" rel="noopener">Klopt dit niet? Meld een correctie</a></p>' +
      "</div>";
  }

  var alleMarkers = [];
  var aanUit = {};

  function filter() {
    clusterLayer.clearLayers();
    clusterLayer.addLayers(alleMarkers.filter(function (m) { return aanUit[m.options.fractie]; }));
  }

  function bouwLegenda(telling) {
    var ul = document.getElementById("legend-body");
    FRACTIES.forEach(function (f) {
      if (!telling[f.key]) return;
      aanUit[f.key] = true;
      var li = document.createElement("li");
      li.innerHTML = '<label><input type="checkbox" checked><span class="name">' + esc(f.naam) +
        ' <span class="count">(' + telling[f.key] + ")</span></span>" + iconHtml(f) + "</label>";
      li.querySelector("input").addEventListener("change", function (e) {
        aanUit[f.key] = e.target.checked;
        filter();
      });
      ul.appendChild(li);
    });
  }

  // Legenda in- en uitklappen
  var legend = document.getElementById("legend");
  var toggle = legend.querySelector(".legend-toggle");
  function setLegend(open) {
    legend.classList.toggle("collapsed", !open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.querySelector(".legend-toggle-label").textContent = open ? "Verberg legenda" : "Toon legenda";
  }
  toggle.addEventListener("click", function () { setLegend(legend.classList.contains("collapsed")); });
  if (window.matchMedia("(max-width: 640px)").matches) setLegend(false);

  // Infopaneel
  var infoBtn = document.querySelector(".info-toggle");
  var info = document.getElementById("info");
  infoBtn.addEventListener("click", function () {
    info.hidden = !info.hidden;
    infoBtn.setAttribute("aria-expanded", String(!info.hidden));
    map.invalidateSize();
  });

  function laad(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + ": " + r.status);
      return r.json();
    });
  }

  Promise.all([laad("data/locaties.geojson"), laad("data/plangebied.geojson")])
    .then(function (res) {
      var data = res[0];
      // Grens van het plangebied
      var grens = L.geoJSON(res[1], {
        interactive: false,
        style: { color: "#004699", weight: 2, opacity: 0.7, dashArray: "6 6", fill: false }
      }).addTo(map);

      var telling = {};
      data.features.forEach(function (feat) {
        var p = feat.properties;
        var c = feat.geometry.coordinates;
        var f = fractie(p.fractie);
        telling[f.key] = (telling[f.key] || 0) + 1;
        var key = c[0] + "," + c[1];
        var plek = plekken[key] || (plekken[key] = { adres: p.adres, code: p.code, positie: p.positie, containers: [] });
        plek.containers.push(p);
        var m = L.marker([c[1], c[0]], {
          icon: L.divIcon({ html: iconHtml(f), className: "afval-marker", iconSize: [32, 32] }),
          title: f.naam + (p.adres ? " – " + p.adres : ""),
          fractie: f.key
        });
        m.bindPopup(function () { return popupHtml(plek); });
        alleMarkers.push(m);
      });
      bouwLegenda(telling);
      filter();
      var h = /^#(\d+)\/(-?[\d.]+)\/(-?[\d.]+)$/.exec(location.hash);
      if (h) map.setView([+h[2], +h[3]], +h[1]);
      else map.fitBounds(grens.getBounds(), { padding: [20, 20] });
      // Kaartpositie in de URL, zodat je een link naar een plek kunt delen
      map.on("moveend", function () {
        var c = map.getCenter();
        history.replaceState(null, "", "#" + map.getZoom() + "/" + c.lat.toFixed(5) + "/" + c.lng.toFixed(5));
      });

      var meta = data.metadata || {};
      document.querySelectorAll("[data-meta]").forEach(function (el) {
        var v = meta[el.getAttribute("data-meta")];
        if (v) el.textContent = new Date(v).toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" });
      });
    })
    .catch(function (err) {
      alert("De containerdata kon niet worden geladen (" + err.message + ").");
    });
})();

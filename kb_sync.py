"""
KB sync — stahne verejny obsah z produkce lughnasad.cz (REST export v theme)
a prepise Google Sheet tab "KB Web (auto)". Tab je plne rizeny timto syncem
(clear + rewrite) — RUCNE NEEDITOVAT, zmeny prepise dalsi beh. Rucni obsah
patri do tabu "Knowledge Base", ktery sync nikdy nemeni.

Bezi: pri startu, pak 1x denne (viz server.py), on-demand POST /kb/sync.
"""

import urllib.request
import json

EXPORT_URL = "https://www.lughnasad.cz/wp-json/lughnasad/v1/chatbot-export"
AUTO_TAB = "KB Web (auto)"

DEN_LABEL = {"patek": "Pátek 31. 7.", "sobota": "Sobota 1. 8."}
POI_TYP = {"station": "stanoviště", "booth": "stánek", "service": "služba"}


def fetch_export(url: str = EXPORT_URL) -> dict:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def build_rows(d: dict) -> list[list[str]]:
    """Prevede export na radky [kategorie, fakt] ve strukture KB tabu."""
    rows: list[list[str]] = []

    f = d.get("festival", {})
    rows.append(["Festival", f"Festival Lughnasad 2026 ({f.get('rocnik')}. ročník, téma {f.get('tema')}) se koná LETOS, {f.get('datum')}, v areálu {f.get('misto')}."])
    rows.append(["Festival", f"Adresa: {f.get('adresa')}. GPS: {f.get('gps')}. Mapa: {f.get('maps_url')}"])

    # Program po dnech (patek pred sobotou; export radi jen podle casu)
    program = sorted(d.get("program", []), key=lambda x: 0 if x.get("den") == "patek" else 1)
    for item in program:
        den = DEN_LABEL.get(item.get("den"), item.get("den", ""))
        kat = f"Program {den.split(' ')[0].lower()}" if den else "Program"
        if item.get("info"):
            rows.append([f"Program — {den}", f"{item.get('cas')}: {item.get('nazev')} (provozní informace)"])
            continue
        fakt = f"{item.get('cas')}: {item.get('nazev')}"
        if item.get("ucinkujici"):
            fakt += f" — {item['ucinkujici']}"
        detail = ", ".join(x for x in [item.get("druh"), item.get("misto")] if x)
        if detail:
            fakt += f" ({detail})"
        if item.get("anotace"):
            fakt += f". {item['anotace']}"
        rows.append([f"Program — {den}", fakt])

    # POI mapy
    for p in d.get("poi", []):
        typ = POI_TYP.get(p.get("typ"), p.get("typ", ""))
        fakt = f"{p.get('nazev')}"
        if typ:
            fakt += f" ({typ}"
            if p.get("pin"):
                fakt += f", na mapě značka {p['pin']}"
            fakt += ")"
        if p.get("popis"):
            fakt += f": {p['popis']}"
        rows.append(["Mapa areálu", fakt])

    # Vstupenky
    v = d.get("vstupenky", {})
    for t in v.get("typy", []):
        rows.append(["Vstupenky", f"{t.get('nazev')}: základní {t.get('zakladni')}, zvýhodněná {t.get('zvyhodnena')}."])
    hp, hs = v.get("historicky_patek", {}), v.get("historicky_sobota", {})
    if hp.get("zakladni"):
        rows.append(["Vstupenky", f"Historický program pátek (bez večerních koncertů): základní {hp.get('zakladni')}, zvýhodněná {hp.get('zvyhodnena')}. Sobota: základní {hs.get('zakladni')}, zvýhodněná {hs.get('zvyhodnena')}."])
    if v.get("kelt", {}).get("popis"):
        rows.append(["Vstupenky", f"Kelt tělem i duší ({v['kelt'].get('cena')}): {v['kelt']['popis']}"])
    for key, label in [("slevy", "Slevy"), ("predprodej_pozn", "Předprodej"), ("omezeni", "Omezený počet vstupenek"), ("predprodej_vs_misto", "Předprodej vs. na místě"), ("pouze_na_miste", "Pouze na místě"), ("pouze_predprodej", "Pouze v předprodeji")]:
        if v.get(key):
            rows.append(["Vstupenky", f"{label}: {v[key]}"])
    rows.append(["Vstupenky", "Vstupenky se prodávají online na lughnasad.cz (vložený prodej SMSticket) nebo na smsticket.cz."])

    # FAQ
    for q in d.get("faq", []):
        rows.append(["Časté dotazy", f"{q.get('otazka')} {q.get('odpoved')}"])

    # Doprava / prakticke info
    for s in d.get("info", []):
        rows.append(["Praktické info", f"{s.get('titulek')}: {s.get('obsah')}"])

    # Stankari
    st = d.get("stankari", {})
    if st.get("text"):
        rows.append(["Stánkaři", st["text"]])
    if st.get("prihlaska_pdf"):
        rows.append(["Stánkaři", f"Přihláška stánkaře ke stažení (PDF): {st['prihlaska_pdf']}. Na stránce lughnasad.cz/stankari je i online přihláškový formulář."])

    return rows


def sync_kb(gc, sheet_id: str) -> int:
    """Stahne export, prepise auto tab. Vraci pocet radku."""
    data = fetch_export()
    rows = build_rows(data)
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(AUTO_TAB)
    except Exception:
        ws = sh.add_worksheet(AUTO_TAB, rows=2000, cols=3)
    header = [["Kategorie", "Fakt (NEEDITOVAT — tab se přepisuje automaticky z lughnasad.cz)"]]
    ws.clear()
    ws.update(header + rows, "A1")
    print(f"✅ KB Web (auto) synced: {len(rows)} rows (program {len(data.get('program', []))}, poi {len(data.get('poi', []))}, faq {len(data.get('faq', []))})")
    return len(rows)

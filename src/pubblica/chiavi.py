"""Prende le chiavi di TUTTE le pagine dei clienti con un solo token di Meta.

Si lancia sul computer di Lisa (mai su GitHub):
    python -m pubblica.chiavi

1. legge dagli appunti il token utente copiato (e subito svuota gli appunti);
2. se è un token breve, legge allo stesso modo la chiave segreta dell'app e lo allunga;
3. legge le pagine collegate al token e le abbina ai clienti;
4. scrive gli id (non segreti) in config/clienti.json;
5. mette le chiavi di pagina negli appunti: le incolli nel segreto GitHub META_PAGE_TOKENS.
Nessuna chiave viene mai stampata a schermo.
"""
import json
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import requests

from .meta import GRAPH

APP_ID = "1804874100748860"

# cliente -> parole che devono comparire nel nome della pagina Facebook
CLIENTI = {
    "rigenera-lab": ["rigenera lab", "rigenera medicina"],
    "rigenera-active": ["rigenera active"],
    "trattoria-la-brasera": ["brasera"],
    "poliambulatorio-benessere": ["poliambulatorio benessere"],
    "arcamed": ["arcamed", "arca med"],
    "vyva-clinic": ["vyva"],
    "studio-dinamo": ["dinamo"],
}


class Errore(Exception):
    pass


def normalizza(testo: str) -> str:
    t = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode().lower()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in t).split())


def abbina(pagine: list[dict], clienti: dict[str, list[str]] = CLIENTI):
    """Restituisce (abbinate {slug: pagina}, mancanti [slug], doppie {slug: [nomi]})."""
    abbinate, mancanti, doppie = {}, [], {}
    for slug, parole in clienti.items():
        trovate = [p for p in pagine if any(normalizza(w) in normalizza(p["name"]) for w in parole)]
        if len(trovate) == 1:
            abbinate[slug] = trovate[0]
        elif not trovate:
            mancanti.append(slug)
        else:
            doppie[slug] = [p["name"] for p in trovate]
    return abbinate, mancanti, doppie


def aggiorna_config(config: dict, abbinate: dict[str, dict]) -> dict:
    """Aggiunge o aggiorna gli id; giorni e fascia delle stories esistenti restano com'erano."""
    nuovo = dict(config)
    for slug, p in abbinate.items():
        voce = dict(nuovo.get(slug, {"giorni_story": [], "fascia_story": [10, 15]}))
        voce["page_id"] = p["id"]
        ig = p.get("instagram_business_account") or {}
        voce["ig_user_id"] = ig.get("id", "")
        nuovo[slug] = {k: voce[k] for k in ("page_id", "ig_user_id", "giorni_story", "fascia_story")}
    return nuovo


# ---- chiamate a Meta (senza mai mostrare il token negli errori) ------------
def _get(percorso: str, params: dict) -> dict:
    try:
        r = requests.get(f"{GRAPH}/{percorso}", params=params, timeout=60)
    except requests.RequestException:
        raise Errore("non riesco a collegarmi a Meta: controlla la connessione") from None
    try:
        dati = r.json()
    except ValueError:
        dati = {}
    if r.status_code >= 400 or "error" in dati:
        raise Errore(dati.get("error", {}).get("message", f"errore HTTP {r.status_code}"))
    return dati


def scadenza(token: str) -> int:
    """0 = non scade; altrimenti il momento (secondi) in cui scade."""
    d = _get("debug_token", {"input_token": token, "access_token": token})["data"]
    if not d.get("is_valid"):
        raise Errore("il token non è valido (forse è già scaduto: generane uno nuovo)")
    return int(d.get("expires_at") or 0)


def allunga(token: str, segreto_app: str) -> str:
    return _get("oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": segreto_app,
        "fb_exchange_token": token,
    })["access_token"]


CAMPI_PAGINA = "id,name,access_token,instagram_business_account{id,username}"


def id_pagine_dei_permessi(dati_debug: dict) -> list[str]:
    """Pagine spuntate nella finestra dei permessi (utile per le pagine del portfolio aziendale)."""
    ids = []
    for g in dati_debug.get("granular_scopes", []):
        if g.get("scope", "").startswith("pages_"):
            for t in g.get("target_ids", []):
                if t not in ids:
                    ids.append(t)
    return ids


def pagine_del_token(token: str) -> list[dict]:
    dati = _get("me/accounts", {"fields": CAMPI_PAGINA, "limit": 100, "access_token": token})
    pagine = dati.get("data", [])
    visti = {p["id"] for p in pagine}
    debug = _get("debug_token", {"input_token": token, "access_token": token})["data"]
    for pid in id_pagine_dei_permessi(debug):
        if pid in visti:
            continue
        try:
            p = _get(pid, {"fields": CAMPI_PAGINA, "access_token": token})
        except Errore as e:
            print(f"  Pagina {pid}: non riesco a leggerla ({e})")
            continue
        if p.get("access_token"):
            pagine.append(p)
            visti.add(pid)
        else:
            print(f"  Pagina \"{p.get('name', pid)}\": Meta non dà la chiave (serve il controllo completo della pagina)")
    if not pagine:
        print(f"  Permessi nel token: {', '.join(debug.get('scopes', [])) or 'nessuno'}")
    return pagine


def dagli_appunti() -> str:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
        capture_output=True, text=True,
    )
    return (r.stdout or "").strip()


def chiedi_copiato(cosa: str) -> str:
    """Si copia il valore (pulsante copia o Ctrl+C) e si preme Invio: lo leggo dagli appunti."""
    input(f"Copia {cosa}, poi torna qui e premi Invio. ")
    valore = dagli_appunti()
    negli_appunti(" ")  # svuoto subito gli appunti
    return valore


def negli_appunti(testo: str):
    subprocess.run("clip", input=testo.encode("utf-8"), check=True, shell=True)


def main() -> int:
    radice = Path(__file__).resolve().parents[2]
    file_config = radice / "config" / "clienti.json"

    print("Niente da incollare: leggo io quello che copi.")
    token = chiedi_copiato("il token da Graph API Explorer (pulsante copia accanto ad Access Token)")
    if not token:
        print("Negli appunti non c'è niente: copia il token e rilancia lo script.")
        return 1

    try:
        fine = scadenza(token)
        if fine and fine - time.time() < 24 * 3600:
            print("\nQuesto token dura poche ore: lo allungo.")
            for tentativo in range(5):
                segreto = chiedi_copiato("la chiave segreta dell'app (Impostazioni dell'app > Di base > Chiave segreta > Mostra)")
                if len(segreto) != 32 or not segreto.isalnum():
                    print(f"  Negli appunti non c'è la chiave segreta (ho trovato {len(segreto)} caratteri, ne servono 32). Riprova.")
                    continue
                try:
                    token = allunga(token, segreto)
                    break
                except Errore as e:
                    print(f"  Meta non accetta la chiave segreta ({e}). Riprova.")
            else:
                raise Errore("chiave segreta non valida dopo 5 tentativi")
        pagine = pagine_del_token(token)
    except Errore as e:
        print(f"\nERRORE: {e}")
        return 1

    if not pagine:
        print("\nIl token non vede nessuna pagina. Rigeneralo spuntando le pagine dei clienti.")
        return 1

    config = json.loads(file_config.read_text(encoding="utf-8")) if file_config.exists() else {}
    per_id = {p["id"]: p for p in pagine}
    gia = {slug: per_id[v["page_id"]] for slug, v in config.items() if v.get("page_id") in per_id}
    resto = [p for p in pagine if p not in gia.values()]
    abbinate, mancanti, doppie = abbina(resto, {k: v for k, v in CLIENTI.items() if k not in gia})
    abbinate = {**gia, **abbinate}
    mancanti += list(doppie)
    doppie = {}
    for slug in list(mancanti):
        libere = [p for p in pagine if p not in abbinate.values()]
        if not libere:
            break
        print(f"\nQuale pagina è {slug}?")
        for i, p in enumerate(libere, 1):
            print(f"  {i}. {p['name']}")
        scelta = input("Scrivi il numero e premi Invio (solo Invio = nessuna): ").strip()
        if scelta.isdigit() and 1 <= int(scelta) <= len(libere):
            abbinate[slug] = libere[int(scelta) - 1]
            mancanti.remove(slug)

    print(f"\nPagine viste dal token: {len(pagine)}")
    for slug, p in abbinate.items():
        ig = (p.get("instagram_business_account") or {}).get("username")
        print(f"  OK  {slug}: pagina \"{p['name']}\", Instagram: {('@' + ig) if ig else 'NON COLLEGATO'}")
    for slug in mancanti:
        print(f"  --  {slug}: nessuna pagina trovata")
    for slug, nomi in doppie.items():
        print(f"  ??  {slug}: più pagine possibili ({', '.join(nomi)}), non scelgo da solo")
    altre = [p["name"] for p in pagine if p not in abbinate.values()]
    if altre:
        print("  Altre pagine viste: " + ", ".join(altre))

    # Controllo che ogni chiave di pagina funzioni e non scada
    chiavi = {}
    for slug, p in abbinate.items():
        try:
            if scadenza(p["access_token"]) != 0:
                print(f"  ATTENZIONE {slug}: la chiave di pagina ha una scadenza (il token non era allungato)")
            chiavi[slug] = p["access_token"]
        except Errore as e:
            print(f"  ERRORE {slug}: {e}")

    if not chiavi:
        print("\nNessuna chiave valida: mi fermo.")
        return 1

    config = aggiorna_config(config, {s: abbinate[s] for s in chiavi})
    file_config.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"\nId delle pagine salvati in {file_config}")

    negli_appunti(json.dumps(chiavi))
    print(f"\nLe chiavi di {len(chiavi)} pagine sono negli APPUNTI (non si vedono a schermo).")
    print("Ora su GitHub, nel segreto META_PAGE_TOKENS, fai Ctrl+V e salva.")
    print("Il nome META_PAGE_TOKENS scrivilo a mano: se lo copi, le chiavi negli appunti si perdono.")
    while input("Se le chiavi si sono perse scrivi R e premi Invio; quando hai salvato premi solo Invio: ").strip().lower() == "r":
        negli_appunti(json.dumps(chiavi))
        print("Chiavi rimesse negli appunti.")
    negli_appunti(" ")
    print("Appunti svuotati. Fatto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

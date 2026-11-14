"""Un giro di pubblicazione: legge le cartelle, pubblica ciò che è dovuto, sposta ciò che è uscito.

Uso: python -m pubblica.run --cliente <cliente> [--dry-run] [--solo-converti] [--now AAAA-MM-GGTHH:MM]
Codice di uscita 0 = tutto bene, 1 = almeno un problema (GitHub manda l'email di avviso).
"""
import argparse
import json
import os
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from .config import carica_config
from .contenuti import Contenuto
from .convert import ESTENSIONI_IMMAGINE, a_jpeg
from .mazzo import ScortaVuota, prossima_story
from .meta import MetaClient, MetaError
from .pianificatore import ROMA, cosa_e_dovuto

REPO = "lisantisocial/pubblicazione-social"
BASE_URL = f"https://raw.githubusercontent.com/{REPO}/main/"
VIDEO = {".mp4", ".mov"}


def _leggi_json(p: Path, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _scrivi_json(p: Path, dati):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def _url(radice: Path, p: Path) -> str:
    return BASE_URL + quote(p.relative_to(radice).as_posix())


def _converti_tutto(outbox: Path) -> int:
    n = 0
    for f in outbox.rglob("*"):
        if f.is_file() and f.suffix.lower() in ESTENSIONI_IMMAGINE and f.suffix.lower() != ".jpg":
            a_jpeg(f)
            n += 1
    return n


def _tenta(stato: dict, piattaforma: str, azione, errori: list[str], descrizione: str):
    """Esegue la pubblicazione su una piattaforma solo se non è già riuscita."""
    if stato.get(piattaforma):
        return
    try:
        stato[piattaforma] = azione()
        print(f"  {descrizione}: pubblicato su {'Instagram' if piattaforma == 'ig' else 'Facebook'}")
    except MetaError as e:
        errori.append(f"{descrizione}: errore su {'Instagram' if piattaforma == 'ig' else 'Facebook'}: {e.messaggio}")


def _pubblica_contenuto(client, radice: Path, c: Contenuto, errori: list[str]) -> bool:
    file_stato = c.cartella / ".stato.json"
    stato = _leggi_json(file_stato, {})
    urls = [_url(radice, m) for m in c.media]
    if c.video:
        cover = _url(radice, c.cover) if c.cover else None
        ig = lambda: client.ig_reel(urls[0], cover, c.testo)
        fb = lambda: client.fb_reel(urls[0], cover, c.testo)
    else:
        ig = lambda: client.ig_post(urls, c.testo)
        fb = lambda: client.fb_post(urls, c.testo)
    _tenta(stato, "ig", ig, errori, c.cartella.name)
    _scrivi_json(file_stato, stato)
    _tenta(stato, "fb", fb, errori, c.cartella.name)
    _scrivi_json(file_stato, stato)
    return bool(stato.get("ig") and stato.get("fb"))


def _pubblica_story(client, radice: Path, file: Path, stato: dict, errori: list[str], nome: str):
    video = file.suffix.lower() in VIDEO
    url = _url(radice, file)
    _tenta(stato, "ig", lambda: client.ig_story(url, video), errori, nome)
    _tenta(stato, "fb", lambda: client.fb_story(url, video), errori, nome)


def token_per(slug: str) -> str:
    """Chiave di pagina del cliente: dal segreto META_PAGE_TOKENS ({cliente: chiave}).
    Per Rigenera Lab vale ancora anche il vecchio segreto META_PAGE_TOKEN."""
    try:
        chiavi = json.loads(os.environ.get("META_PAGE_TOKENS") or "{}")
    except ValueError:
        chiavi = {}
    token = chiavi.get(slug, "") if isinstance(chiavi, dict) else ""
    if not token and slug == "rigenera-lab":
        token = os.environ.get("META_PAGE_TOKEN", "")
    return token


def main(argv: list[str] | None = None, client=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cliente", required=True)
    ap.add_argument("--radice", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--solo-converti", action="store_true")
    ap.add_argument("--verifica", action="store_true", help="solo lettura: controlla il collegamento a Meta")
    ap.add_argument("--now")
    a = ap.parse_args(argv)

    radice = Path(a.radice)
    cliente = carica_config(radice / "config" / "clienti.json")[a.cliente]
    outbox = radice / "outbox" / cliente.slug
    ora = datetime.fromisoformat(a.now).replace(tzinfo=ROMA) if a.now else datetime.now(ROMA)

    if a.verifica:
        if client is None:
            token = token_per(cliente.slug)
            if not token or not cliente.ig_user_id:
                print(f"ERRORE ({cliente.slug}): manca la chiave di Meta in META_PAGE_TOKENS o l'id Instagram")
                return 1
            client = MetaClient(token, cliente.page_id, cliente.ig_user_id)
        try:
            r = client.verifica()
        except MetaError as e:
            print(f"ERRORE: Meta risponde: {e.messaggio}")
            return 1
        print(f"{cliente.slug}: collegamento riuscito. Pagina Facebook: {r['pagina']}. Account Instagram: {r['instagram']}.")
        return 0

    if a.solo_converti:
        n = 0 if a.dry_run else _converti_tutto(outbox)
        print(f"Immagini convertite in JPEG: {n}")
        return 0

    errori: list[str] = []
    dovuti = cosa_e_dovuto(cliente, outbox, ora)

    # Problemi da segnalare una volta sola
    for p, motivo in dovuti.non_validi:
        errori.append(f"Contenuto non valido, non esce: {motivo}")
        if not a.dry_run:
            (p.parent / (p.name + ".avvisato") if p.is_file() else p / ".avvisato").write_text("avvisato", encoding="utf-8")
    for p in dovuti.scaduti:
        errori.append(f"Fascia oraria passata, non è uscito: {p.name}. Scegli una nuova data.")
        if not a.dry_run:
            dest = radice / "scaduti" / cliente.slug
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dest / p.name))

    if a.dry_run:
        for c in dovuti.post:
            print(f"[prova a vuoto] uscirebbe ora: {c.cartella.name} ({'reel' if c.video else str(len(c.media)) + ' immagini'})")
        if dovuti.story_datata:
            print(f"[prova a vuoto] uscirebbe ora la story datata: {dovuti.story_datata.file.name}")
        if dovuti.story_da_scorta:
            cartella = outbox / "stories-scorta" / (dovuti.mazzo_scorta or "")
            n = len([f for f in cartella.iterdir() if f.is_file() and f.name != ".gitkeep"]) if cartella.exists() else 0
            quale = f"dal mazzo «{dovuti.mazzo_scorta}»" if dovuti.mazzo_scorta else "dalla scorta"
            turno = f", story n. {dovuti.turno_scorta + 1} del giorno" if cliente.stories_al_giorno > 1 and not dovuti.mazzo_scorta else ""
            print(f"[prova a vuoto] uscirebbe ora una story {quale} ({n} grafiche{turno})")
        if not (dovuti.post or dovuti.story_datata or dovuti.story_da_scorta):
            print("[prova a vuoto] nessun contenuto dovuto in questo momento")
        for e in errori:
            print("AVVISO:", e)
        return 1 if errori else 0

    if client is None and (dovuti.post or dovuti.story_datata or dovuti.story_da_scorta):
        token = token_per(cliente.slug)
        if not token or not cliente.ig_user_id:
            errori.append(f"{cliente.slug}: manca la chiave di Meta in META_PAGE_TOKENS o l'id Instagram nel file clienti.json")
            for e in errori:
                print("ERRORE:", e)
            return 1
        client = MetaClient(token, cliente.page_id, cliente.ig_user_id)

    # Post, caroselli, reel
    for c in dovuti.post:
        print(f"Pubblico {c.cartella.name}")
        if _pubblica_contenuto(client, radice, c, errori):
            dest = radice / "published" / cliente.slug
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(c.cartella), str(dest / c.cartella.name))

    # Stories
    file_stories = radice / "state" / f"{cliente.slug}-stories.json"
    st = _leggi_json(file_stories, {"registro": {"mazzo": [], "ultima": None, "uscite": []}, "giorni": {}, "datate": {}})

    if dovuti.story_datata:
        s = dovuti.story_datata
        stato = st["datate"].setdefault(s.file.name, {})
        print(f"Pubblico la story datata {s.file.name}")
        _pubblica_story(client, radice, s.file, stato, errori, s.file.name)
        if stato.get("ig") and stato.get("fb"):
            dest = radice / "published" / cliente.slug / "stories"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(s.file), str(dest / s.file.name))
            del st["datate"][s.file.name]
        _scrivi_json(file_stories, st)

    if dovuti.story_da_scorta:
        oggi = ora.date().isoformat()
        # la prima story del giorno resta sotto la data (come prima), le altre sotto data#2, data#3…
        chiave = oggi if dovuti.turno_scorta == 0 else f"{oggi}#{dovuti.turno_scorta + 1}"
        voce = st["giorni"].get(chiave)
        if voce and voce.get("ig") and voce.get("fb"):
            pass  # già uscita oggi su entrambe
        else:
            mazzo = dovuti.mazzo_scorta or ""
            if voce and voce.get("mazzo", "") != mazzo:
                voce = None  # tentativo fallito di un altro mazzo: si riparte da questo
            cartella_scorta = outbox / "stories-scorta" / mazzo if mazzo else outbox / "stories-scorta"
            nomi = sorted(f.name for f in cartella_scorta.iterdir() if f.is_file() and f.name != ".gitkeep") if cartella_scorta.exists() else []
            vuoto = {"mazzo": [], "ultima": None, "uscite": []}
            registro = st.setdefault("registri", {}).get(mazzo, vuoto) if mazzo else st["registro"]
            try:
                if voce:
                    nome, nuovo_reg = voce["file"], registro
                else:
                    nome, nuovo_reg = prossima_story(nomi, registro, random.Random(), oggi)
                    voce = {"file": nome, "mazzo": mazzo} if mazzo else {"file": nome}
                print(f"Pubblico la story dalla scorta: {nome}")
                _pubblica_story(client, radice, cartella_scorta / nome, voce, errori, f"story {nome}")
                if voce.get("ig") or voce.get("fb"):
                    st["giorni"][chiave] = voce
                    if mazzo:
                        st["registri"][mazzo] = nuovo_reg
                    else:
                        st["registro"] = nuovo_reg
                _scrivi_json(file_stories, st)
            except ScortaVuota:
                quale = f"Il mazzo di stories «{mazzo}» è vuoto" if mazzo else "La scorta delle stories è vuota"
                errori.append(f"{quale}: oggi non esce nessuna story")

    for e in errori:
        print("ERRORE:", e)
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())

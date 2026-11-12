import json
import time
from typing import Callable

import requests

GRAPH_VERSION = "v23.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"


class MetaError(Exception):
    def __init__(self, messaggio: str, codice: int | None = None):
        super().__init__(messaggio)
        self.messaggio = messaggio
        self.codice = codice


class MetaClient:
    def __init__(
        self,
        token: str,
        page_id: str,
        ig_user_id: str,
        sessione: requests.Session | None = None,
        pausa: Callable[[float], None] = time.sleep,
    ):
        self.token = token
        self.page_id = page_id
        self.ig_user_id = ig_user_id
        self.http = sessione or requests.Session()
        self.pausa = pausa

    # ---- chiamate di base -------------------------------------------------
    def _controlla(self, r: requests.Response) -> dict:
        try:
            dati = r.json()
        except ValueError:
            dati = {}
        if r.status_code >= 400 or "error" in dati:
            err = dati.get("error", {}) if isinstance(dati, dict) else {}
            raise MetaError(err.get("message", f"errore HTTP {r.status_code}"), err.get("code"))
        return dati

    def _post(self, percorso: str, dati: dict) -> dict:
        dati = {**dati, "access_token": self.token}
        return self._controlla(self.http.post(f"{GRAPH}/{percorso}", data=dati, timeout=120))

    def _get(self, percorso: str, params: dict | None = None) -> dict:
        params = {**(params or {}), "access_token": self.token}
        return self._controlla(self.http.get(f"{GRAPH}/{percorso}", params=params, timeout=60))

    # ---- Facebook (pagina) --------------------------------------------------
    def fb_post(self, urls: list[str], testo: str) -> str:
        if len(urls) == 1:
            r = self._post(f"{self.page_id}/photos", {"url": urls[0], "message": testo, "published": "true"})
            return r.get("post_id") or r["id"]
        dati = {"message": testo}
        for i, u in enumerate(urls):
            foto = self._post(f"{self.page_id}/photos", {"url": u, "published": "false"})["id"]
            dati[f"attached_media[{i}]"] = json.dumps({"media_fbid": foto})
        return self._post(f"{self.page_id}/feed", dati)["id"]

    def _fb_video(self, endpoint: str, video_url: str, chiusura: dict) -> str:
        """Caricamento in tre fasi (avvio, file da link pubblico, chiusura) per reel e video stories."""
        avvio = self._post(f"{self.page_id}/{endpoint}", {"upload_phase": "start"})
        video_id = avvio["video_id"]
        r = self.http.post(
            avvio["upload_url"],
            headers={"Authorization": f"OAuth {self.token}", "file_url": video_url},
            timeout=300,
        )
        self._controlla(r)
        self._post(f"{self.page_id}/{endpoint}", {"upload_phase": "finish", "video_id": video_id, **chiusura})
        return video_id

    def fb_reel(self, video_url: str, cover_url: str | None, testo: str) -> str:
        # La copertina del reel su Facebook non ha un parametro nell'API di caricamento da link:
        # cover_url è accettato per simmetria con Instagram ma per ora non viene inviato.
        return self._fb_video("video_reels", video_url, {"video_state": "PUBLISHED", "description": testo})

    def fb_story(self, url: str, video: bool) -> str:
        if video:
            return self._fb_video("video_stories", url, {})
        foto = self._post(f"{self.page_id}/photos", {"url": url, "published": "false"})["id"]
        r = self._post(f"{self.page_id}/photo_stories", {"photo_id": foto})
        return r.get("post_id") or foto

    # ---- Instagram ----------------------------------------------------------
    def _ig_attendi(self, contenitore: str, tentativi: int = 30, secondi: float = 10) -> None:
        for _ in range(tentativi):
            stato = self._get(contenitore, {"fields": "status_code"}).get("status_code")
            if stato == "FINISHED":
                return
            if stato in ("ERROR", "EXPIRED"):
                raise MetaError(f"Instagram non ha accettato il file (stato {stato})")
            self.pausa(secondi)
        raise MetaError("Instagram non ha finito di elaborare il file in tempo")

    def _ig_crea(self, dati: dict) -> str:
        contenitore = self._post(f"{self.ig_user_id}/media", dati)["id"]
        self._ig_attendi(contenitore)
        return contenitore

    def _ig_pubblica(self, contenitore: str) -> str:
        return self._post(f"{self.ig_user_id}/media_publish", {"creation_id": contenitore})["id"]

    def ig_post(self, urls: list[str], didascalia: str) -> str:
        if len(urls) == 1:
            c = self._ig_crea({"image_url": urls[0], "caption": didascalia})
        else:
            figli = [self._ig_crea({"image_url": u, "is_carousel_item": "true"}) for u in urls]
            c = self._ig_crea({"media_type": "CAROUSEL", "children": ",".join(figli), "caption": didascalia})
        return self._ig_pubblica(c)

    def ig_reel(self, video_url: str, cover_url: str | None, didascalia: str) -> str:
        dati = {"media_type": "REELS", "video_url": video_url, "caption": didascalia, "share_to_feed": "true"}
        if cover_url:
            dati["cover_url"] = cover_url
        return self._ig_pubblica(self._ig_crea(dati))

    def ig_story(self, url: str, video: bool) -> str:
        dati = {"media_type": "STORIES", ("video_url" if video else "image_url"): url}
        return self._ig_pubblica(self._ig_crea(dati))

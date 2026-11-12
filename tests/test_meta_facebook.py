import json
from urllib.parse import parse_qs

import requests
import responses

from pubblica.meta import MetaClient

P = "https://graph.facebook.com/v23.0/page1"
UP = "https://rupload.facebook.com/video-upload/v23.0/vid1"


def client():
    return MetaClient("TOKEN", "page1", "ig1", requests.Session(), pausa=lambda s: None)


def corpo(call):
    return {k: v[0] for k, v in parse_qs(call.request.body).items()}


@responses.activate
def test_foto_singola():
    responses.add(responses.POST, f"{P}/photos", json={"id": "ph1", "post_id": "page1_ph1"})
    assert client().fb_post(["https://x/1.jpg"], "Ciao\n\nTesto") == "page1_ph1"
    b = corpo(responses.calls[0])
    assert b["url"] == "https://x/1.jpg" and b["message"] == "Ciao\n\nTesto" and b["published"] == "true"


@responses.activate
def test_piu_foto_usano_attached_media_in_ordine():
    ids = iter(["a", "b"])
    responses.add_callback(responses.POST, f"{P}/photos", callback=lambda r: (200, {}, '{"id": "%s"}' % next(ids)))
    responses.add(responses.POST, f"{P}/feed", json={"id": "post9"})
    assert client().fb_post(["https://x/1.jpg", "https://x/2.jpg"], "T") == "post9"
    foto = [corpo(c) for c in responses.calls[:2]]
    assert all(f["published"] == "false" for f in foto)
    feed = corpo(responses.calls[2])
    assert json.loads(feed["attached_media[0]"]) == {"media_fbid": "a"}
    assert json.loads(feed["attached_media[1]"]) == {"media_fbid": "b"}
    assert feed["message"] == "T"


def _reel_mock():
    responses.add(responses.POST, f"{P}/video_reels", json={"video_id": "vid1", "upload_url": UP})
    responses.add(responses.POST, UP, json={"success": True})


@responses.activate
def test_reel_tre_fasi():
    _reel_mock()
    assert client().fb_reel("https://x/v.mp4", "https://x/c.jpg", "Descr") == "vid1"
    avvio, caricamento, chiusura = responses.calls
    assert corpo(avvio)["upload_phase"] == "start"
    assert caricamento.request.headers["file_url"] == "https://x/v.mp4"
    assert caricamento.request.headers["Authorization"] == "OAuth TOKEN"
    c = corpo(chiusura)
    assert c["upload_phase"] == "finish" and c["video_state"] == "PUBLISHED"
    assert c["video_id"] == "vid1" and c["description"] == "Descr"


@responses.activate
def test_reel_senza_cover():
    _reel_mock()
    assert client().fb_reel("https://x/v.mp4", None, "D") == "vid1"


@responses.activate
def test_story_foto():
    responses.add(responses.POST, f"{P}/photos", json={"id": "ph1"})
    responses.add(responses.POST, f"{P}/photo_stories", json={"success": True, "post_id": "st1"})
    assert client().fb_story("https://x/s.jpg", False) == "st1"
    assert corpo(responses.calls[0])["published"] == "false"
    assert corpo(responses.calls[1])["photo_id"] == "ph1"


@responses.activate
def test_story_video():
    responses.add(responses.POST, f"{P}/video_stories", json={"video_id": "vid1", "upload_url": UP})
    responses.add(responses.POST, UP, json={"success": True})
    assert client().fb_story("https://x/s.mp4", True) == "vid1"
    assert corpo(responses.calls[0])["upload_phase"] == "start"
    assert corpo(responses.calls[2])["upload_phase"] == "finish"


@responses.activate
def test_testo_identico_a_instagram():
    testo = "Riga uno\n\n\nRiga due 🌿 è à\n"
    responses.add(responses.POST, f"{P}/photos", json={"id": "ph1", "post_id": "p"})
    responses.add(responses.POST, "https://graph.facebook.com/v23.0/ig1/media", json={"id": "c1"})
    responses.add(responses.GET, "https://graph.facebook.com/v23.0/c1", json={"status_code": "FINISHED"})
    responses.add(responses.POST, "https://graph.facebook.com/v23.0/ig1/media_publish", json={"id": "m"})
    c = client()
    c.fb_post(["https://x/1.jpg"], testo)
    c.ig_post(["https://x/1.jpg"], testo)
    assert corpo(responses.calls[0])["message"] == testo == corpo(responses.calls[1])["caption"]

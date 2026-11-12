from urllib.parse import parse_qs, urlparse

import pytest
import requests
import responses

from pubblica.meta import MetaClient, MetaError

IG = "ig123"


def client():
    return MetaClient("TOKEN", "page1", IG, requests.Session(), pausa=lambda s: None)


def corpo(call):
    return {k: v[0] for k, v in parse_qs(call.request.body).items()}


def percorsi(rsps):
    return [(c.request.method, urlparse(c.request.url).path.split("/", 2)[2]) for c in rsps.calls]


def stato_ok(rsps, cid):
    rsps.add(responses.GET, f"https://graph.facebook.com/v23.0/{cid}", json={"status_code": "FINISHED"})


@responses.activate
def test_post_singolo_crea_contenitore_poi_pubblica():
    responses.add(responses.POST, f"https://graph.facebook.com/v23.0/{IG}/media", json={"id": "c1"})
    stato_ok(responses, "c1")
    responses.add(responses.POST, f"https://graph.facebook.com/v23.0/{IG}/media_publish", json={"id": "m1"})
    assert client().ig_post(["https://x/1.jpg"], "Ciao") == "m1"
    assert percorsi(responses) == [("POST", f"{IG}/media"), ("GET", "c1"), ("POST", f"{IG}/media_publish")]
    assert corpo(responses.calls[0])["image_url"] == "https://x/1.jpg"
    assert corpo(responses.calls[2])["creation_id"] == "c1"


@responses.activate
def test_carosello_crea_figli_poi_contenitore_poi_pubblica():
    ids = iter(["f1", "f2", "car"])
    responses.add_callback(
        responses.POST,
        f"https://graph.facebook.com/v23.0/{IG}/media",
        callback=lambda r: (200, {}, '{"id": "%s"}' % next(ids)),
    )
    for cid in ("f1", "f2", "car"):
        stato_ok(responses, cid)
    responses.add(responses.POST, f"https://graph.facebook.com/v23.0/{IG}/media_publish", json={"id": "m2"})
    assert client().ig_post(["https://x/1.jpg", "https://x/2.jpg"], "Testo") == "m2"
    creati = [corpo(c) for c in responses.calls if c.request.method == "POST" and c.request.url.endswith("/media")]
    assert creati[0]["is_carousel_item"] == "true" and creati[0]["image_url"] == "https://x/1.jpg"
    assert creati[1]["image_url"] == "https://x/2.jpg"
    assert creati[2]["media_type"] == "CAROUSEL" and creati[2]["children"] == "f1,f2"
    assert creati[2]["caption"] == "Testo"


@responses.activate
def test_reel_usa_cover_url_e_share_to_feed():
    responses.add(responses.POST, f"https://graph.facebook.com/v23.0/{IG}/media", json={"id": "r1"})
    stato_ok(responses, "r1")
    responses.add(responses.POST, f"https://graph.facebook.com/v23.0/{IG}/media_publish", json={"id": "m3"})
    client().ig_reel("https://x/v.mp4", "https://x/cover.jpg", "T")
    b = corpo(responses.calls[0])
    assert b["media_type"] == "REELS" and b["video_url"] == "https://x/v.mp4"
    assert b["cover_url"] == "https://x/cover.jpg" and b["share_to_feed"] == "true"


@responses.activate
def test_reel_senza_cover_non_invia_cover_url():
    responses.add(responses.POST, f"https://graph.facebook.com/v23.0/{IG}/media", json={"id": "r1"})
    stato_ok(responses, "r1")
    responses.add(responses.POST, f"https://graph.facebook.com/v23.0/{IG}/media_publish", json={"id": "m3"})
    client().ig_reel("https://x/v.mp4", None, "T")
    assert "cover_url" not in corpo(responses.calls[0])


@responses.activate
@pytest.mark.parametrize("video,chiave", [(False, "image_url"), (True, "video_url")])
def test_story_con_media_type_stories(video, chiave):
    responses.add(responses.POST, f"https://graph.facebook.com/v23.0/{IG}/media", json={"id": "s1"})
    stato_ok(responses, "s1")
    responses.add(responses.POST, f"https://graph.facebook.com/v23.0/{IG}/media_publish", json={"id": "m4"})
    client().ig_story("https://x/s", video)
    b = corpo(responses.calls[0])
    assert b["media_type"] == "STORIES" and b[chiave] == "https://x/s"


@responses.activate
def test_errore_17_solleva_meta_error_con_codice():
    responses.add(
        responses.POST,
        f"https://graph.facebook.com/v23.0/{IG}/media",
        status=400,
        json={"error": {"code": 17, "message": "User request limit reached"}},
    )
    with pytest.raises(MetaError) as e:
        client().ig_post(["https://x/1.jpg"], "T")
    assert e.value.codice == 17


@responses.activate
def test_contenitore_in_errore_solleva():
    responses.add(responses.POST, f"https://graph.facebook.com/v23.0/{IG}/media", json={"id": "c1"})
    responses.add(responses.GET, "https://graph.facebook.com/v23.0/c1", json={"status_code": "ERROR"})
    with pytest.raises(MetaError):
        client().ig_post(["https://x/1.jpg"], "T")


@responses.activate
def test_didascalia_inviata_identica():
    testo = "Riga uno\n\n\nRiga due 🌿 è à\n"
    responses.add(responses.POST, f"https://graph.facebook.com/v23.0/{IG}/media", json={"id": "c1"})
    stato_ok(responses, "c1")
    responses.add(responses.POST, f"https://graph.facebook.com/v23.0/{IG}/media_publish", json={"id": "m1"})
    client().ig_post(["https://x/1.jpg"], testo)
    assert corpo(responses.calls[0])["caption"] == testo

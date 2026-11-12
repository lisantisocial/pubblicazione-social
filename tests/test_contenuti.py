from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from pubblica.contenuti import (
    ContenutoNonValido,
    leggi_contenuto,
    leggi_story_datata,
)
from pubblica.convert import a_jpeg


def _img(p: Path, fmt="JPEG"):
    Image.new("RGB", (20, 20), "red").save(p, fmt)


def _cartella(tmp_path, nome="2026-11-18_16-19_pronuncia", immagini=("1.jpg", "2.jpg"), testo="Ciao\n\nSecondo paragrafo\n"):
    c = tmp_path / nome
    c.mkdir()
    for i in immagini:
        _img(c / i)
    if testo is not None:
        (c / "testo.txt").write_bytes(testo.encode("utf-8"))
    return c


def test_png_diventa_jpg(tmp_path):
    png = tmp_path / "a.png"
    _img(png, "PNG")
    out = a_jpeg(png)
    assert out.suffix == ".jpg" and out.exists() and not png.exists()
    assert Image.open(out).format == "JPEG"


def test_jpg_resta_invariato(tmp_path):
    jpg = tmp_path / "a.jpg"
    _img(jpg)
    assert a_jpeg(jpg) == jpg


def test_leggi_carosello_ordina_per_numero(tmp_path):
    c = _cartella(tmp_path, immagini=("1.jpg", "2.jpg", "10.jpg"))
    r = leggi_contenuto(c)
    assert [m.name for m in r.media] == ["1.jpg", "2.jpg", "10.jpg"]
    assert r.data == date(2026, 11, 18) and r.fascia == (16, 19) and not r.video


def test_leggi_reel_con_e_senza_cover(tmp_path):
    c = _cartella(tmp_path, immagini=())
    (c / "video.mp4").write_bytes(b"x")
    assert leggi_contenuto(c).cover is None
    _img(c / "cover.jpg")
    r = leggi_contenuto(c)
    assert r.video and r.cover.name == "cover.jpg" and [m.name for m in r.media] == ["video.mp4"]


def test_testo_con_righe_vuote_invariato(tmp_path):
    testo = "Riga uno\n\n\nRiga due 🌿\n"
    r = leggi_contenuto(_cartella(tmp_path, testo=testo))
    assert r.testo == testo


def test_11_immagini_rifiutato(tmp_path):
    c = _cartella(tmp_path, immagini=tuple(f"{i}.jpg" for i in range(1, 12)))
    with pytest.raises(ContenutoNonValido, match="10"):
        leggi_contenuto(c)


@pytest.mark.parametrize("testo", ["Ciao #salute", "#uno"])
def test_hashtag_rifiutato(tmp_path, testo):
    with pytest.raises(ContenutoNonValido, match="hashtag"):
        leggi_contenuto(_cartella(tmp_path, testo=testo))


def test_nome_non_sicuro_rifiutato(tmp_path):
    c = _cartella(tmp_path, nome="2026-11-18_16-19_Città con spazi")
    with pytest.raises(ContenutoNonValido, match="nome"):
        leggi_contenuto(c)


def test_testo_mancante_rifiutato(tmp_path):
    with pytest.raises(ContenutoNonValido, match="testo"):
        leggi_contenuto(_cartella(tmp_path, testo=None))


def test_story_datata(tmp_path):
    f = tmp_path / "2026-12-08_10-15_evento.jpg"
    _img(f)
    s = leggi_story_datata(f)
    assert s.data == date(2026, 12, 8) and s.fascia == (10, 15) and s.file == f

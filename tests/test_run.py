import json
from pathlib import Path

import pytest
from PIL import Image

from pubblica.meta import MetaError
from pubblica.run import main

BASE = "https://raw.githubusercontent.com/lisantisocial/pubblicazione-social/main/"


class Finto:
    def __init__(self, falliscono=()):
        self.calls = []
        self.falliscono = set(falliscono)

    def _f(self, nome, *args):
        self.calls.append((nome, *args))
        if nome in self.falliscono:
            raise MetaError("finto errore", 17)
        return f"id-{nome}-{len(self.calls)}"

    def ig_post(self, *a): return self._f("ig_post", *a)
    def ig_reel(self, *a): return self._f("ig_reel", *a)
    def ig_story(self, *a): return self._f("ig_story", *a)
    def fb_post(self, *a): return self._f("fb_post", *a)
    def fb_reel(self, *a): return self._f("fb_reel", *a)
    def fb_story(self, *a): return self._f("fb_story", *a)

    def nomi(self):
        return [c[0] for c in self.calls]


@pytest.fixture
def radice(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "clienti.json").write_text(
        json.dumps({"rigenera-lab": {"page_id": "p1", "ig_user_id": "ig1", "giorni_story": [0, 2, 3, 4], "fascia_story": [10, 15]}}),
        encoding="utf-8",
    )
    for d in ("post", "stories-scorta", "stories-datate"):
        (tmp_path / "outbox" / "rigenera-lab" / d).mkdir(parents=True)
    (tmp_path / "state").mkdir()
    return tmp_path


def post(radice, nome="2026-11-18_16-19_a", testo="Ciao\n\nMondo"):
    c = radice / "outbox" / "rigenera-lab" / "post" / nome
    c.mkdir()
    Image.new("RGB", (5, 5)).save(c / "1.jpg")
    (c / "testo.txt").write_bytes(testo.encode())
    return c


def scorta(radice, n=3):
    d = radice / "outbox" / "rigenera-lab" / "stories-scorta"
    for i in range(n):
        Image.new("RGB", (5, 5)).save(d / f"s{i}.jpg")


def esegui(radice, ora, client=None, *extra, token="T"):
    import os
    if token:
        os.environ["META_PAGE_TOKEN"] = token
    else:
        os.environ.pop("META_PAGE_TOKEN", None)
    return main(["--radice", str(radice), "--cliente", "rigenera-lab", "--now", ora, *extra], client=client)


def test_post_dovuto_pubblicato_su_ig_e_fb_poi_spostato(radice):
    c = post(radice)
    f = Finto()
    assert esegui(radice, "2026-11-18T16:30", f) == 0
    url = BASE + "outbox/rigenera-lab/post/2026-11-18_16-19_a/1.jpg"
    assert f.calls == [("ig_post", [url], "Ciao\n\nMondo"), ("fb_post", [url], "Ciao\n\nMondo")]
    assert not c.exists() and (radice / "published" / "rigenera-lab" / c.name).exists()


def test_reel_con_cover(radice):
    c = radice / "outbox" / "rigenera-lab" / "post" / "2026-11-18_16-19_reel"
    c.mkdir()
    (c / "video.mp4").write_bytes(b"v")
    Image.new("RGB", (5, 5)).save(c / "cover.jpg")
    (c / "testo.txt").write_text("T")
    f = Finto()
    assert esegui(radice, "2026-11-18T17:00", f) == 0
    p = BASE + "outbox/rigenera-lab/post/2026-11-18_16-19_reel/"
    assert f.calls == [("ig_reel", p + "video.mp4", p + "cover.jpg", "T"), ("fb_reel", p + "video.mp4", p + "cover.jpg", "T")]


def test_dry_run_non_chiama_meta_e_non_sposta(radice):
    c = post(radice)
    f = Finto()
    assert esegui(radice, "2026-11-18T16:30", f, "--dry-run") == 0
    assert f.calls == [] and c.exists()


def test_scaduto_non_pubblica_e_restituisce_1(radice):
    c = post(radice, "2026-11-17_16-19_a")
    f = Finto()
    assert esegui(radice, "2026-11-18T16:30", f) == 1
    assert f.calls == [] and (radice / "scaduti" / "rigenera-lab" / c.name).exists()
    assert esegui(radice, "2026-11-18T17:00", f) == 0  # avvisato una volta sola


def test_errore_ig_non_sposta_e_al_giro_dopo_non_ripubblica_fb(radice):
    c = post(radice)
    assert esegui(radice, "2026-11-18T16:30", Finto(falliscono={"ig_post"})) == 1
    assert c.exists()
    f2 = Finto()
    assert esegui(radice, "2026-11-18T17:00", f2) == 0
    assert f2.nomi() == ["ig_post"] and not c.exists()


def test_giro_ripetuto_non_pubblica_due_volte(radice):
    post(radice)
    f = Finto()
    esegui(radice, "2026-11-18T16:30", f)
    esegui(radice, "2026-11-18T17:00", f)
    assert f.nomi() == ["ig_post", "fb_post"]


def test_story_da_scorta_una_volta_al_giorno_e_aggiorna_registro(radice):
    scorta(radice)
    f = Finto()
    assert esegui(radice, "2026-11-18T11:00", f) == 0
    assert f.nomi() == ["ig_story", "fb_story"]
    assert f.calls[0][1].startswith(BASE + "outbox/rigenera-lab/stories-scorta/s")
    assert f.calls[0][2] is False
    esegui(radice, "2026-11-18T11:30", f)
    assert len(f.calls) == 2
    reg = json.loads((radice / "state" / "rigenera-lab-stories.json").read_text())["registro"]
    assert [u["data"] for u in reg["uscite"]] == ["2026-11-18"]


def test_stories_di_giorni_diversi_non_ripetono(radice):
    scorta(radice)
    f = Finto()
    for g in ("2026-11-18", "2026-11-19", "2026-11-20"):
        esegui(radice, g + "T11:00", f)
    usate = [c[1] for c in f.calls if c[0] == "ig_story"]
    assert len(set(usate)) == 3


def test_story_con_errore_non_aggiorna_registro_e_riprova_nella_fascia(radice):
    scorta(radice)
    assert esegui(radice, "2026-11-18T11:00", Finto(falliscono={"ig_story", "fb_story"})) == 1
    p = radice / "state" / "rigenera-lab-stories.json"
    assert not p.exists() or json.loads(p.read_text())["registro"]["uscite"] == []
    f = Finto()
    assert esegui(radice, "2026-11-18T11:30", f) == 0 and f.nomi() == ["ig_story", "fb_story"]


def test_story_datata_ha_precedenza_ed_esce_di_martedi(radice):
    scorta(radice)
    d = radice / "outbox" / "rigenera-lab" / "stories-datate" / "2026-11-17_10-15_evento.jpg"
    Image.new("RGB", (5, 5)).save(d)
    f = Finto()
    assert esegui(radice, "2026-11-17T11:00", f) == 0
    assert f.nomi() == ["ig_story", "fb_story"] and "stories-datate" in f.calls[0][1]
    assert not d.exists() and (radice / "published" / "rigenera-lab" / "stories" / d.name).exists()


def test_scorta_vuota_restituisce_1(radice):
    f = Finto()
    assert esegui(radice, "2026-11-18T11:00", f) == 1 and f.calls == []


def test_nessun_dovuto_restituisce_0(radice):
    f = Finto()
    assert esegui(radice, "2026-11-17T11:00", f) == 0 and f.calls == []


def test_non_valido_avvisa_una_volta_e_non_esce(radice):
    c = post(radice, testo="ciao #salute")
    f = Finto()
    assert esegui(radice, "2026-11-18T16:30", f) == 1
    assert (c / ".avvisato").exists() and f.calls == []
    assert esegui(radice, "2026-11-18T17:00", f) == 0


def test_solo_converti_trasforma_png_in_jpg(radice):
    c = post(radice)
    Image.new("RGB", (5, 5)).save(c / "2.png")
    assert esegui(radice, "2026-11-18T09:00", Finto(), "--solo-converti") == 0
    assert (c / "2.jpg").exists() and not (c / "2.png").exists()


def test_verifica_non_pubblica_e_restituisce_0(radice, capsys):
    class Lettore(Finto):
        def verifica(self):
            return {"pagina": "Rigenera", "instagram": "rigenera_valcamonica"}

    f = Lettore()
    post(radice)
    assert esegui(radice, "2026-11-18T16:30", f, "--verifica") == 0
    assert f.calls == []
    assert "rigenera-lab: collegamento riuscito" in capsys.readouterr().out


def test_senza_token_restituisce_1(radice):
    post(radice)
    assert esegui(radice, "2026-11-18T16:30", None, token=None) == 1


def test_mazzo_sottocartella_con_registro_proprio(radice):
    cfg = radice / "config" / "clienti.json"
    dati = json.loads(cfg.read_text())
    dati["rigenera-lab"]["mazzi_story"] = {"01-carosello": {"giorni": [5, 6], "fascia": [11, 19]}}
    cfg.write_text(json.dumps(dati), encoding="utf-8")
    scorta(radice)
    m = radice / "outbox" / "rigenera-lab" / "stories-scorta" / "01-carosello"
    m.mkdir()
    for i in range(2):
        Image.new("RGB", (5, 5)).save(m / f"c{i}.jpg")
    f = Finto()
    assert esegui(radice, "2026-11-21T11:30", f) == 0  # sabato
    assert esegui(radice, "2026-11-22T12:00", f) == 0  # domenica
    usate = [c[1] for c in f.calls if c[0] == "ig_story"]
    assert len(usate) == 2 and len(set(usate)) == 2
    assert all(u.startswith(BASE + "outbox/rigenera-lab/stories-scorta/01-carosello/c") for u in usate)
    assert esegui(radice, "2026-11-23T11:00", f) == 0  # lunedì: scorta generale, non il carosello
    assert "/stories-scorta/s" in f.calls[-2][1]
    st = json.loads((radice / "state" / "rigenera-lab-stories.json").read_text())
    assert len(st["registri"]["01-carosello"]["uscite"]) == 2
    assert len(st["registro"]["uscite"]) == 1


def test_due_stories_al_giorno_diverse(radice):
    cfg = radice / "config" / "clienti.json"
    dati = json.loads(cfg.read_text())
    dati["rigenera-lab"].update({"fascia_story": [14, 21], "stories_al_giorno": 2})
    cfg.write_text(json.dumps(dati))
    scorta(radice, 5)
    f = Finto()
    for t in ("14:00", "14:30", "17:30", "18:00", "20:30"):
        assert esegui(radice, "2026-11-18T" + t, f) == 0
    usate = [c[1] for c in f.calls if c[0] == "ig_story"]
    assert len(usate) == 2 and len(set(usate)) == 2
    st = json.loads((radice / "state" / "rigenera-lab-stories.json").read_text())
    assert set(st["giorni"]) == {"2026-11-18", "2026-11-18#2"}

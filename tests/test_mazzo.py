import random

import pytest

from pubblica.mazzo import ScortaVuota, prossima_story

NUOVO = {"mazzo": [], "ultima": None, "uscite": []}


def _estrai(scorta, n, registro=None, seed=1):
    reg = registro or dict(NUOVO, uscite=[])
    rng = random.Random(seed)
    scelte = []
    for i in range(n):
        f, reg = prossima_story(scorta, reg, rng, f"2026-11-{i + 1:02d}")
        scelte.append(f)
    return scelte, reg


def test_nessuna_ripetizione_nel_giro():
    scorta = [f"{i}.jpg" for i in range(30)]
    scelte, _ = _estrai(scorta, 30)
    assert sorted(scelte) == sorted(scorta)


def test_primo_del_nuovo_giro_diverso_dall_ultimo():
    scorta = ["a.jpg", "b.jpg", "c.jpg"]
    for seed in range(200):
        scelte, _ = _estrai(scorta, 6, seed=seed)
        assert scelte[2] != scelte[3]


def test_file_aggiunto_entra_nel_giro_successivo():
    scorta = ["a.jpg", "b.jpg", "c.jpg"]
    rng = random.Random(3)
    reg = dict(NUOVO, uscite=[])
    f1, reg = prossima_story(scorta, reg, rng, "2026-11-01")
    scorta2 = scorta + ["nuova.jpg"]
    f2, reg = prossima_story(scorta2, reg, rng, "2026-11-02")
    f3, reg = prossima_story(scorta2, reg, rng, "2026-11-03")
    assert "nuova.jpg" not in (f1, f2, f3)
    giro = []
    for i in range(4):
        f, reg = prossima_story(scorta2, reg, rng, f"2026-12-{i + 1:02d}")
        giro.append(f)
    assert "nuova.jpg" in giro


def test_file_tolto_non_esce_piu():
    scorta = ["a.jpg", "b.jpg", "c.jpg"]
    rng = random.Random(5)
    reg = dict(NUOVO, uscite=[])
    _, reg = prossima_story(scorta, reg, rng, "2026-11-01")
    ridotta = [f for f in scorta if f != "b.jpg"]
    for i in range(6):
        f, reg = prossima_story(ridotta, reg, rng, f"2026-12-{i + 1:02d}")
        assert f != "b.jpg"


def test_scorta_di_un_file():
    scelte, _ = _estrai(["solo.jpg"], 3)
    assert scelte == ["solo.jpg"] * 3


def test_scorta_vuota_solleva():
    with pytest.raises(ScortaVuota):
        prossima_story([], dict(NUOVO, uscite=[]), random.Random(1), "2026-11-01")


def test_registro_tiene_traccia():
    _, reg = _estrai(["a.jpg", "b.jpg"], 2)
    assert [u["data"] for u in reg["uscite"]] == ["2026-11-01", "2026-11-02"]
    assert reg["ultima"] == reg["uscite"][-1]["file"]

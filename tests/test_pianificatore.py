from datetime import date, datetime
from zoneinfo import ZoneInfo

from PIL import Image

from pubblica.config import Cliente
from pubblica.pianificatore import cosa_e_dovuto, stato_fascia

ROMA = ZoneInfo("Europe/Rome")
CLIENTE = Cliente("rigenera-lab", "1", "2", [0, 2, 3, 4], (10, 15))


def ora(s):
    return datetime.fromisoformat(s).replace(tzinfo=ROMA)


def _post(radice, nome, testo="Ciao"):
    c = radice / "post" / nome
    c.mkdir(parents=True)
    Image.new("RGB", (5, 5)).save(c / "1.jpg")
    (c / "testo.txt").write_text(testo, encoding="utf-8")
    return c


def _story_datata(radice, nome):
    d = radice / "stories-datate"
    d.mkdir(parents=True, exist_ok=True)
    f = d / nome
    Image.new("RGB", (5, 5)).save(f)
    return f


def test_giro_dentro_fascia_pubblica(tmp_path):
    _post(tmp_path, "2026-11-18_16-19_a")
    d = cosa_e_dovuto(CLIENTE, tmp_path, ora("2026-11-18T16:30"))
    assert [c.cartella.name for c in d.post] == ["2026-11-18_16-19_a"]


def test_stato_fascia_bordi():
    g = date(2026, 11, 18)
    assert stato_fascia(ora("2026-11-18T15:59"), g, (16, 19)) == "presto"
    assert stato_fascia(ora("2026-11-18T18:55"), g, (16, 19)) == "ora"
    assert stato_fascia(ora("2026-11-18T19:05"), g, (16, 19)) == "scaduta"
    assert stato_fascia(ora("2026-11-17T23:00"), g, (16, 19)) == "presto"
    assert stato_fascia(ora("2026-11-19T00:10"), g, (16, 19)) == "scaduta"


def test_ora_legale():
    # 28 marzo 2027: sera prima del cambio; 31 ottobre 2027: giorno del ritorno all'ora solare
    assert stato_fascia(ora("2027-03-30T17:00"), date(2027, 3, 30), (16, 19)) == "ora"
    assert stato_fascia(ora("2027-10-31T18:30"), date(2027, 10, 31), (16, 19)) == "ora"
    # un orario UTC convertito a Roma conta come ora di Roma
    utc = datetime(2027, 7, 14, 14, 30, tzinfo=ZoneInfo("UTC"))  # 16:30 a Roma
    assert stato_fascia(utc, date(2027, 7, 14), (16, 19)) == "ora"


def test_contenuto_futuro_non_dovuto_ne_scaduto(tmp_path):
    _post(tmp_path, "2026-11-25_16-19_a")
    d = cosa_e_dovuto(CLIENTE, tmp_path, ora("2026-11-18T16:30"))
    assert d.post == [] and d.scaduti == []


def test_contenuto_scaduto_va_in_scaduti(tmp_path):
    c = _post(tmp_path, "2026-11-17_16-19_a")
    d = cosa_e_dovuto(CLIENTE, tmp_path, ora("2026-11-18T16:30"))
    assert d.post == [] and d.scaduti == [c]


def test_contenuto_non_valido_non_fa_fallire_gli_altri(tmp_path):
    _post(tmp_path, "2026-11-18_16-19_ok")
    _post(tmp_path, "2026-11-18_16-19_hash", testo="#no")
    d = cosa_e_dovuto(CLIENTE, tmp_path, ora("2026-11-18T16:30"))
    assert [c.cartella.name for c in d.post] == ["2026-11-18_16-19_ok"]
    assert [p.name for p, _ in d.non_validi] == ["2026-11-18_16-19_hash"]


def test_story_da_scorta_nei_giorni_previsti(tmp_path):
    # mercoledì 18 novembre 2026, ore 11
    d = cosa_e_dovuto(CLIENTE, tmp_path, ora("2026-11-18T11:00"))
    assert d.story_da_scorta and d.story_datata is None


def test_story_giorno_non_previsto_senza_datata_non_esce(tmp_path):
    # martedì 17 novembre 2026
    d = cosa_e_dovuto(CLIENTE, tmp_path, ora("2026-11-17T11:00"))
    assert not d.story_da_scorta and d.story_datata is None


def test_story_fuori_fascia_non_esce(tmp_path):
    d = cosa_e_dovuto(CLIENTE, tmp_path, ora("2026-11-18T15:30"))
    assert not d.story_da_scorta


def test_story_datata_di_martedi_esce(tmp_path):
    f = _story_datata(tmp_path, "2026-11-17_10-15_evento.jpg")
    d = cosa_e_dovuto(CLIENTE, tmp_path, ora("2026-11-17T11:00"))
    assert d.story_datata.file == f and not d.story_da_scorta


def test_story_datata_ha_precedenza_su_scorta(tmp_path):
    f = _story_datata(tmp_path, "2026-11-18_10-15_evento.jpg")
    d = cosa_e_dovuto(CLIENTE, tmp_path, ora("2026-11-18T11:00"))
    assert d.story_datata.file == f and d.story_da_scorta is False


def test_story_datata_scaduta_va_in_scaduti(tmp_path):
    f = _story_datata(tmp_path, "2026-11-16_10-15_evento.jpg")
    d = cosa_e_dovuto(CLIENTE, tmp_path, ora("2026-11-18T11:00"))
    assert d.story_datata is None and f in d.scaduti


CON_MAZZO = Cliente("brasera", "1", "2", [2, 3, 4], (17, 21), {"01-carosello": ([5, 6], (11, 19))})


def test_mazzo_esce_nei_suoi_giorni_e_fascia(tmp_path):
    # sabato 21 novembre 2026
    d = cosa_e_dovuto(CON_MAZZO, tmp_path, ora("2026-11-21T11:30"))
    assert d.story_da_scorta and d.mazzo_scorta == "01-carosello"
    d = cosa_e_dovuto(CON_MAZZO, tmp_path, ora("2026-11-22T19:10"))  # domenica, fuori fascia
    assert not d.story_da_scorta and d.mazzo_scorta is None


def test_scorta_generale_nei_suoi_giorni_e_mai_il_mazzo(tmp_path):
    # mercoledì 18 novembre 2026
    d = cosa_e_dovuto(CON_MAZZO, tmp_path, ora("2026-11-18T17:30"))
    assert d.story_da_scorta and d.mazzo_scorta == ""
    d = cosa_e_dovuto(CON_MAZZO, tmp_path, ora("2026-11-18T12:00"))
    assert not d.story_da_scorta
    d = cosa_e_dovuto(CON_MAZZO, tmp_path, ora("2026-11-17T18:00"))  # martedì
    assert not d.story_da_scorta

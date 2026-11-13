import json

from pubblica.chiavi import abbina, aggiorna_config, normalizza
from pubblica.run import token_per

PAGINE = [
    {"id": "1", "name": "Rigenera Lab", "instagram_business_account": {"id": "ig1"}},
    {"id": "2", "name": "Rigenera Active", "instagram_business_account": {"id": "ig2"}},
    {"id": "3", "name": "Trattoria La Brasera"},
    {"id": "4", "name": "Studio Dinamo Fisioterapia"},
]


def test_normalizza_toglie_accenti_e_punteggiatura():
    assert normalizza("Città-Àrca  Med!") == "citta arca med"


def test_abbina_distingue_rigenera_lab_e_active():
    abbinate, mancanti, doppie = abbina(PAGINE)
    assert abbinate["rigenera-lab"]["id"] == "1"
    assert abbinate["rigenera-active"]["id"] == "2"
    assert abbinate["trattoria-la-brasera"]["id"] == "3"
    assert abbinate["studio-dinamo"]["id"] == "4"
    assert set(mancanti) == {"poliambulatorio-benessere", "arcamed", "vyva-clinic"}
    assert doppie == {}


def test_abbina_non_sceglie_tra_due_pagine():
    _, _, doppie = abbina([{"id": "1", "name": "Dinamo"}, {"id": "2", "name": "Dinamo bis"}], {"studio-dinamo": ["dinamo"]})
    assert doppie == {"studio-dinamo": ["Dinamo", "Dinamo bis"]}


def test_aggiorna_config_tiene_le_stories_esistenti_e_aggiunge_i_nuovi():
    vecchia = {"rigenera-lab": {"page_id": "1", "ig_user_id": "ig1", "giorni_story": [0, 2], "fascia_story": [10, 15]}}
    abbinate, _, _ = abbina(PAGINE)
    nuova = aggiorna_config(vecchia, abbinate)
    assert nuova["rigenera-lab"]["giorni_story"] == [0, 2]
    assert nuova["trattoria-la-brasera"] == {"page_id": "3", "ig_user_id": "", "giorni_story": [], "fascia_story": [10, 15]}


def test_token_per_cliente(monkeypatch):
    monkeypatch.setenv("META_PAGE_TOKENS", json.dumps({"studio-dinamo": "t-dinamo"}))
    monkeypatch.setenv("META_PAGE_TOKEN", "t-vecchio")
    assert token_per("studio-dinamo") == "t-dinamo"
    assert token_per("rigenera-lab") == "t-vecchio"  # ripiego sul vecchio segreto
    assert token_per("arcamed") == ""


def test_token_per_preferisce_il_nuovo_segreto(monkeypatch):
    monkeypatch.setenv("META_PAGE_TOKENS", json.dumps({"rigenera-lab": "t-nuovo"}))
    monkeypatch.setenv("META_PAGE_TOKEN", "t-vecchio")
    assert token_per("rigenera-lab") == "t-nuovo"

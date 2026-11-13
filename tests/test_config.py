from pathlib import Path
from pubblica.config import carica_config


def test_carica_config_rigenera_lab():
    cfg = carica_config(Path(__file__).parent.parent / "config" / "clienti.json")
    c = cfg["rigenera-lab"]
    assert c.slug == "rigenera-lab"
    assert c.giorni_story == []  # stories ferme finché Lisa non carica la scorta (era [0, 2, 3, 4])
    assert c.fascia_story == (10, 15)
    assert c.page_id == "1932726716776796"

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Cliente:
    slug: str
    page_id: str
    ig_user_id: str
    giorni_story: list[int]  # lunedì = 0
    fascia_story: tuple[int, int]


def carica_config(percorso: Path) -> dict[str, Cliente]:
    dati = json.loads(Path(percorso).read_text(encoding="utf-8"))
    return {
        slug: Cliente(
            slug=slug,
            page_id=c["page_id"],
            ig_user_id=c.get("ig_user_id", ""),
            giorni_story=list(c.get("giorni_story", [])),  # vuoto = nessuna story dalla scorta
            fascia_story=tuple(c.get("fascia_story", [10, 15])),
        )
        for slug, c in dati.items()
    }

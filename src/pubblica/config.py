import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Cliente:
    slug: str
    page_id: str
    ig_user_id: str
    giorni_story: list[int]  # lunedì = 0
    fascia_story: tuple[int, int]
    # sottocartelle di stories-scorta con giorni e fascia propri: {nome: (giorni, fascia)}
    mazzi_story: dict[str, tuple[list[int], tuple[int, int]]] = field(default_factory=dict)
    # quante stories dalla scorta generale nei giorni previsti: la fascia si divide in parti uguali
    stories_al_giorno: int = 1


def carica_config(percorso: Path) -> dict[str, Cliente]:
    dati = json.loads(Path(percorso).read_text(encoding="utf-8"))
    return {
        slug: Cliente(
            slug=slug,
            page_id=c["page_id"],
            ig_user_id=c.get("ig_user_id", ""),
            giorni_story=list(c.get("giorni_story", [])),  # vuoto = nessuna story dalla scorta
            fascia_story=tuple(c.get("fascia_story", [10, 15])),
            mazzi_story={
                nome: (list(m.get("giorni", [])), tuple(m.get("fascia", [10, 15])))
                for nome, m in c.get("mazzi_story", {}).items()
            },
            stories_al_giorno=max(1, int(c.get("stories_al_giorno", 1))),
        )
        for slug, c in dati.items()
    }

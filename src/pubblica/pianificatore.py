from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from .config import Cliente
from .contenuti import (
    Contenuto,
    ContenutoNonValido,
    StoryDatata,
    leggi_contenuto,
    leggi_story_datata,
)

ROMA = ZoneInfo("Europe/Rome")


@dataclass
class Dovuti:
    post: list[Contenuto] = field(default_factory=list)
    story_datata: StoryDatata | None = None
    story_da_scorta: bool = False
    # quale mazzo della scorta: "" = file sciolti di stories-scorta, altrimenti il nome della sottocartella
    mazzo_scorta: str | None = None
    # quale delle stories del giorno (0 = la prima), quando ne escono più di una
    turno_scorta: int = 0
    scaduti: list[Path] = field(default_factory=list)
    non_validi: list[tuple[Path, str]] = field(default_factory=list)


def stato_fascia(ora: datetime, giorno: date, fascia: tuple[float, float]) -> Literal["presto", "ora", "scaduta"]:
    """La fascia è [inizio, fine) all'ora di Roma."""
    ora = ora.astimezone(ROMA)
    mezzanotte = datetime(giorno.year, giorno.month, giorno.day, tzinfo=ROMA)
    inizio = mezzanotte + timedelta(hours=fascia[0])
    fine = mezzanotte + timedelta(hours=fascia[1])
    if ora < inizio:
        return "presto"
    if ora < fine:
        return "ora"
    return "scaduta"


def cosa_e_dovuto(cliente: Cliente, radice_outbox: Path, ora: datetime) -> Dovuti:
    radice = Path(radice_outbox)
    ora = ora.astimezone(ROMA)
    oggi = ora.date()
    dovuti = Dovuti()

    cartella_post = radice / "post"
    if cartella_post.exists():
        for cartella in sorted(p for p in cartella_post.iterdir() if p.is_dir()):
            if (cartella / ".avvisato").exists():
                continue
            try:
                c = leggi_contenuto(cartella)
            except ContenutoNonValido as e:
                dovuti.non_validi.append((cartella, str(e)))
                continue
            stato = stato_fascia(ora, c.data, c.fascia)
            if stato == "ora":
                dovuti.post.append(c)
            elif stato == "scaduta":
                dovuti.scaduti.append(cartella)

    ce_datata_oggi = False
    cartella_datate = radice / "stories-datate"
    if cartella_datate.exists():
        for f in sorted(p for p in cartella_datate.iterdir() if p.is_file() and p.name != ".gitkeep"):
            if f.name.endswith(".avvisato") or (f.parent / (f.name + ".avvisato")).exists():
                continue
            try:
                s = leggi_story_datata(f)
            except ContenutoNonValido as e:
                dovuti.non_validi.append((f, str(e)))
                continue
            if s.data == oggi:
                ce_datata_oggi = True
            stato = stato_fascia(ora, s.data, s.fascia)
            if stato == "ora" and dovuti.story_datata is None:
                dovuti.story_datata = s
            elif stato == "scaduta":
                dovuti.scaduti.append(f)

    # prima i mazzi con regole proprie (una story), poi la scorta generale (stories_al_giorno);
    # una story datata prende il posto di una di quelle della scorta
    quante = cliente.stories_al_giorno - (1 if ce_datata_oggi else 0)
    regole = [(nome, g, f, 1) for nome, (g, f) in cliente.mazzi_story.items()]
    regole.append(("", cliente.giorni_story, cliente.fascia_story, cliente.stories_al_giorno))
    if quante > 0:
        for nome, giorni, fascia, n in regole:
            n = n - (1 if ce_datata_oggi else 0)
            if n <= 0 or oggi.weekday() not in giorni:
                continue
            passo = (fascia[1] - fascia[0]) / n
            for turno in range(n):
                parte = (fascia[0] + passo * turno, fascia[0] + passo * (turno + 1))
                if stato_fascia(ora, oggi, parte) == "ora":
                    dovuti.story_da_scorta = True
                    dovuti.mazzo_scorta = nome
                    dovuti.turno_scorta = turno
                    break
            if dovuti.story_da_scorta:
                break

    return dovuti

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# fascia in ore intere (16-19) o con i minuti (1230-1530, 1630-18)
NOME_SICURO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_(\d{1,2})(\d{2})?-(\d{1,2})(\d{2})?_[a-z0-9-]+$")
HASHTAG = re.compile(r"#\w")
# unica eccezione (Lisa, 2026-11-18): l'apertura della rubrica dei post "lavori" di Studio Dinamo
CONSENTITI = re.compile(r"#Progetti_Dinamo\b")
VIDEO = {".mp4", ".mov"}
# nome utente Instagram: lettere, numeri, punto e trattino basso, massimo 30 caratteri
NOME_UTENTE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
MAX_COLLABORATORI = 3


class ContenutoNonValido(Exception):
    pass


@dataclass
class Contenuto:
    cartella: Path
    data: date
    fascia: tuple[float, float]
    media: list[Path]
    video: bool
    cover: Path | None
    testo: str
    collaboratori: list[str] = field(default_factory=list)


@dataclass
class StoryDatata:
    file: Path
    data: date
    fascia: tuple[float, float]


def _data_e_fascia(nome: str) -> tuple[date, tuple[float, float]]:
    m = NOME_SICURO.match(nome)
    if not m:
        raise ContenutoNonValido(
            f"il nome «{nome}» non è corretto: serve AAAA-MM-GG_16-19_titolo-in-minuscolo-con-trattini"
        )
    a, mese, g, hi, mi, hf, mf = (int(x) if x else 0 for x in m.groups())
    if mi > 59 or mf > 59:
        raise ContenutoNonValido(f"i minuti nel nome «{nome}» non sono validi")
    i, f = hi + mi / 60, hf + mf / 60
    if i % 1 == 0 and f % 1 == 0:
        i, f = int(i), int(f)
    try:
        return date(a, mese, g), (i, f)
    except ValueError:
        raise ContenutoNonValido(f"la data nel nome «{nome}» non esiste")


def leggi_contenuto(cartella: Path) -> Contenuto:
    cartella = Path(cartella)
    data, fascia = _data_e_fascia(cartella.name)

    testo_file = cartella / "testo.txt"
    if not testo_file.exists():
        raise ContenutoNonValido(f"{cartella.name}: manca il file testo.txt")
    testo = testo_file.read_bytes().decode("utf-8")
    if HASHTAG.search(CONSENTITI.sub("", testo)):
        raise ContenutoNonValido(f"{cartella.name}: il testo contiene un hashtag, non esce")

    immagini, video, cover = [], [], None
    for f in sorted(cartella.iterdir()):
        if f.name in ("testo.txt", "collaboratori.txt", ".stato.json", ".avvisato"):
            continue
        if f.name == "cover.jpg":
            cover = f
        elif f.suffix.lower() == ".jpg" and f.stem.isdigit():
            immagini.append(f)
        elif f.suffix.lower() in VIDEO:
            video.append(f)
        else:
            raise ContenutoNonValido(f"{cartella.name}: file non riconosciuto «{f.name}»")

    if video and immagini:
        raise ContenutoNonValido(f"{cartella.name}: ci sono sia video sia immagini")
    if len(video) > 1:
        raise ContenutoNonValido(f"{cartella.name}: ci sono più video, ne serve uno solo")
    if not video and not immagini:
        raise ContenutoNonValido(f"{cartella.name}: non c'è nessuna immagine né video")
    if len(immagini) > 10:
        raise ContenutoNonValido(f"{cartella.name}: un carosello può avere al massimo 10 immagini")

    immagini.sort(key=lambda p: int(p.stem))
    collaboratori = _leggi_collaboratori(cartella)
    return Contenuto(
        cartella=cartella,
        data=data,
        fascia=fascia,
        media=video or immagini,
        video=bool(video),
        cover=cover if video else None,
        testo=testo,
        collaboratori=collaboratori,
    )


def _leggi_collaboratori(cartella: Path) -> list[str]:
    """collaboratori.txt (facoltativo): un nome utente Instagram per riga, con o senza @.
    Vengono invitati come collaboratori del post o del reel (solo Instagram)."""
    f = cartella / "collaboratori.txt"
    if not f.exists():
        return []
    nomi = []
    for parte in re.split(r"[\s,;]+", f.read_bytes().decode("utf-8-sig")):
        nome = parte.strip().lstrip("@")
        if not nome:
            continue
        if not NOME_UTENTE.match(nome):
            raise ContenutoNonValido(f"{cartella.name}: «{parte}» in collaboratori.txt non è un nome utente Instagram valido")
        if nome.lower() not in (n.lower() for n in nomi):
            nomi.append(nome)
    if len(nomi) > MAX_COLLABORATORI:
        raise ContenutoNonValido(f"{cartella.name}: al massimo {MAX_COLLABORATORI} collaboratori, in collaboratori.txt ce ne sono {len(nomi)}")
    return nomi


def leggi_story_datata(file: Path) -> StoryDatata:
    file = Path(file)
    data, fascia = _data_e_fascia(file.stem)
    return StoryDatata(file=file, data=data, fascia=fascia)

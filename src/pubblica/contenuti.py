import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

NOME_SICURO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_(\d{1,2})-(\d{1,2})_[a-z0-9-]+$")
HASHTAG = re.compile(r"#\w")
VIDEO = {".mp4", ".mov"}


class ContenutoNonValido(Exception):
    pass


@dataclass
class Contenuto:
    cartella: Path
    data: date
    fascia: tuple[int, int]
    media: list[Path]
    video: bool
    cover: Path | None
    testo: str


@dataclass
class StoryDatata:
    file: Path
    data: date
    fascia: tuple[int, int]


def _data_e_fascia(nome: str) -> tuple[date, tuple[int, int]]:
    m = NOME_SICURO.match(nome)
    if not m:
        raise ContenutoNonValido(
            f"il nome Â«{nome}Â» non Ã¨ corretto: serve AAAA-MM-GG_16-19_titolo-in-minuscolo-con-trattini"
        )
    a, mese, g, i, f = (int(x) for x in m.groups())
    try:
        return date(a, mese, g), (i, f)
    except ValueError:
        raise ContenutoNonValido(f"la data nel nome Â«{nome}Â» non esiste")


def leggi_contenuto(cartella: Path) -> Contenuto:
    cartella = Path(cartella)
    data, fascia = _data_e_fascia(cartella.name)

    testo_file = cartella / "testo.txt"
    if not testo_file.exists():
        raise ContenutoNonValido(f"{cartella.name}: manca il file testo.txt")
    testo = testo_file.read_bytes().decode("utf-8")
    if HASHTAG.search(testo):
        raise ContenutoNonValido(f"{cartella.name}: il testo contiene un hashtag, non esce")

    immagini, video, cover = [], [], None
    for f in sorted(cartella.iterdir()):
        if f.name in ("testo.txt", ".stato.json", ".avvisato"):
            continue
        if f.name == "cover.jpg":
            cover = f
        elif f.suffix.lower() == ".jpg" and f.stem.isdigit():
            immagini.append(f)
        elif f.suffix.lower() in VIDEO:
            video.append(f)
        else:
            raise ContenutoNonValido(f"{cartella.name}: file non riconosciuto Â«{f.name}Â»")

    if video and immagini:
        raise ContenutoNonValido(f"{cartella.name}: ci sono sia video sia immagini")
    if len(video) > 1:
        raise ContenutoNonValido(f"{cartella.name}: ci sono piÃ¹ video, ne serve uno solo")
    if not video and not immagini:
        raise ContenutoNonValido(f"{cartella.name}: non c'Ã¨ nessuna immagine nÃ© video")
    if len(immagini) > 10:
        raise ContenutoNonValido(f"{cartella.name}: un carosello puÃ² avere al massimo 10 immagini")

    immagini.sort(key=lambda p: int(p.stem))
    return Contenuto(
        cartella=cartella,
        data=data,
        fascia=fascia,
        media=video or immagini,
        video=bool(video),
        cover=cover if video else None,
        testo=testo,
    )


def leggi_story_datata(file: Path) -> StoryDatata:
    file = Path(file)
    data, fascia = _data_e_fascia(file.stem)
    return StoryDatata(file=file, data=data, fascia=fascia)

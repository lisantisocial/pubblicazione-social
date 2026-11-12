from pathlib import Path

from PIL import Image

ESTENSIONI_IMMAGINE = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}


def a_jpeg(percorso: Path) -> Path:
    """Se l'immagine non è già .jpg la converte in JPEG accanto all'originale,
    elimina l'originale e restituisce il nuovo percorso."""
    percorso = Path(percorso)
    if percorso.suffix.lower() == ".jpg":
        return percorso
    destinazione = percorso.with_suffix(".jpg")
    with Image.open(percorso) as img:
        img.convert("RGB").save(destinazione, "JPEG", quality=95)
    percorso.unlink()
    return destinazione

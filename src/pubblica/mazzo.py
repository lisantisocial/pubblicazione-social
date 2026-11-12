import copy
import random


class ScortaVuota(Exception):
    pass


def prossima_story(scorta: list[str], registro: dict, rng: random.Random, data: str = "") -> tuple[str, dict]:
    """Metodo del mazzo di carte: si usano tutte le grafiche della scorta una dopo l'altra,
    poi si rimescola. L'ultima di un giro non può essere la prima del giro successivo."""
    if not scorta:
        raise ScortaVuota("la scorta delle stories è vuota")

    reg = copy.deepcopy(registro)
    reg.setdefault("mazzo", [])
    reg.setdefault("ultima", None)
    reg.setdefault("uscite", [])

    # le grafiche tolte dalla scorta escono dal mazzo; quelle aggiunte entrano nel giro dopo
    reg["mazzo"] = [f for f in reg["mazzo"] if f in scorta]
    if not reg["mazzo"]:
        nuovo = list(scorta)
        rng.shuffle(nuovo)
        if len(nuovo) > 1 and nuovo[0] == reg["ultima"]:
            nuovo.append(nuovo.pop(0))
        reg["mazzo"] = nuovo

    scelta = reg["mazzo"].pop(0)
    reg["ultima"] = scelta
    reg["uscite"].append({"file": scelta, "data": data})
    return scelta, reg

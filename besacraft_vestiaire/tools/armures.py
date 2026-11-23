"""The armour stand of a player, as the game sends it: up to eight armours, each a breastplate
and its colour, an optional helmet and its colour, an appearance style and, optionally, the
colour of the beacon its gyrophare function pops out of the helmet.

Pure Python, no Odoo: the API and the model use it, and it can be checked on its own.
"""
import re

STAND_MAX = 8
NOM_MAX = 40
ID = re.compile(r"^[a-z0-9_]{1,48}$")


def _id(valeur):
    return valeur if isinstance(valeur, str) and ID.match(valeur) else None


def normaliser(armures, pieces):
    """Keep what can be kept of the armours sent by the game.

    `pieces` maps every owned code that is an armour piece to "plastron" or "casque". An
    armour whose breastplate is not an owned breastplate is dropped; a helmet that is not an
    owned helmet is dropped alone. Colours and style are game-side names, only their form is
    checked. The beacon colour ("gyrophare") is kept only when it is set, so an armour without
    one comes back as older games wrote it; it does not make another armour. A second identical
    armour is dropped. Returns the clean list."""
    gardees, vues = [], set()
    for objet in armures if isinstance(armures, list) else []:
        if len(gardees) >= STAND_MAX:
            break
        if not isinstance(objet, dict):
            continue
        plastron = _id(objet.get("plastron"))
        if not plastron or pieces.get(plastron) != "plastron":
            continue
        casque = _id(objet.get("casque"))
        if casque and pieces.get(casque) != "casque":
            casque = None
        nom = objet.get("nom")
        armure = {
            "nom": nom[:NOM_MAX] if isinstance(nom, str) and nom.strip() else None,
            "plastron": plastron,
            "teinte_plastron": _id(objet.get("teinte_plastron")),
            "casque": casque,
            "teinte_casque": _id(objet.get("teinte_casque")) if casque else None,
            "style": _id(objet.get("style")),
        }
        cle = tuple(v for k, v in armure.items() if k != "nom")
        gyrophare = _id(objet.get("gyrophare"))
        if gyrophare:
            armure["gyrophare"] = gyrophare
        if cle in vues:
            continue
        vues.add(cle)
        gardees.append(armure)
    return gardees


def derniere(index, armures):
    """The position of the last armour used, or -1 when it points nowhere."""
    return index if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(armures) else -1

import base64
import json
import logging

import requests

_logger = logging.getLogger(__name__)

PROFIL = "https://sessionserver.mojang.com/session/minecraft/profile/%s"


def texture_skin(uuid):
    """(PNG bytes, model) of the player's Mojang skin, or None. Never raises."""
    try:
        reponse = requests.get(PROFIL % uuid, timeout=10)
        if reponse.status_code != 200:
            return None
        proprietes = (reponse.json() or {}).get("properties") or []
        valeur = next((p["value"] for p in proprietes if p.get("name") == "textures"), None)
        if not valeur:
            return None
        skin = json.loads(base64.b64decode(valeur)).get("textures", {}).get("SKIN")
        if not skin or not skin.get("url"):
            return None
        modele = "slim" if (skin.get("metadata") or {}).get("model") == "slim" else "classic"
        image = requests.get(skin["url"], timeout=10)
        if image.status_code != 200:
            return None
        return image.content, modele
    except (requests.RequestException, ValueError, KeyError) as erreur:
        _logger.warning("Mojang skin of %s unavailable: %s", uuid, erreur)
        return None

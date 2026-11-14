import base64
import json
import logging
from urllib.parse import urlsplit

import requests

_logger = logging.getLogger(__name__)

PROFIL = "https://sessionserver.mojang.com/session/minecraft/profile/%s"
HOTE_TEXTURES = "textures.minecraft.net"
TAILLE_MAX = 1024 * 1024


def _url_texture(url):
    """The https URL of a Mojang texture, or None for any other host or scheme."""
    morceaux = urlsplit(url)
    if morceaux.scheme not in ("http", "https") or morceaux.hostname != HOTE_TEXTURES:
        return None
    return morceaux._replace(scheme="https", netloc=HOTE_TEXTURES).geturl()


def _telecharger(url):
    """Body of `url`, capped at TAILLE_MAX bytes, without following redirects; None otherwise."""
    reponse = requests.get(url, timeout=10, allow_redirects=False, stream=True)
    try:
        if reponse.status_code != 200:
            return None
        annonce = (reponse.headers or {}).get("Content-Length")
        if annonce and annonce.isdigit() and int(annonce) > TAILLE_MAX:
            _logger.warning("Mojang texture %s too large (%s bytes announced)", url, annonce)
            return None
        corps = bytearray()
        for morceau in reponse.iter_content(65536):
            corps += morceau
            if len(corps) > TAILLE_MAX:
                _logger.warning("Mojang texture %s exceeds %s bytes", url, TAILLE_MAX)
                return None
        return bytes(corps)
    finally:
        reponse.close()


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
        url = _url_texture(skin["url"])
        if not url:
            _logger.warning("Mojang skin of %s points outside %s: refused", uuid, HOTE_TEXTURES)
            return None
        modele = "slim" if (skin.get("metadata") or {}).get("model") == "slim" else "classic"
        image = _telecharger(url)
        if image is None:
            return None
        return image, modele
    except (requests.RequestException, ValueError, KeyError, AttributeError, TypeError) as erreur:
        _logger.warning("Mojang skin of %s unavailable: %s", uuid, erreur)
        return None

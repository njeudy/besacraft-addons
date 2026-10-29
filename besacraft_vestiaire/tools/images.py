import base64
import binascii
import hashlib
import io

from PIL import Image, UnidentifiedImageError

from odoo.exceptions import ValidationError

POIDS_MAX = 1024 * 1024
SKINS = {(64, 64), (64, 32)}


def _ouvrir(env, data):
    if len(data) > POIDS_MAX:
        raise ValidationError(env._("The image is larger than 1 MB."))
    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError):
        raise ValidationError(env._("The file is not a valid image."))
    if image.format != "PNG":
        raise ValidationError(env._("The image must be a PNG."))
    return image.size


def verifier_skin(env, data):
    if _ouvrir(env, data) not in SKINS:
        raise ValidationError(env._("A skin must be 64×64 or 64×32 pixels."))


def verifier_cape(env, data):
    largeur, hauteur = _ouvrir(env, data)
    if largeur % 64 or largeur != 2 * hauteur:
        raise ValidationError(env._("A cape must be 64×32 pixels or a multiple of it."))


def decoder(env, valeur):
    """Decode a base64 payload, turning malformed input into a ValidationError."""
    try:
        return base64.b64decode(valeur, validate=True)
    except (binascii.Error, ValueError, TypeError):
        raise ValidationError(env._("The file is not a valid image."))


def empreinte(data):
    return hashlib.sha256(data).hexdigest()

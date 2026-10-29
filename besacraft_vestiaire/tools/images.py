import base64
import binascii
import hashlib
import io

from PIL import Image, UnidentifiedImageError

from odoo import _
from odoo.exceptions import ValidationError

POIDS_MAX = 1024 * 1024
SKINS = {(64, 64), (64, 32)}


def _ouvrir(data):
    if len(data) > POIDS_MAX:
        raise ValidationError(_("The image is larger than 1 MB."))
    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError):
        raise ValidationError(_("The file is not a valid image."))
    if image.format != "PNG":
        raise ValidationError(_("The image must be a PNG."))
    return image.size


def verifier_skin(data):
    if _ouvrir(data) not in SKINS:
        raise ValidationError(_("A skin must be 64×64 or 64×32 pixels."))


def verifier_cape(data):
    largeur, hauteur = _ouvrir(data)
    if largeur % 64 or largeur != 2 * hauteur:
        raise ValidationError(_("A cape must be 64×32 pixels or a multiple of it."))


def decoder(valeur):
    """Decode a base64 payload, turning malformed input into a ValidationError."""
    try:
        return base64.b64decode(valeur, validate=True)
    except (binascii.Error, ValueError, TypeError):
        raise ValidationError(_("The file is not a valid image."))


def empreinte(data):
    return hashlib.sha256(data).hexdigest()

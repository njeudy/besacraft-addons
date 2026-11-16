"""Read and check the zip package of a remote cosmetic, as made by ``generer.py --paquet``.

The package is data only: JSON and PNG files at fixed paths, the same as under the
mod's ``assets/besacraft/``. Anything else refuses the whole package, so that no code
and no stray file can ever reach a game client.
"""
import hashlib
import io
import json
import re
import zipfile

from PIL import Image, UnidentifiedImageError

from odoo.exceptions import ValidationError

ARCHIVE_MAX = 2 * 1024 * 1024
FICHIERS_MAX = 32
DECOMPRESSE_MAX = 4 * 1024 * 1024
JSON_MAX = 256 * 1024
PNG_MAX = 256 * 1024
COTE_MAX = 512

ENTREE = "cosmetique.json"
ID = re.compile(r"^[a-z0-9_]{1,40}$")
VARIANTE = re.compile(r"^[a-z0-9_]+$")
ACCROCHES = {"head", "body", "arm_left", "arm_right", "leg_left", "leg_right"}
# Every slot of the mod's catalogue but "effet", whose particles ship with the mod.
EMPLACEMENTS = {"chapeau", "tete", "visage", "cape", "ailes", "dos", "bandouliere", "queue", "torse",
                "taille", "bras", "chaussures", "familier_epaule", "familier_tete", "accessoire"}


def chemins_permis(code):
    """The regular expression of every path a package for this code may hold."""
    c = re.escape(code)
    return re.compile(
        r"^(cosmetique\.json"
        rf"|geo/cosmetique/{c}\.geo\.json"
        rf"|animations/cosmetique/{c}\.animation\.json"
        rf"|textures/cosmetique/{c}(__[a-z0-9_]+)?(_glowmask)?\.png)$")


def empreinte(octets):
    return hashlib.sha256(octets).hexdigest()


def lire(env, octets, code):
    """Check a package and return ``(entree, fichiers)``: the catalogue entry as a dict and
    ``{path: bytes}`` for every file, ``cosmetique.json`` included.

    Raise a ValidationError naming the first problem found."""
    _ = env._
    if not code or not ID.match(code):
        raise ValidationError(_("The code must be 1 to 40 lowercase letters, digits or underscores."))
    if len(octets) > ARCHIVE_MAX:
        raise ValidationError(_("The package is larger than 2 MB."))
    try:
        archive = zipfile.ZipFile(io.BytesIO(octets))
        infos = [i for i in archive.infolist() if not i.is_dir()]
    except (zipfile.BadZipFile, OSError, ValueError):
        raise ValidationError(_("The package is not a valid zip file."))
    if len(infos) > FICHIERS_MAX:
        raise ValidationError(_("The package holds more than %s files.", FICHIERS_MAX))
    permis = chemins_permis(code)
    total = 0
    for info in infos:
        if not permis.match(info.filename):
            raise ValidationError(_("Unexpected file in the package: %s", info.filename))
        total += info.file_size
    if total > DECOMPRESSE_MAX:
        raise ValidationError(_("The package is larger than 4 MB once unpacked."))
    fichiers = {}
    for info in infos:
        try:
            # Read one byte past the limit: the size in the zip header is not trusted.
            with archive.open(info) as f:
                donnees = f.read(DECOMPRESSE_MAX + 1)
        except (zipfile.BadZipFile, OSError, ValueError, RuntimeError, EOFError):
            raise ValidationError(_("Unreadable file in the package: %s", info.filename))
        if info.filename.endswith(".png"):
            _verifier_png(env, info.filename, donnees)
        elif len(donnees) > JSON_MAX:
            raise ValidationError(_("%s is larger than 256 KB.", info.filename))
        fichiers[info.filename] = donnees
    if ENTREE not in fichiers:
        raise ValidationError(_("The package has no cosmetique.json."))
    entree = _json(env, ENTREE, fichiers[ENTREE])
    geo = _json(env, f"geo/cosmetique/{code}.geo.json", fichiers.get(f"geo/cosmetique/{code}.geo.json"))
    animations = _json(env, f"animations/cosmetique/{code}.animation.json",
                       fichiers.get(f"animations/cosmetique/{code}.animation.json"))
    _verifier_entree(env, code, entree)
    if not isinstance(geo.get("minecraft:geometry"), list) or not geo["minecraft:geometry"]:
        raise ValidationError(_("The geometry file has no minecraft:geometry."))
    if not isinstance(animations.get("animations"), dict):
        raise ValidationError(_("The animation file has no animations."))
    for declencheur in entree.get("declencheurs") or []:
        nom = isinstance(declencheur, dict) and declencheur.get("animation")
        if not isinstance(nom, str) or nom not in animations["animations"]:
            raise ValidationError(_("A trigger plays an unknown animation: %s", nom))
    _verifier_textures(env, code, entree, fichiers)
    return entree, fichiers


def _json(env, chemin, donnees):
    if donnees is None:
        raise ValidationError(env._("The package has no %s.", chemin))
    try:
        valeur = json.loads(donnees.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ValidationError(env._("%s is not valid JSON.", chemin))
    if not isinstance(valeur, dict):
        raise ValidationError(env._("%s must hold a JSON object.", chemin))
    return valeur


def _verifier_png(env, chemin, donnees):
    if len(donnees) > PNG_MAX:
        raise ValidationError(env._("%s is larger than 256 KB.", chemin))
    try:
        image = Image.open(io.BytesIO(donnees))
        image.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        raise ValidationError(env._("%s is not a valid image.", chemin))
    if image.format != "PNG":
        raise ValidationError(env._("%s must be a PNG.", chemin))
    largeur, hauteur = image.size
    if largeur > COTE_MAX or hauteur > COTE_MAX:
        raise ValidationError(env._("%s is larger than 512×512 pixels.", chemin))


def _verifier_entree(env, code, entree):
    _ = env._
    if entree.get("id") != code:
        raise ValidationError(_("cosmetique.json describes %s, not %s.", entree.get("id"), code))
    if entree.get("emplacement") == "effet":
        raise ValidationError(_("Effects cannot be remote: their particles ship with the mod."))
    if entree.get("emplacement") not in EMPLACEMENTS:
        raise ValidationError(_("Unknown slot: %s", entree.get("emplacement")))
    accroches = entree.get("accroches")
    if not isinstance(accroches, list) or not accroches or not set(accroches) <= ACCROCHES:
        raise ValidationError(_("The attachment bones must be among %s.", ", ".join(sorted(ACCROCHES))))
    if not isinstance(entree.get("declencheurs", []), list):
        raise ValidationError(_("The triggers must be a list."))


def _verifier_textures(env, code, entree, fichiers):
    _ = env._
    textures = {c[len("textures/cosmetique/"):-len(".png")] for c in fichiers if c.endswith(".png")}
    if code not in textures:
        raise ValidationError(_("The package has no base texture %s.png.", code))
    variantes = entree.get("variantes") or []
    if not isinstance(variantes, list):
        raise ValidationError(_("The colours must be a list."))
    attendues = {code}
    for variante in variantes[1:]:
        vid = isinstance(variante, dict) and variante.get("id")
        if not isinstance(vid, str) or not VARIANTE.match(vid):
            raise ValidationError(_("Invalid colour in cosmetique.json."))
        attendues.add(f"{code}__{vid}")
    for nom in attendues:
        if nom not in textures:
            raise ValidationError(_("The package has no texture %s.png.", nom))
    for nom in textures:
        base = nom[:-len("_glowmask")] if nom.endswith("_glowmask") else nom
        if base not in attendues:
            raise ValidationError(_("Texture %s.png matches no declared colour.", nom))

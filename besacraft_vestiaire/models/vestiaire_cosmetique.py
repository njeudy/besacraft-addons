import base64
import binascii
import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..tools import paquet

GENRES = [("cosmetique", "Cosmetic"), ("emote", "Emote")]
PIECES_ARMURE = [("plastron", "Breastplate"), ("casque", "Helmet")]


class BesacraftVestiaireCosmetique(models.Model):
    """What a player may own, keyed by the code of the mod's catalogue. The 3D model and
    the animation ship in the mod's jar, or come from a package dropped here: the game
    then downloads them (remote cosmetic)."""

    _name = "besacraft.vestiaire.cosmetique"
    _description = "Wardrobe cosmetic or emote"
    _order = "genre, sequence, name, id"

    code = fields.Char(required=True, index=True,
                       help="Identifier of the item in the mod's catalogue.json.")
    name = fields.Char(required=True, translate=True)
    genre = fields.Selection(GENRES, string="Kind", required=True, default="cosmetique")
    emplacement = fields.Char(string="Slot",
                              help="Slot of a cosmetic in the mod (chapeau, tete, ailes...).")
    piece_armure = fields.Selection(
        PIECES_ARMURE, string="Armour piece",
        help="A deployable armour piece leaves the outfit: the player puts it in the armour "
             "stand of the wardrobe and deploys it in game. Read from the mod's catalogue.")
    fonction_ids = fields.Many2many(
        "besacraft.vestiaire.fonction", "besacraft_vestiaire_cosmetique_fonction_rel",
        "cosmetique_id", "fonction_id", string="Armour functions",
        help="What this armour piece lets its wearer do. Empty: everything. A deployed armour "
             "gives the functions of its breastplate and of its helmet together.")
    sequence = fields.Integer(default=10)
    vignette = fields.Image(string="Thumbnail", max_width=256, max_height=256)
    prix = fields.Integer(string="Price (points)", default=0,
                          help="0 means the item is not sold.")
    de_base = fields.Boolean(string="Owned by everyone",
                             help="Every valid account owns it without a purchase.")
    publie = fields.Boolean(string="Published", default=True)
    createur_id = fields.Many2one("res.partner", string="Creator")
    source = fields.Char()
    licence = fields.Char(string="License")
    possession_ids = fields.One2many("besacraft.vestiaire.possession", "cosmetique_id",
                                     string="Ownerships")
    possesseur_count = fields.Integer(string="Owners", compute="_compute_possesseur_count",
                                      help="Players who bought, won or were given the item. "
                                           "An item owned by everyone is not counted here.")

    apercu_url = fields.Char(string="Preview", compute="_compute_apercu_url",
                             help="Static picture shipped with the module for this code: a PNG "
                                  "for a cosmetic, an animated GIF for an emote.")

    paquet = fields.Binary(string="Package", compute="_compute_paquet", inverse="_inverse_paquet",
                           help="Zip made by generer.py --paquet <code>: catalogue entry, model, "
                                "animations and textures. Replaces the remote files at once.")
    paquet_nom = fields.Char(string="Package name", compute="_compute_paquet", inverse="_inverse_paquet_nom")
    fichier_ids = fields.One2many("besacraft.vestiaire.fichier", "cosmetique_id", string="Remote files")
    version_distante = fields.Integer(string="Remote version", default=0, readonly=True, copy=False,
                                      help="Raised by one at each accepted package. 0: drawn from the jar only.")
    entree_distante = fields.Text(string="Catalogue entry", readonly=True, copy=False,
                                  help="The catalogue entry read from the package, served to the game.")
    distant = fields.Boolean(string="Remote", compute="_compute_distant", store=True,
                             help="The game downloads this cosmetic from Odoo.")

    _sql_constraints = [
        ("unique_code", "unique(code)", "The code of a wardrobe item must be unique."),
        ("prix_positif", "check(prix >= 0)", "A price cannot be negative."),
    ]

    @api.depends("possession_ids")
    def _compute_possesseur_count(self):
        comptes = dict(self.env["besacraft.vestiaire.possession"].sudo()._read_group(
            [("cosmetique_id", "in", self.ids)], ["cosmetique_id"], ["__count"]))
        for cosmetique in self:
            cosmetique.possesseur_count = comptes.get(cosmetique._origin, 0)

    @api.depends("code", "genre")
    def _compute_apercu_url(self):
        for cosmetique in self:
            if not cosmetique.code:
                cosmetique.apercu_url = False
            elif cosmetique.genre == "emote":
                cosmetique.apercu_url = f"/besacraft_vestiaire/static/img/emotes/{cosmetique.code}.gif"
            else:
                cosmetique.apercu_url = f"/besacraft_vestiaire/static/img/cosmetiques/{cosmetique.code}.png"

    def _en_vente(self):
        return self.filtered(lambda c: c.publie and c.prix > 0)

    def _compute_paquet(self):
        for cosmetique in self:
            cosmetique.paquet = False
            cosmetique.paquet_nom = False

    def _inverse_paquet_nom(self):
        """The file name only comes with the upload; nothing to keep."""

    def _inverse_paquet(self):
        for cosmetique in self.filtered("paquet"):
            try:
                octets = base64.b64decode(cosmetique.paquet, validate=True)
            except (binascii.Error, ValueError, TypeError):
                raise ValidationError(self.env._("The package is not a valid zip file."))
            cosmetique._deposer_paquet(octets)

    @api.depends("version_distante", "fichier_ids")
    def _compute_distant(self):
        for cosmetique in self:
            cosmetique.distant = bool(cosmetique.version_distante and cosmetique.fichier_ids)

    def _deposer_paquet(self, octets):
        """Check a package and replace the remote files with its content, in one go."""
        self.ensure_one()
        if self.genre != "cosmetique":
            raise ValidationError(self.env._("Only cosmetics can be remote, not emotes."))
        entree, fichiers = paquet.lire(self.env, octets, self.code)
        if self.emplacement and self.emplacement != entree["emplacement"]:
            raise ValidationError(self.env._(
                "The package is for the slot %(paquet)s, the cosmetic is in %(fiche)s.",
                paquet=entree["emplacement"], fiche=self.emplacement))
        self.fichier_ids.unlink()
        self.env["besacraft.vestiaire.fichier"].create([{
            "cosmetique_id": self.id,
            "chemin": chemin,
            "sha256": paquet.empreinte(donnees),
            "taille": len(donnees),
            "contenu": base64.b64encode(donnees),
        } for chemin, donnees in sorted(fichiers.items()) if chemin != paquet.ENTREE])
        self.write({
            "version_distante": self.version_distante + 1,
            "entree_distante": json.dumps(entree, ensure_ascii=False, sort_keys=True),
            "emplacement": entree["emplacement"],
        })

    def action_retirer_paquet(self):
        """Back to the jar only: the game forgets the remote files at its next sync."""
        self.fichier_ids.unlink()
        self.write({"version_distante": 0, "entree_distante": False})

    @api.model
    def _distants_servis(self):
        """The remote cosmetics the game must know: published, with a package."""
        return self.search([("distant", "=", True), ("publie", "=", True), ("genre", "=", "cosmetique")])

    def _manifeste(self):
        """The manifest entry of each cosmetic: what to put in the catalogue, what to download."""
        entrees = []
        for cosmetique in self:
            try:
                entree = json.loads(cosmetique.entree_distante or "{}")
            except ValueError:
                continue
            entree["version"] = cosmetique.version_distante
            entrees.append({
                "code": cosmetique.code,
                "version": cosmetique.version_distante,
                "emplacement": cosmetique.emplacement or None,
                "entree": entree,
                "fichiers": [{"chemin": f.chemin, "sha256": f.sha256, "taille": f.taille}
                             for f in cosmetique.fichier_ids],
            })
        return {"format": 1, "cosmetiques": entrees}

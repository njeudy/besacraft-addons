from odoo import api, fields, models

GENRES = [("cosmetique", "Cosmetic"), ("emote", "Emote")]
PIECES_ARMURE = [("plastron", "Breastplate"), ("casque", "Helmet")]


class BesacraftVestiaireCosmetique(models.Model):
    """What a player may own. The 3D model and the animation ship in the mod's jar;
    Odoo only holds the rights, keyed by the code of the jar's catalogue."""

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

from odoo import fields, models

GENRES = [("cosmetique", "Cosmetic"), ("emote", "Emote")]


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

    _sql_constraints = [
        ("unique_code", "unique(code)", "The code of a wardrobe item must be unique."),
        ("prix_positif", "check(prix >= 0)", "A price cannot be negative."),
    ]

    def _en_vente(self):
        return self.filtered(lambda c: c.publie and c.prix > 0)

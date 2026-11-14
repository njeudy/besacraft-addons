from odoo import _, api, fields, models
from odoo.exceptions import UserError

MOTIFS = [
    ("mission", "Mission"),
    ("defi", "Challenge"),
    ("construction", "Published build"),
    ("cadeau", "Gift"),
    ("achat", "Purchase"),
    ("boutique", "Shop"),
    ("correction", "Correction"),
]


class BesacraftVestiaireMouvement(models.Model):
    """One line of a player's points ledger. Never edited nor deleted: a mistake is
    fixed by a correction line, so the balance always has its history."""

    _name = "besacraft.vestiaire.mouvement"
    _description = "Wardrobe points movement"
    _order = "date desc, id desc"

    partner_id = fields.Many2one("res.partner", string="Player", required=True,
                                 ondelete="cascade", index=True)
    points = fields.Integer(required=True)
    motif = fields.Selection(MOTIFS, string="Reason", required=True)
    libelle = fields.Char(string="Label")
    reference = fields.Char(help="Mission, episode, build or order this movement comes from. "
                                 "A player gets a given reason and reference only once.")
    cosmetique_id = fields.Many2one("besacraft.vestiaire.cosmetique", string="Bought item",
                                    ondelete="restrict")
    date = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True)
    user_id = fields.Many2one("res.users", string="Author", default=lambda self: self.env.user,
                              readonly=True)
    annonce = fields.Boolean(string="Announced in game")

    _sql_constraints = [
        ("unique_reference", "unique(partner_id, motif, reference)",
         "This player already received points for this reason and reference."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("reference"):
                vals["reference"] = False  # NULLs never collide in the unique constraint
            if vals.get("motif") == "achat":
                vals["annonce"] = True  # the player saw it happen
        return super().create(vals_list)

    def write(self, vals):
        if set(vals) - {"annonce"}:
            raise UserError(_("A points movement cannot be changed: add a correction instead."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("A points movement cannot be deleted: add a correction instead."))

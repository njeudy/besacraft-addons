from odoo import api, fields, models

MOTIFS_GAIN = [("mission", "Mission"), ("defi", "Challenge"), ("construction", "Published build")]


class BesacraftVestiaireBareme(models.Model):
    """How many points a reward is worth. Whoever reports a reward never picks the amount."""

    _name = "besacraft.vestiaire.bareme"
    _description = "Wardrobe points scale"
    _order = "motif, code"

    motif = fields.Selection(MOTIFS_GAIN, string="Reason", required=True)
    code = fields.Char(help="Mission or challenge code. Empty: default for the reason.")
    points = fields.Integer(required=True)
    name = fields.Char(string="Label")

    _sql_constraints = [
        ("unique_motif_code", "unique(motif, code)", "This reason and code already have points."),
        ("points_positifs", "check(points > 0)", "A reward must be worth some points."),
    ]

    @api.model
    def _trouver(self, motif, code=None):
        """The scale line of this code, else the default line of the reason."""
        if code:
            ligne = self.search([("motif", "=", motif), ("code", "=", code)], limit=1)
            if ligne:
                return ligne
        return self.search([("motif", "=", motif), ("code", "=", False)], limit=1)

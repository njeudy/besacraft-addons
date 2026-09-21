from odoo import fields, models


class BesacraftSerie(models.Model):
    """One of the channel's three series. Drives the badge colour and the visual mode.

    The visual mode is not decoration: it selects which of the three validated art
    directions a page renders in, so it belongs to the data, not to a template.
    """

    _name = "besacraft.serie"
    _description = "Build Series"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    color = fields.Char("Badge Colour", required=True, help="Hex, e.g. #478BB2.")
    badge_ink = fields.Char("Badge Ink", required=True, help="Text colour over the badge.")
    visual_mode = fields.Selection(
        [("notice", "Notice"), ("chronique", "Chronique"), ("airain", "Coeur d'Airain")],
        required=True, default="notice",
    )

    _sql_constraints = [("code_uniq", "unique(code)", "A series code must be unique.")]

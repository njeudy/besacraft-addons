from odoo import fields, models

CASES_ROUE = 8


class BesacraftVestiaireCase(models.Model):
    """One of the eight slots of a player's emote wheel."""

    _name = "besacraft.vestiaire.case"
    _description = "Emote wheel slot"
    _order = "partner_id, index"

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    index = fields.Integer(required=True)
    emote_id = fields.Many2one("besacraft.vestiaire.cosmetique", string="Emote", required=True,
                               ondelete="cascade", domain=[("genre", "=", "emote")])

    _sql_constraints = [
        ("unique_case", "unique(partner_id, index)", "A wheel slot holds one emote."),
        ("index_borne", "check(index >= 0 and index < %d)" % CASES_ROUE,
         "The wheel has eight slots."),
    ]

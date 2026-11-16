from odoo import fields, models


class BesacraftVestiaireFonction(models.Model):
    """One power of a deployable armour (flight, headlights, HUD...). The codes are the
    ones the mod knows: they are created by the module, only their label is edited."""

    _name = "besacraft.vestiaire.fonction"
    _description = "Armour function"
    _order = "sequence, id"

    code = fields.Char(required=True, readonly=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)

    _sql_constraints = [
        ("unique_code", "unique(code)", "An armour function code is unique."),
    ]

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    besacraft_projet_url = fields.Char(
        related="website_id.besacraft_projet_url", readonly=False)

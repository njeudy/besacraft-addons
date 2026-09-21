from odoo import fields, models


class ProductTemplate(models.Model):
    """Only a marker: no build data lives on the product.

    The instance is shared with unrelated businesses, so the product catalogue must
    stay free of Minecraft fields.
    """

    _inherit = "product.template"

    is_besacraft_tutorial = fields.Boolean(
        "Besacraft Tutorial", help="This product grants access to a build tutorial.")

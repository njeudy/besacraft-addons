from odoo import fields, models


class ProductTemplate(models.Model):
    """Only a marker: no build data lives on the product.

    The instance is shared with unrelated businesses, so the product catalogue must
    stay free of Minecraft fields.
    """

    _inherit = "product.template"

    is_besacraft_tutorial = fields.Boolean(
        "Besacraft Tutorial", help="This product grants access to a build tutorial.")
    besacraft_build_id = fields.Many2one(
        "besacraft.build", compute="_compute_besacraft_build_id",
        help="The build this product unlocks. Computed, so the link stays owned by the "
             "build side and a product never carries build data of its own.")

    def _compute_besacraft_build_id(self):
        builds = self.env["besacraft.build"].sudo().search(
            [("product_id.product_tmpl_id", "in", self.ids)])
        par_modele = {b.product_id.product_tmpl_id.id: b for b in builds}
        for produit in self:
            produit.besacraft_build_id = par_modele.get(produit.id, False)

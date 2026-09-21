from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        """Grant access to the builds sold on this order, as website_sale_slides does."""
        resultat = super()._action_confirm()
        produits = self.order_line.product_id.filtered("is_besacraft_tutorial")
        if not produits:
            return resultat
        builds = self.env["besacraft.build"].sudo().search([("product_id", "in", produits.ids)])
        for commande in self:
            vendus = commande.order_line.product_id.filtered("is_besacraft_tutorial")
            concernes = builds.filtered(lambda b: b.product_id in vendus)
            concernes._action_add_members(commande.partner_id)
        return resultat

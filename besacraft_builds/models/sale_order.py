from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        """Grant access to the builds sold on this order, as website_sale_slides does.

        A build is sold on its own product, or within the pack of one of its series.
        """
        resultat = super()._action_confirm()
        Build = self.env["besacraft.build"].sudo()
        Serie = self.env["besacraft.serie"].sudo()
        for commande in self:
            produits = commande.order_line.product_id
            builds = Build.search([("product_id", "in", produits.filtered(
                "is_besacraft_tutorial").ids)]) if produits else Build
            packs = Serie.search([("pack_product_id", "in", produits.ids)]) if produits else Serie
            if packs:
                builds |= packs._builds_du_pack()
            if builds:
                builds._action_add_members(commande.partner_id)
        return resultat

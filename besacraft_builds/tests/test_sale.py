from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSale(TransactionCase):
    def test_confirmer_la_commande_donne_l_acces(self):
        partner = self.env["res.partner"].create({"name": "Zoé"})
        produit = self.env["product.product"].create({
            "name": "Tuto 9242", "type": "service", "is_besacraft_tutorial": True,
            "list_price": 5.0,
        })
        build = self.env["besacraft.build"].create({
            "name": "Taverne", "code": "9242", "enroll": "payment", "product_id": produit.id,
            "serie_id": self.env.ref("besacraft_builds.serie_survie").id,
        })
        self.assertFalse(build.is_accessible_by(partner))

        commande = self.env["sale.order"].create({
            "partner_id": partner.id,
            "order_line": [(0, 0, {"product_id": produit.id, "product_uom_qty": 1})],
        })
        commande.action_confirm()

        self.assertTrue(build.is_accessible_by(partner))

    def test_une_commande_sans_tuto_ne_cree_aucun_acces(self):
        partner = self.env["res.partner"].create({"name": "Zoé"})
        autre = self.env["product.product"].create({"name": "Conseil", "type": "service"})
        avant = self.env["besacraft.build.member"].search_count([])
        commande = self.env["sale.order"].create({
            "partner_id": partner.id,
            "order_line": [(0, 0, {"product_id": autre.id, "product_uom_qty": 1})],
        })
        commande.action_confirm()
        self.assertEqual(self.env["besacraft.build.member"].search_count([]), avant)

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMember(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({"name": "Zoé"})
        self.build = self.env["besacraft.build"].create({
            "name": "Taverne", "code": "9142",
            "serie_id": self.env.ref("besacraft_builds.serie_survie").id,
        })

    def test_un_build_public_est_accessible_sans_inscription(self):
        self.assertEqual(self.build.enroll, "public")
        self.assertTrue(self.build.is_accessible_by(self.partner))

    def test_un_build_payant_exige_une_inscription(self):
        produit = self.env["product.product"].create({"name": "Tuto", "type": "service"})
        self.build.write({"enroll": "payment", "product_id": produit.id})
        self.assertFalse(self.build.is_accessible_by(self.partner))
        self.build._action_add_members(self.partner)
        self.assertTrue(self.build.is_accessible_by(self.partner))

    def test_on_n_inscrit_pas_deux_fois_la_meme_personne(self):
        self.build._action_add_members(self.partner)
        self.build._action_add_members(self.partner)
        membres = self.env["besacraft.build.member"].search(
            [("build_id", "=", self.build.id), ("partner_id", "=", self.partner.id)])
        self.assertEqual(len(membres), 1)

    def test_le_lien_pointe_bien_res_partner(self):
        """La table de liaison n'est pas un partenaire bis : member_ids EST res.partner."""
        self.build._action_add_members(self.partner)
        self.build.invalidate_recordset(["member_ids"])
        self.assertEqual(self.build.member_ids._name, "res.partner")
        self.assertIn(self.partner, self.build.member_ids)

    def test_le_code_reste_unique_apres_ajout_des_contraintes(self):
        """La tache 4 etend _sql_constraints : l'unicite du code ne doit pas disparaitre."""
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.env["besacraft.build"].create({
                    "name": "Doublon", "code": "9142",
                    "serie_id": self.env.ref("besacraft_builds.serie_survie").id})

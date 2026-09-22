from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestAcces(HttpCase):
    def setUp(self):
        super().setUp()
        self.produit = self.env["product.product"].create({
            "name": "Tuto test", "type": "service",
            "is_besacraft_tutorial": True, "list_price": 4.0,
            "is_published": True,
        })
        self.build = self.env["besacraft.build"].create({
            "name": "Build payant", "code": "911", "enroll": "payment",
            "product_id": self.produit.id, "is_published": True,
            "serie_id": self.env.ref("besacraft_builds.serie_survie").id,
        })

    def test_une_fiche_payante_montre_le_voile_et_mene_au_produit(self):
        """La fiche ne se ferme pas au nez : on devine derrière, et on sait quoi acheter.

        Pas de redirection ici -- envoyer vers /shop ferait disparaître le build que le
        visiteur est venu voir, et c'est justement ce qui lui donne envie.
        """
        reponse = self.url_open("/t/911", allow_redirects=False)
        self.assertEqual(reponse.status_code, 200)
        self.assertIn(self.produit.product_tmpl_id.website_url, reponse.text)

    def test_la_notice_ne_part_pas_dans_la_page_sans_acces(self):
        """Un voile devant une liste lisible dans le code source serait une serrure en carton."""
        couche = self.env["besacraft.build.layer"].create({
            "build_id": self.build.id, "sequence": 1, "title": "Fondations"})
        self.env["besacraft.build.layer.line"].create({
            "layer_id": couche.id, "item_key": "minecraft:oak_planks",
            "name_fr": "Planches de chene", "qty": 64})
        self.assertNotIn("Planches de chene", self.url_open("/t/911").text)

    def test_un_build_gratuit_s_ouvre_directement(self):
        self.build.write({"enroll": "public", "product_id": False})
        reponse = self.url_open("/t/911", allow_redirects=False)
        self.assertEqual(reponse.status_code, 200)

    def test_le_viewer_d_un_build_payant_ne_se_sert_pas(self):
        """Le viewer ne doit jamais partir par une URL devinable."""
        reponse = self.url_open("/besacraft/viewer/%d" % self.build.id, allow_redirects=False)
        self.assertIn(reponse.status_code, (303, 404))

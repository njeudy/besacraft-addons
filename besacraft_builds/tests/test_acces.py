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

    def test_un_visiteur_est_envoye_vers_le_produit(self):
        """Une fiche payante ne se ferme pas au nez : elle mène à ce qu'il faut acheter."""
        reponse = self.url_open("/t/911", allow_redirects=False)
        self.assertEqual(reponse.status_code, 303)
        self.assertIn("/shop", reponse.headers.get("Location", ""))

    def test_un_build_gratuit_s_ouvre_directement(self):
        self.build.write({"enroll": "public", "product_id": False})
        reponse = self.url_open("/t/911", allow_redirects=False)
        self.assertEqual(reponse.status_code, 200)

    def test_le_viewer_d_un_build_payant_ne_se_sert_pas(self):
        """Le viewer ne doit jamais partir par une URL devinable."""
        reponse = self.url_open("/besacraft/viewer/%d" % self.build.id, allow_redirects=False)
        self.assertIn(reponse.status_code, (303, 404))

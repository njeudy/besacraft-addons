import base64

from odoo.tests import TransactionCase, tagged

# Un PNG 1x1 valide : le champ Image refuse ce qui n'en est pas un.
PIXEL = base64.b64encode(base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
    "IQAAAABJRU5ErkJggg=="))


@tagged("post_install", "-at_install")
class TestVendre(TransactionCase):
    def setUp(self):
        super().setUp()
        # Code hors plage éditoriale : la base de dev porte de vrais builds.
        self.build = self.env["besacraft.build"].create({
            "name": "L'Hôtel de Ville", "code": "9943",
            "serie_id": self.env.ref("besacraft_builds.serie_survie").id,
            "accroche": "Le beffroi qui domine la vallée.",
            "block_count": 2177, "layer_count": 23,
            "size_x": 15, "size_y": 26, "size_z": 22,
            "palette_label": "18 types de blocs", "level": "confirme",
        })

    def _vendre(self, **kw):
        valeurs = {"build_id": self.build.id, "price": 4.9, "with_media": False}
        valeurs.update(kw)
        return self.env["besacraft.vendre"].create(valeurs)

    def test_vendre_cree_le_produit_et_ouvre_l_acces(self):
        self._vendre().action_vendre()
        self.assertEqual(self.build.enroll, "payment")
        self.assertEqual(self.build.state, "publie")
        self.assertTrue(self.build.is_published)
        self.assertEqual(self.build.product_id.list_price, 4.9)
        self.assertTrue(self.build.product_id.product_tmpl_id.is_besacraft_tutorial)

    def test_le_produit_porte_la_boite_pas_le_rendu(self):
        """La boutique montre un produit, pas une capture d'écran."""
        self.build.write({"overview_image": PIXEL, "box_image": PIXEL})
        self._vendre().action_vendre()
        self.assertTrue(self.build.product_id.image_1920)

    def test_sans_boite_on_retombe_sur_le_rendu(self):
        """Un build importé avant la boîte reste vendable."""
        self.build.overview_image = PIXEL
        self._vendre().action_vendre()
        self.assertTrue(self.build.product_id.image_1920)

    def test_la_description_reprend_les_chiffres_du_plan(self):
        """Promettre 23 couches et en livrer 21 se verrait à la première."""
        texte = self.build._description_produit()
        self.assertIn("2 177", texte)
        self.assertIn("23", texte)
        self.assertIn("15 × 22", texte)
        self.assertIn("18 types de blocs", texte)
        self.assertIn(self.build.accroche, texte)

    def test_la_description_part_sur_le_produit(self):
        self._vendre().action_vendre()
        modele = self.build.product_id.product_tmpl_id
        self.assertIn("couche par couche", modele.website_description)
        # La fiche chiffrée vit dans la description, pas dans un gabarit surchargé : une
        # page de boutique se retouche en base, sans déployer.
        self.assertIn("2 177", modele.website_description)
        self.assertIn("15 × 26 × 22", modele.website_description)

    def test_le_produit_est_rattache_au_site_besacraft(self):
        """Le même Odoo sert la boutique freelance : un tuto n'y a rien à faire."""
        site = self.env["website"].search([("name", "=ilike", "besacraft")], limit=1)
        if not site:
            site = self.env["website"].create({"name": "Besacraft"})
        self._vendre().action_vendre()
        self.assertEqual(self.build.product_id.product_tmpl_id.website_id, site)

    def test_le_site_du_build_prime_sur_la_recherche_par_nom(self):
        autre = self.env["website"].create({"name": "Boutique d'essai"})
        self.build.website_id = autre
        self._vendre().action_vendre()
        self.assertEqual(self.build.product_id.product_tmpl_id.website_id, autre)

    def test_revendre_reutilise_le_meme_produit(self):
        """Corriger un prix ne doit pas laisser deux fiches pour un tutoriel."""
        self._vendre().action_vendre()
        produit = self.build.product_id
        self._vendre(price=6.5).action_vendre()
        self.assertEqual(self.build.product_id, produit)
        self.assertEqual(produit.list_price, 6.5)

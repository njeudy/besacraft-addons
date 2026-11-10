from odoo.tests import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestShop(HttpCase):
    """The shop page: featured build, shelves by series, series pack, the website_sale cart.

    The test database may speak French: assertions look at markup and data, not at words.
    """

    def setUp(self):
        super().setUp()
        self.site = self.env.ref("website.default_website")
        # Series of its own: a dev database files real builds, paid ones included, under the
        # data series, and they would compete for the featured place.
        self.env["besacraft.serie"].search([]).write({"website_ids": [(3, self.site.id)]})
        Serie = self.env["besacraft.serie"]
        self.serie = Serie.create({"name": "Survie shop", "code": "shop-survie", "color": "#478BB2",
                                   "badge_ink": "#FFFFFF", "website_ids": [(4, self.site.id)]})
        self.autre = Serie.create({"name": "Ville shop", "code": "shop-ville", "color": "#B2478B",
                                   "badge_ink": "#FFFFFF"})
        Produit = self.env["product.product"]
        self.produit = Produit.create({
            "name": "Tuto shop", "type": "service", "is_besacraft_tutorial": True,
            "list_price": 4.9, "is_published": True})
        self.pack = Produit.create({
            "name": "Pack survie shop", "type": "service", "list_price": 14.9,
            "is_published": True})
        Build = self.env["besacraft.build"]
        self.haut = Build.create({
            "name": "Grand navire", "code": "9961", "enroll": "payment",
            "product_id": self.produit.id, "is_published": True, "serie_id": self.serie.id,
            "layer_count": 34, "block_count": 1870})
        self.bas = Build.create({
            "name": "Petite barque", "code": "9962", "enroll": "public",
            "is_published": True, "serie_id": self.serie.id, "layer_count": 60})
        self.haut.chapter_ids = [
            (0, 0, {"sequence": 1, "name": "La quille", "first_layer": 1, "last_layer": 2,
                    "free": True}),
            (0, 0, {"sequence": 2, "name": "Le pont", "first_layer": 3, "last_layer": 9}),
        ]

    def _page(self):
        page = self.url_open("/builds/shop")
        self.assertEqual(page.status_code, 200)
        return page.text

    def test_la_vedette_est_le_plus_haut_des_builds_payants(self):
        """A taller free build does not take the place: the featured build is for sale."""
        page = self._page()
        vedette = page[page.index('class="sh-vedette"'):page.index('class="ac-sec sh-catalogue"')]
        self.assertIn("Grand navire", vedette)
        self.assertNotIn("Petite barque", vedette)
        self.assertIn('class="is-libre"', vedette)
        self.assertIn('class="is-clos"', vedette)
        self.assertIn('data-ajout="%d"' % self.produit.id, vedette)

    def test_sans_build_payant_la_vedette_est_le_plus_haut_du_site(self):
        self.haut.write({"enroll": "public"})
        page = self._page()
        vedette = page[page.index('class="sh-vedette"'):page.index('class="ac-sec sh-catalogue"')]
        self.assertIn("Petite barque", vedette)
        self.assertNotIn("data-ajout", vedette)

    def test_chaque_serie_du_site_a_son_rayon_meme_vide(self):
        self.autre.website_ids = [(4, self.site.id)]
        page = self._page()
        self.assertIn('id="sh-%s"' % self.serie.code, page)
        self.assertIn('id="sh-%s"' % self.autre.code, page)
        self.assertIn('href="#sh-%s"' % self.autre.code, page)
        self.assertEqual(page.count('class="sh-avenir"'), 1, "seule la série vide l'annonce")
        plein = page[page.index('id="sh-%s"' % self.serie.code):page.index('id="sh-%s"' % self.autre.code)]
        self.assertNotIn('class="sh-avenir"', plein)

    def test_un_rayon_montre_tout_le_payant_puis_une_rangee_de_gratuits(self):
        Build = self.env["besacraft.build"]
        for i in range(5):
            Build.create({"name": "Cabane %d" % i, "code": "998%d" % i, "enroll": "public",
                          "is_published": True, "serie_id": self.serie.id})
        page = self._page()
        rayon = page[page.index('id="sh-%s"' % self.serie.code):page.index('class="ac-sec sh-faq-sec"')]
        self.assertEqual(rayon.count('class="ac-build sh-carte"'), 4)
        self.assertIn("Grand navire", rayon, "le payant passe toujours")
        self.assertIn('href="/builds/collections?serie=%s"' % self.serie.code, rayon)

    def test_le_pack_n_apparait_que_si_la_serie_a_un_produit(self):
        self.assertNotIn('class="sh-pack"', self._page())
        self.serie.pack_product_id = self.pack
        page = self._page()
        self.assertIn('class="sh-pack"', page)
        self.assertIn('data-ajout="%d"' % self.pack.id, page)

    def test_un_build_achete_n_a_plus_de_bouton_panier(self):
        # An active company: the superuser's is archived on the dev database.
        societe = self.site.company_id or self.env["res.company"].search([], limit=1)
        zoe = self.env["res.users"].create({
            "name": "Zoé", "login": "zoe_shop", "password": "zoe_shop",
            "company_id": societe.id, "company_ids": [(6, 0, societe.ids)],
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})
        self.haut._action_add_members(zoe.partner_id)
        self.authenticate("zoe_shop", "zoe_shop")
        page = self._page()
        self.assertNotIn('data-ajout="%d"' % self.produit.id, page)
        self.assertIn("ac-etat--achete", page)

    def test_le_tiroir_suit_le_panier_website_sale(self):
        """The cart is the site's: a product put through /shop/cart/update_json shows in
        the drawer, and in the page's buttons once the page is reloaded."""
        self.url_open("/builds/shop")
        self.make_jsonrpc_request(
            "/shop/cart/update_json", {"product_id": self.produit.id, "add_qty": 1, "display": False})
        panier = self.make_jsonrpc_request("/builds/shop/panier", {})
        self.assertEqual(panier["produits"], [self.produit.id])
        self.assertEqual(panier["n"], 1)
        self.assertIn("Grand navire", panier["html"])
        page = self._page()
        self.assertRegex(page, r'data-ajout="%d"[^>]*aria-pressed="true"' % self.produit.id)

    def test_le_tiroir_est_introuvable_sur_un_site_sans_serie(self):
        self.serie.website_ids = [(3, self.site.id)]
        with self.assertRaises(Exception):
            self.make_jsonrpc_request("/builds/shop/panier", {})


@tagged("post_install", "-at_install")
class TestPack(TransactionCase):
    """Buying a series pack opens every paid guide of the series, those added since included."""

    def test_le_pack_donne_les_guides_payants_de_la_serie(self):
        serie = self.env.ref("besacraft_builds.serie_survie")
        autre = self.env.ref("besacraft_builds.serie_hardcore")
        partner = self.env["res.partner"].create({"name": "Zoé"})
        Produit = self.env["product.product"]
        pack = Produit.create({"name": "Pack", "type": "service", "list_price": 14.9})
        tuto = Produit.create({"name": "Tuto", "type": "service", "is_besacraft_tutorial": True})
        serie.pack_product_id = pack
        Build = self.env["besacraft.build"]
        dedans = Build.create({"name": "Dedans", "code": "9971", "enroll": "payment",
                               "product_id": tuto.id, "serie_id": serie.id})
        aussi = Build.create({"name": "Aussi", "code": "9972", "enroll": "payment",
                              "product_id": tuto.id, "serie_id": autre.id,
                              "serie_ids": [(4, serie.id)]})
        dehors = Build.create({"name": "Dehors", "code": "9973", "enroll": "payment",
                               "product_id": tuto.id, "serie_id": autre.id})
        commande = self.env["sale.order"].create({
            "partner_id": partner.id,
            "order_line": [(0, 0, {"product_id": pack.id, "product_uom_qty": 1})],
        })
        commande.action_confirm()
        self.assertTrue(dedans.is_accessible_by(partner))
        self.assertTrue(aussi.is_accessible_by(partner), "un build rangé aussi dans la série")
        self.assertFalse(dehors.is_accessible_by(partner))

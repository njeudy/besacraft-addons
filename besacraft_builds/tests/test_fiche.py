from odoo.tests import HttpCase, TransactionCase, tagged

from .test_v2 import GLB, WEBP


@tagged("post_install", "-at_install")
class TestFiche(HttpCase):
    """The product sheet /t/<n>, the 3D showcase page and the notice moved to /guide."""

    def setUp(self):
        super().setUp()
        self.site = self.env.ref("website.default_website")
        self.serie = self.env.ref("besacraft_builds.serie_survie")
        self.autre = self.env.ref("besacraft_builds.serie_hardcore")
        self.env["besacraft.serie"].search([]).write({"website_ids": [(3, self.site.id)]})
        self.serie.website_ids = [(4, self.site.id)]
        self.produit = self.env["product.product"].create({
            "name": "Tuto fiche", "type": "service", "is_besacraft_tutorial": True,
            "list_price": 4.9, "is_published": True})
        Build = self.env["besacraft.build"]
        self.payant = Build.create({
            "name": "Navire de fiche", "code": "9951", "enroll": "payment",
            "product_id": self.produit.id, "is_published": True, "serie_id": self.serie.id,
            "layer_count": 34, "block_count": 1870, "size_x": 17, "size_z": 42,
            "description": "<p>La quille posée dans l'eau.</p>"})
        self.gratuit = Build.create({
            "name": "Moulin de fiche", "code": "9952", "enroll": "public",
            "is_published": True, "serie_id": self.serie.id})
        self.payant.poser_paquet({"vitrine.glb": GLB, "face.webp": WEBP})
        self.payant.chapter_ids = [
            (0, 0, {"sequence": 1, "name": "La quille", "first_layer": 1, "last_layer": 2,
                    "free": True}),
            (0, 0, {"sequence": 2, "name": "Les membrures", "first_layer": 3, "last_layer": 4,
                    "free": True}),
            (0, 0, {"sequence": 3, "name": "Le pont", "first_layer": 5, "last_layer": 9}),
        ]
        Episode = self.env["besacraft.episode"]
        self.episode = Episode.create({
            "name": "Quinze morts", "serie_id": self.serie.id, "number": 1,
            "is_published": True, "youtube_url": "https://youtu.be/AAAAAAAAAAA",
            "build_ids": [(4, self.payant.id)]})
        self.a_venir = Episode.create({
            "name": "Episode a venir", "serie_id": self.serie.id, "number": 2,
            "is_published": True, "build_ids": [(4, self.payant.id)]})
        self.ailleurs = Episode.create({
            "name": "Episode d'une autre serie", "serie_id": self.autre.id, "number": 3,
            "is_published": True, "build_ids": [(4, self.payant.id)]})

    def _statut(self, url):
        return self.url_open(url, allow_redirects=False).status_code

    # --- la fiche ------------------------------------------------------------------------------

    def test_la_fiche_payante_se_vend(self):
        page = self.url_open("/t/9951")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Navire de fiche", page.text)
        self.assertIn(self.payant.price_label, page.text)
        self.assertIn('action="/shop/cart/update"', page.text)
        self.assertIn('name="product_id" value="%d"' % self.produit.id, page.text)
        self.assertIn("La quille posée dans l'eau.", page.text)

    def test_la_galerie_montre_la_vitrine_et_la_face_sans_charger_le_glb(self):
        page = self.url_open("/t/9951").text
        self.assertIn('data-iframe="/builds/9951/vitrine?seul=1"', page)
        self.assertIn("/besacraft.build/%d/box_face_image/" % self.payant.id, page)
        # La vitrine se charge à la demande : aucune iframe ni glb dans la page servie.
        self.assertNotIn("<iframe", page)
        self.assertNotIn(".glb", page)

    def test_les_chapitres_offerts_se_lancent(self):
        page = self.url_open("/t/9951").text
        # The site of the test database may speak French: the link, not its words.
        self.assertIn('class="ac-lien" href="/builds/9951?apercu=1"', page)
        self.assertIn("· 1, 2", page)
        self.assertLess(page.index("La quille"), page.index("Les membrures"))
        self.assertLess(page.index("Les membrures"), page.index("Le pont"))

    def test_les_episodes_du_site_seulement(self):
        page = self.url_open("/t/9951").text
        self.assertIn("Quinze morts", page)
        self.assertIn("Episode a venir", page)
        self.assertNotIn("Episode d'une autre serie", page,
                         "une série non publiée sur le site ne montre pas ses épisodes")

    def test_le_moment_ouvre_la_video_au_bon_endroit(self):
        self.env["besacraft.episode.appearance"].create({
            "episode_id": self.episode.id, "build_id": self.payant.id, "minute": 12 + 40 / 60})
        page = self.url_open("/t/9951").text
        self.assertIn("https://www.youtube.com/watch?v=AAAAAAAAAAA&amp;t=760s", page)
        self.assertIn("12:40", page)

    def test_la_fiche_gratuite_lance_le_build(self):
        page = self.url_open("/t/9952").text
        self.assertNotIn('action="/shop/cart/update"', page)
        self.assertIn('href="/builds/9952"', page)
        self.assertNotIn("data-iframe", page, "pas de glb, pas de vitrine")

    def test_la_fiche_garde_les_gardes(self):
        self.serie.website_ids = [(3, self.site.id)]
        self.autre.website_ids = [(4, self.site.id)]
        self.assertEqual(self._statut("/t/9951"), 404)
        self.assertEqual(self._statut("/builds/9951/vitrine"), 404)
        self.assertEqual(self._statut("/builds/9951/guide"), 404)

    # --- la vitrine 3D -------------------------------------------------------------------------

    def test_la_page_de_vitrine_charge_three_depuis_le_module(self):
        page = self.url_open("/builds/9951/vitrine")
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-glb="/besacraft/vitrine/9951.glb"', page.text)
        self.assertIn("/besacraft_builds/static/lib/three/three.module.min.js", page.text)
        self.assertNotIn("cdn.jsdelivr", page.text)
        self.assertNotIn("o_main_navbar", page.text)

    def test_pas_de_vitrine_sans_glb_ni_hors_publication(self):
        self.assertEqual(self._statut("/builds/9952/vitrine"), 404)
        self.payant.is_published = False
        self.assertEqual(self._statut("/builds/9951/vitrine"), 404)

    # --- la notice, à sa nouvelle adresse ------------------------------------------------------

    def test_la_notice_reste_joignable(self):
        page = self.url_open("/builds/9952/guide")
        self.assertEqual(page.status_code, 200)
        self.assertIn("bc_donnees", page.text)


@tagged("post_install", "-at_install")
class TestMoment(TransactionCase):

    def test_un_moment_range_le_build_dans_l_episode(self):
        serie = self.env.ref("besacraft_builds.serie_survie")
        build = self.env["besacraft.build"].create({
            "name": "Moment", "code": "9953", "serie_id": serie.id})
        episode = self.env["besacraft.episode"].create({"name": "Ep", "serie_id": serie.id})
        moment = self.env["besacraft.episode.appearance"].create({
            "episode_id": episode.id, "build_id": build.id, "minute": 1.5})
        self.assertIn(build, episode.build_ids)
        self.assertEqual(moment.seconds, 90)
        self.assertEqual(moment.timecode, "1:30")

import json

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestPages(HttpCase):
    """Les pages du catalogue sur un site qui publie la série `schematics`."""

    def setUp(self):
        super().setUp()
        self.site = self.env.ref("website.default_website")
        self.serie = self.env.ref("besacraft_builds.serie_survie")
        self.serie.website_ids = [(4, self.site.id)]
        self.produit = self.env["product.product"].create({
            "name": "Tuto test", "type": "service", "is_besacraft_tutorial": True,
            "list_price": 4.0, "is_published": True})
        Build = self.env["besacraft.build"]
        self.payant = Build.create({
            "name": "Build payant", "code": "9921", "enroll": "payment",
            "product_id": self.produit.id, "is_published": True,
            "serie_id": self.serie.id, "block_count": 120, "layer_count": 3})
        self.gratuit = Build.create({
            "name": "Build gratuit", "code": "9922", "enroll": "public",
            "is_published": True, "serie_id": self.serie.id,
            "block_count": 80, "layer_count": 2,
            "holo_data": json.dumps({"taille": [2, 2, 2], "couches": [[0, 0, 1, 1]]})})

    def _connecter_admin(self):
        """Log in as an existing website designer.

        Creating a user here is not an option: the base is multi-company and a new user's
        default company is not always one it may use. The test session skips the password
        check, so any active internal designer will do -- `base.user_admin` is archived or
        renamed on some bases.
        """
        designer = self.env.ref("website.group_website_designer")
        user = self.env["res.users"].search(
            [("share", "=", False), ("groups_id", "in", designer.id)], limit=1)
        self.assertTrue(user, "no active website designer on this database")
        self.authenticate(user.login, "sans-importance")
        return user

    def _statut(self, url):
        return self.url_open(url, allow_redirects=False).status_code

    # --- écran d'un build -----------------------------------------------------------------

    def test_l_ecran_d_un_build_repond(self):
        self.assertEqual(self._statut("/builds/9921"), 200)
        self.assertEqual(self._statut("/builds/9922"), 200)

    def test_l_ecran_d_un_build_hors_site_est_introuvable(self):
        autre = self.env.ref("besacraft_builds.serie_hardcore")
        autre.website_ids = [(3, self.site.id)]
        voisin = self.env["besacraft.build"].create({
            "name": "Hors site", "code": "9923", "is_published": True, "serie_id": autre.id})
        self.assertEqual(self._statut("/builds/%d" % int(voisin.code)), 404)
        self.serie.website_ids = [(3, self.site.id)]
        self.assertEqual(self._statut("/builds/9921"), 404)

    def test_le_bouton_d_achat_n_est_que_sur_un_payant_non_acquis(self):
        payant = self.url_open("/builds/9921").text
        self.assertIn('action="/shop/cart/update"', payant)
        self.assertIn("Obtenir ce tutoriel", payant)
        self.assertIn("4,00", payant)
        gratuit = self.url_open("/builds/9922").text
        self.assertNotIn("/shop/cart/update", gratuit)
        self.assertIn("Ouvrir le tuto", gratuit)

    def test_un_acquereur_voit_le_badge_et_plus_l_achat(self):
        admin = self._connecter_admin()
        self.payant._action_add_members(admin.partner_id)
        page = self.url_open("/builds/9921").text
        self.assertNotIn("/shop/cart/update", page)
        self.assertIn("Acheté", page)

    def test_l_apercu_montre_trois_couches_reelles(self):
        for sequence in (1, 2, 3):
            couche = self.env["besacraft.build.layer"].create({
                "build_id": self.payant.id, "sequence": sequence, "block_count": 10})
            self.env["besacraft.build.layer.line"].create({
                "layer_id": couche.id, "item_key": "minecraft:b%d" % sequence,
                "name_fr": "Bloc numero %d" % sequence, "qty": sequence})
        page = self.url_open("/builds/9921").text
        for sequence in (1, 2, 3):
            self.assertIn("Bloc numero %d" % sequence, page)

    def test_le_court_se_sert_avec_la_meme_garde(self):
        self.assertEqual(self._statut("/builds/9922/court"), 404, "pas de court posé")
        self.gratuit.short_video = "AAAAGGZ0eXBpc29t"
        self.assertEqual(self._statut("/builds/9922/court"), 200)
        self.serie.website_ids = [(3, self.site.id)]
        self.assertEqual(self._statut("/builds/9922/court"), 404)

    # --- tuto verrouillé --------------------------------------------------------------------

    def test_le_tuto_verrouille_montre_la_couche_1_et_pas_la_suivante(self):
        for sequence, nom in ((1, "Planches un"), (2, "Planches deux")):
            couche = self.env["besacraft.build.layer"].create({
                "build_id": self.payant.id, "sequence": sequence, "block_count": 5})
            self.env["besacraft.build.layer.line"].create({
                "layer_id": couche.id, "item_key": "minecraft:p%d" % sequence,
                "name_fr": nom, "qty": 5})
        page = self.url_open("/t/9921").text
        self.assertIn("Planches un", page)
        self.assertNotIn("Planches deux", page)
        self.assertIn("/shop/cart/update", page)

    # --- série et épisodes --------------------------------------------------------------------

    def test_la_page_de_serie_et_ses_episodes_repondent(self):
        self.assertEqual(self._statut("/builds/serie/schematics"), 200)
        self.assertEqual(self._statut("/builds/serie/schematics/episodes"), 200)

    def test_une_serie_non_publiee_sur_le_site_est_introuvable(self):
        self.env.ref("besacraft_builds.serie_hardcore").website_ids = [(3, self.site.id)]
        self.assertEqual(self._statut("/builds/serie/hardcore"), 404)
        self.assertEqual(self._statut("/builds/serie/hardcore/episodes"), 404)
        self.assertEqual(self._statut("/builds/serie/inconnue"), 404)

    def test_la_serie_sans_episode_montre_l_etat_vide(self):
        self.assertIn("Pas encore d'épisode", self.url_open("/builds/serie/schematics").text)

    def test_les_episodes_non_publies_ne_se_montrent_qu_aux_editeurs(self):
        episode = self.env["besacraft.episode"].create({
            "name": "Episode secret", "serie_id": self.serie.id, "number": 1,
            "youtube_url": "https://youtu.be/dQw4w9WgXcQ", "build_ids": [(4, self.gratuit.id)]})
        page = self.url_open("/builds/serie/schematics/episodes").text
        self.assertNotIn("Episode secret", page)
        self._connecter_admin()
        page = self.url_open("/builds/serie/schematics/episodes").text
        self.assertIn("Episode secret", page)
        self.assertIn("youtube-nocookie.com/embed/dQw4w9WgXcQ", page)
        self.assertIn('id="episode-%d"' % episode.id, page)
        self.assertIn("Build gratuit", page)

    def test_un_episode_publie_s_affiche_pour_tous(self):
        self.env["besacraft.episode"].create({
            "name": "Episode public", "serie_id": self.serie.id, "number": 2,
            "is_published": True})
        self.assertIn("Episode public", self.url_open("/builds/serie/schematics/episodes").text)
        self.assertIn("Episode public", self.url_open("/builds/serie/schematics").text)

    # --- catalogue et barre ---------------------------------------------------------------------

    def test_le_catalogue_porte_les_donnees_des_filtres(self):
        page = self.url_open("/builds").text
        for attribut in ('data-serie="schematics"', 'data-acces="payant"',
                         'data-acces="gratuit"', 'data-blocs="120"', 'data-couches="2"'):
            self.assertIn(attribut, page)
        self.assertIn("Tuto payant", page)

    def test_la_barre_porte_le_projet_quand_il_est_renseigne(self):
        self.assertNotIn(">Le projet<", self.url_open("/builds").text)
        self.site.besacraft_projet_url = "/builds-minecraft"
        page = self.url_open("/builds").text
        self.assertIn('href="/builds-minecraft"', page)
        self.assertIn(">Le projet<", page)

    # --- hologramme ---------------------------------------------------------------------------------

    def test_le_point_d_entree_holo_donne_un_build_et_des_chiffres(self):
        reponse = self.url_open("/besacraft/holo?code=9922")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.headers.get("Cache-Control"), "no-store")
        donnees = reponse.json()
        build = donnees["build"]
        self.assertEqual(build["code"], "9922")
        self.assertEqual(build["nom"], "Build gratuit")
        self.assertEqual(build["taille"], [2, 2, 2])
        self.assertEqual(build["couches"], [[0, 0, 1, 1]])
        self.assertEqual(build["url"], "/builds/9922")
        self.assertEqual((build["blocs"], build["couches_n"]), (80, 2))
        self.assertEqual(build["couleur"], self.serie.color)
        self.assertEqual(
            set(donnees["stats"]), {"builds", "blocs", "series"})
        self.assertGreaterEqual(donnees["stats"]["builds"], 2)

    def test_holo_sans_serie_renvoie_null_sans_404(self):
        self.site._besacraft_series().write({"website_ids": [(3, self.site.id)]})
        reponse = self.url_open("/besacraft/holo")
        self.assertEqual(reponse.status_code, 200)
        donnees = reponse.json()
        self.assertIsNone(donnees["build"])
        self.assertEqual(donnees["stats"], {"builds": 0, "blocs": 0, "series": 0})

    def test_holo_tire_parmi_les_builds_qui_ont_des_positions(self):
        # Le payant n'a pas de holo_data : seul le gratuit peut sortir (parmi ceux du test).
        for _ in range(5):
            donnees = self.url_open("/besacraft/holo?code=9921").json()
            self.assertIsNone(donnees["build"], "un build sans positions n'est jamais tiré")

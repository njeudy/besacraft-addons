from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestAcces(HttpCase):
    def setUp(self):
        super().setUp()
        # url_open tape le site par défaut, et le catalogue ne se sert que là où une
        # série est publiée. Sans elle les fiches répondent 404 — ce qui est le
        # comportement voulu ailleurs, mais pas ce que ces tests mesurent.
        self.site = self.env.ref("website.default_website")
        self.serie = self.env.ref("besacraft_builds.serie_survie")
        self.serie.website_ids = [(4, self.site.id)]
        self.produit = self.env["product.product"].create({
            "name": "Tuto test", "type": "service",
            "is_besacraft_tutorial": True, "list_price": 4.0,
            "is_published": True,
        })
        self.build = self.env["besacraft.build"].create({
            "name": "Build payant", "code": "911", "enroll": "payment",
            "product_id": self.produit.id, "is_published": True,
            "serie_id": self.serie.id,
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
        """Un voile devant une liste lisible dans le code source serait une serrure en carton.

        Seule la couche 1 est montrée, comme aperçu ; la suivante ne doit pas y être.
        """
        for sequence, nom in ((1, "Planches de chene"), (2, "Pierre taillee")):
            couche = self.env["besacraft.build.layer"].create({
                "build_id": self.build.id, "sequence": sequence, "block_count": 64})
            self.env["besacraft.build.layer.line"].create({
                "layer_id": couche.id, "item_key": "minecraft:block_%d" % sequence,
                "name_fr": nom, "qty": 64})
        self.build.layer_count = 2
        page = self.url_open("/t/911").text
        self.assertIn("Planches de chene", page)
        self.assertNotIn("Pierre taillee", page)

    def test_un_build_gratuit_s_ouvre_directement(self):
        self.build.write({"enroll": "public", "product_id": False})
        reponse = self.url_open("/t/911", allow_redirects=False)
        self.assertEqual(reponse.status_code, 200)

    def test_le_viewer_d_un_build_payant_ne_se_sert_pas(self):
        """Le viewer ne doit jamais partir par une URL devinable."""
        reponse = self.url_open("/besacraft/viewer/%d" % self.build.id, allow_redirects=False)
        self.assertIn(reponse.status_code, (303, 404))

    # Les implémentations du cœur lisent ces clés sans défaut : un dict vide lève.
    OPTIONS_RECHERCHE = {
        "displayDescription": True, "displayDetail": False,
        "displayExtraDetail": False, "displayExtraLink": False,
        "displayImage": False, "allowFuzzy": False,
    }

    def test_la_recherche_du_site_trouve_un_tuto(self):
        """Sans ça, le seul chemin vers /t/<n> est le catalogue.

        On cherche aussi par numéro : sur la boîte c'est le numéro qui est imprimé en
        grand, et c'est lui qu'on se fait répéter.
        """
        for terme in ("Build payant", "911"):
            _count, trouves, _fuzzy = self.site._search_with_fuzzy(
                "builds", terme, limit=5, order="", options=self.OPTIONS_RECHERCHE)
            resultats = self.site._search_render_results(trouves, limit=5)
            noms = [r["name"] for bloc in resultats for r in bloc["results_data"]]
            self.assertIn("Build payant", noms, "recherche « %s »" % terme)

    def test_la_recherche_ignore_les_tutos_hors_du_site(self):
        """Proposer un résultat qui mène à un 404 est pire que ne rien proposer.

        Interrogé sur « builds » et non sur « all » : `all` réveille aussi
        `website_appointment`, dont le `_search_get_detail` lit `request.env` et casse
        hors d'une requête HTTP. Ce n'est pas ce qu'on mesure ici.
        """
        self.assertIn("besacraft.build", [
            d["model"] for d in
            self.site._search_get_details("builds", "", self.OPTIONS_RECHERCHE)])
        self._retirer_le_site()
        self.assertNotIn("besacraft.build", [
            d["model"] for d in
            self.site._search_get_details("builds", "", self.OPTIONS_RECHERCHE)])

    def _retirer_le_site(self):
        """No series on the test site any more, whatever the host database carries."""
        self.site._besacraft_series().write({"website_ids": [(3, self.site.id)]})

    def test_sans_serie_publiee_les_pages_n_existent_pas(self):
        """Pas un rayon vide : la page ne doit pas exister du tout.

        Borner les enregistrements par site laissait les autres sites servir /builds
        avec leur propre habillage et zéro carte, ce qui a l'air cassé. Le viewer est
        testé aussi : sa route n'est pas `website=True` et lisait un `request.website`
        inexistant — elle répondait 500 au lieu de 404.
        """
        self._retirer_le_site()
        for url in ("/builds", "/t/911", "/besacraft/viewer/%d" % self.build.id):
            self.assertEqual(
                self.url_open(url, allow_redirects=False).status_code, 404,
                "%s devrait être introuvable sur un site sans série" % url)

    def _build_d_une_autre_serie(self):
        """A public build whose series is NOT published on the test site."""
        autre = self.env.ref("besacraft_builds.serie_hardcore")
        autre.website_ids = [(3, self.site.id)]
        piece = self.env["ir.attachment"].create({
            "name": "viewer.html", "datas": "PGh0bWw+PC9odG1sPg==",
            "mimetype": "text/html"})
        return self.env["besacraft.build"].create({
            "name": "Build voisin", "code": "912", "enroll": "public",
            "is_published": True, "serie_id": autre.id,
            "viewer_attachment_id": piece.id,
        })

    def test_un_site_ne_montre_que_les_series_qu_il_publie(self):
        """Le catalogue est servi, mais la série d'à côté n'y est ni listée ni ouverte."""
        autre = self._build_d_une_autre_serie()
        catalogue = self.url_open("/builds").text
        self.assertIn("Build payant", catalogue)
        self.assertNotIn(autre.name, catalogue)
        self.assertNotIn(autre.serie_id.name, catalogue, "son filtre non plus")
        for url in ("/t/912", "/besacraft/viewer/%d" % autre.id):
            self.assertEqual(
                self.url_open(url, allow_redirects=False).status_code, 404, url)

    def test_publier_la_serie_sur_le_site_ouvre_ses_builds(self):
        autre = self._build_d_une_autre_serie()
        autre.serie_id.website_ids = [(4, self.site.id)]
        self.assertIn(autre.name, self.url_open("/builds").text)
        self.assertEqual(self.url_open("/t/912", allow_redirects=False).status_code, 200)
        self.assertEqual(self.url_open(
            "/besacraft/viewer/%d" % autre.id, allow_redirects=False).status_code, 200)

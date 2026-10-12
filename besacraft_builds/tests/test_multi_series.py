from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestMultiSeries(HttpCase):
    """A build filed in several series: a Create farm is a survival building AND a
    steampunk machine. Filing it under one forced a choice, and the reader browsing the
    other series never found it."""

    def setUp(self):
        super().setUp()
        self.site = self.env.ref("website.default_website")
        self.principale = self.env.ref("besacraft_builds.serie_steampunk")
        self.seconde = self.env.ref("besacraft_builds.serie_survie")
        # Aucune série publiée ici au départ : chaque test dit laquelle il publie.
        self.env["besacraft.serie"].search([]).write({"website_ids": [(3, self.site.id)]})
        self.build = self.env["besacraft.build"].create({
            "name": "Ferme à blé rotative", "code": "900", "enroll": "public",
            "is_published": True, "serie_id": self.principale.id,
        })

    def test_le_build_connait_toutes_ses_series_la_principale_en_tete(self):
        self.build.serie_ids = [(4, self.seconde.id)]
        self.assertEqual(self.build.series(), self.principale | self.seconde)
        self.assertEqual(self.build.series()[0], self.principale,
                         "la principale vient d'abord : c'est elle qui habille la page")

    def test_une_serie_supplementaire_suffit_a_montrer_le_build(self):
        """Le site ne publie que la seconde série : le build doit quand même s'y voir.

        Sans ça, ajouter un build à une série ne le rendait visible nulle part de plus --
        le périmètre ne regardait que la série principale.
        """
        self.build.serie_ids = [(4, self.seconde.id)]
        self.seconde.website_ids = [(4, self.site.id)]
        self.assertTrue(self.build.is_shown_on(self.site))
        self.assertIn(self.build.name, self.url_open("/builds").text)
        self.assertEqual(self.url_open("/builds/900", allow_redirects=False).status_code, 200)

    def test_sans_serie_supplementaire_le_build_reste_hors_du_site(self):
        """Le témoin du test précédent : c'est bien l'ajout qui ouvre la porte."""
        self.seconde.website_ids = [(4, self.site.id)]
        self.assertFalse(self.build.is_shown_on(self.site))
        self.assertEqual(self.url_open("/builds/900", allow_redirects=False).status_code, 404)

    def test_la_page_d_une_serie_liste_les_builds_qui_s_y_ajoutent(self):
        self.build.serie_ids = [(4, self.seconde.id)]
        self.seconde.website_ids = [(4, self.site.id)]
        page = self.url_open("/builds/serie/%s" % self.seconde.code)
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.build.name, page.text)

    def test_la_carte_porte_ses_deux_series_pour_le_filtre(self):
        """Le filtre du catalogue se joue dans le navigateur, sur `data-series`."""
        self.build.serie_ids = [(4, self.seconde.id)]
        self.principale.website_ids = [(4, self.site.id)]
        page = self.url_open("/builds").text
        self.assertIn('data-series="%s %s"' % (self.principale.code, self.seconde.code), page)

    def test_le_compteur_du_filtre_compte_le_build_dans_chaque_serie(self):
        """Un filtre annoncé à 0 alors qu'il montre une carte est pire que pas de compteur."""
        self.build.serie_ids = [(4, self.seconde.id)]
        (self.principale | self.seconde).website_ids = [(4, self.site.id)]
        site = self.env["website"].browse(self.site.id)
        builds = self.env["besacraft.build"].search(
            self.env["besacraft.build"]._domaine_site(site))
        for serie in (self.principale, self.seconde):
            self.assertIn(self.build, builds.filtered(lambda b, s=serie: s in b.series()),
                          "compté dans %s" % serie.code)

    def test_un_build_voisin_peut_venir_de_la_serie_supplementaire(self):
        """La page d'un build propose ses voisins : ceux qui partagent une série."""
        self.build.serie_ids = [(4, self.seconde.id)]
        voisin = self.env["besacraft.build"].create({
            "name": "Hutte de survie", "code": "901", "enroll": "public",
            "is_published": True, "serie_id": self.seconde.id,
        })
        self.seconde.website_ids = [(4, self.site.id)]
        self.assertIn(voisin.name, self.url_open("/builds/900").text)

    def test_la_recherche_du_site_trouve_un_build_par_sa_serie_supplementaire(self):
        self.build.serie_ids = [(4, self.seconde.id)]
        self.seconde.website_ids = [(4, self.site.id)]
        site = self.env["website"].browse(self.site.id)
        options = {"displayDescription": True, "displayDetail": False,
                   "displayExtraDetail": False, "displayExtraLink": False,
                   "displayImage": False, "allowFuzzy": False}
        _count, trouves, _fuzzy = site._search_with_fuzzy(
            "builds", "900", limit=5, order="", options=options)
        noms = [r["name"] for bloc in site._search_render_results(trouves, limit=5)
                for r in bloc["results_data"]]
        self.assertIn(self.build.name, noms)

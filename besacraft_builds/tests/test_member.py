from odoo import http
from odoo.tests import HttpCase, TransactionCase, tagged


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
        self.build.invalidate_recordset(["member_ids", "partner_ids"])
        self.assertEqual(self.build.partner_ids._name, "res.partner")
        self.assertIn(self.partner, self.build.partner_ids)

    def test_le_code_reste_unique_apres_ajout_des_contraintes(self):
        """La tache 4 etend _sql_constraints : l'unicite du code ne doit pas disparaitre."""
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.env["besacraft.build"].create({
                    "name": "Doublon", "code": "9142",
                    "serie_id": self.env.ref("besacraft_builds.serie_survie").id})


@tagged("post_install", "-at_install")
class TestRejoindre(HttpCase):
    """La route qui met un lecteur connecté dans les membres d'un build gratuit."""

    def setUp(self):
        super().setUp()
        self.site = self.env.ref("website.default_website")
        self.serie = self.env.ref("besacraft_builds.serie_survie")
        self.serie.website_ids = [(4, self.site.id)]
        # Un utilisateur portail créé ici : la base de dev n'a pas les données de démo.
        # Une société ACTIVE : celle du superutilisateur est archivée sur la base de dev,
        # et `company_ids` la filtre à la lecture — la contrainte tombe alors sur une liste vide.
        societe = self.site.company_id or self.env["res.company"].search([], limit=1)
        self.utilisateur = self.env["res.users"].create({
            "name": "Zoé", "login": "zoe-rejoindre", "password": "zoe-rejoindre",
            "company_id": societe.id, "company_ids": [(6, 0, societe.ids)],
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})
        self.gratuit = self.env["besacraft.build"].create({
            "name": "Taverne libre", "code": "9145",
            "serie_id": self.serie.id, "is_published": True})
        produit = self.env["product.product"].create({
            "name": "Tuto payant", "type": "service", "is_besacraft_tutorial": True,
            "list_price": 4.0, "is_published": True})
        self.payant = self.env["besacraft.build"].create({
            "name": "Taverne payante", "code": "9146", "serie_id": self.serie.id,
            "enroll": "payment", "product_id": produit.id, "is_published": True})

    def _rejoindre(self, build, **kw):
        return self.url_open(
            "/builds/%d/rejoindre" % int(build.code),
            data={"csrf_token": http.Request.csrf_token(self)}, **kw)

    def test_rejoindre_un_build_gratuit(self):
        """A logged-in visitor adds a free build to their books."""
        self.authenticate("zoe-rejoindre", "zoe-rejoindre")
        reponse = self._rejoindre(self.gratuit)
        self.assertEqual(reponse.status_code, 200)
        membre = self.env["besacraft.build.member"].search([
            ("build_id", "=", self.gratuit.id),
            ("partner_id", "=", self.utilisateur.partner_id.id)])
        self.assertEqual(len(membre), 1)

    def test_rejoindre_un_build_payant_est_refuse(self):
        """Joining is for free builds only: a paying one goes through the shop."""
        self.authenticate("zoe-rejoindre", "zoe-rejoindre")
        self.assertEqual(self._rejoindre(self.payant).status_code, 403)

    def test_rejoindre_deux_fois_ne_cree_quun_membre(self):
        """_action_add_members is idempotent, and the route must stay so."""
        self.authenticate("zoe-rejoindre", "zoe-rejoindre")
        for _ in range(2):
            self._rejoindre(self.gratuit)
        self.assertEqual(self.env["besacraft.build.member"].search_count(
            [("build_id", "=", self.gratuit.id)]), 1)

    def test_un_visiteur_non_connecte_ne_rejoint_pas(self):
        """auth="user": the public visitor is sent to the login, no member is created."""
        self.authenticate(None, None)
        self._rejoindre(self.gratuit)
        self.assertEqual(self.env["besacraft.build.member"].search_count(
            [("build_id", "=", self.gratuit.id)]), 0)

    def test_le_bouton_s_affiche_tant_qu_on_n_est_pas_membre(self):
        """The page offers the button, and stops offering it once joined."""
        self.authenticate("zoe-rejoindre", "zoe-rejoindre")
        self.assertIn("/builds/9145/rejoindre", self.url_open("/builds/9145").text)
        self.gratuit._action_add_members(self.utilisateur.partner_id)
        self.assertNotIn("/builds/9145/rejoindre", self.url_open("/builds/9145").text)

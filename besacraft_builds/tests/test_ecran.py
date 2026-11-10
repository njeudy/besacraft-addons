import base64
import json

from odoo.tests import HttpCase, tagged

# A viewer laid out as buildplan writes it: its data as one-line JSON constants.
DATA = {"name": "Navire", "block_count": 6, "layers": [
    {"y": i, "blocks": [[i, 0, 1], [i, 1, 1]]} for i in range(3)]}
GUIDE = {"start": 0,
         "zones": [{"nom": "La quille"}, {"nom": "Les membrures"}, {"nom": "Le pont"}],
         "steps": [{"zone": z, "layer": z, "item": "minecraft:bloc_%d" % z, "count": 2,
                    "blocks": []} for z in range(3)]}
VIEWER = ("<html><script>\nconst DATA = %s;\nconst GUIDE_DATA = %s;\n"
          "document.title = 'viewer';\n</script></html>") % (json.dumps(DATA), json.dumps(GUIDE))


@tagged("post_install", "-at_install")
class TestEcranBuild(HttpCase):
    """/builds/<n>: the guide full screen, and the veil of a locked build."""

    def setUp(self):
        super().setUp()
        self.site = self.env.ref("website.default_website")
        self.serie = self.env.ref("besacraft_builds.serie_survie")
        self.serie.website_ids = [(4, self.site.id)]
        self.produit = self.env["product.product"].create({
            "name": "Tuto navire", "type": "service", "is_besacraft_tutorial": True,
            "list_price": 4.0, "is_published": True})
        self.piece = self.env["ir.attachment"].create({
            "name": "viewer.html", "mimetype": "text/html",
            "datas": base64.b64encode(VIEWER.encode())})
        self.build = self.env["besacraft.build"].create({
            "name": "Navire d'essai", "code": "9961", "enroll": "payment",
            "product_id": self.produit.id, "is_published": True, "serie_id": self.serie.id,
            "layer_count": 3, "viewer_attachment_id": self.piece.id,
            "chapter_ids": [
                (0, 0, {"sequence": 1, "name": "La quille", "first_layer": 1,
                        "last_layer": 1, "free": True}),
                (0, 0, {"sequence": 2, "name": "Les membrures", "first_layer": 2,
                        "last_layer": 2}),
                (0, 0, {"sequence": 3, "name": "Le pont", "first_layer": 3,
                        "last_layer": 3}),
            ]})
        self.viewer = "/besacraft/viewer/%d" % self.build.id

    def _get(self, url):
        return self.url_open(url, allow_redirects=False)

    def _connecter_admin(self):
        designer = self.env.ref("website.group_website_designer")
        user = self.env["res.users"].search(
            [("share", "=", False), ("groups_id", "in", designer.id)], limit=1)
        self.authenticate(user.login, user.login)
        return user

    def test_sans_acces_le_guide_ne_se_charge_pas(self):
        """The veil is not a lock painted on: the page does not even name the full guide."""
        page = self._get("/builds/9961").text
        self.assertIn("acb-voile", page)
        self.assertNotIn('data-src="%s' % self.viewer, page)
        self.assertIn('data-apercu="%s?apercu=1"' % self.viewer, page)
        self.assertIn('action="/shop/cart/update"', page)

    def test_le_voile_dit_quels_chapitres_sont_fermes(self):
        page = self._get("/builds/9961").text
        self.assertEqual(page.count('class="is-libre"'), 1)
        self.assertEqual(page.count('class="is-clos"'), 2)
        self.assertIn("La quille", page)

    def test_l_apercu_direct_est_annonce_a_la_page(self):
        self.assertIn('data-apercu-direct="1"', self._get("/builds/9961?apercu=1").text)
        self.assertNotIn("data-apercu-direct", self._get("/builds/9961").text)

    def test_avec_acces_le_guide_se_charge_et_l_hologramme_suit(self):
        admin = self._connecter_admin()
        self.build._action_add_members(admin.partner_id)
        page = self._get("/builds/9961").text
        self.assertNotIn("acb-voile", page)
        self.assertIn('data-src="%s"' % self.viewer, page)
        self.assertIn('data-src="%s?holo=1"' % self.viewer, self._get("/builds/9961?holo=1").text)

    def test_un_build_gratuit_s_ouvre_sans_voile(self):
        self.build.write({"enroll": "public", "product_id": False})
        page = self._get("/builds/9961").text
        self.assertNotIn("acb-voile", page)
        self.assertIn('data-src="%s"' % self.viewer, page)

    def test_sans_guide_la_page_le_dit(self):
        self.build.write({"enroll": "public", "product_id": False,
                          "viewer_attachment_id": False})
        page = self._get("/builds/9961").text
        self.assertIn("acb-vide", page)
        self.assertNotIn("<iframe", page)

    def test_un_build_sur_invitation_n_a_ni_achat_ni_viewer(self):
        self.build.write({"enroll": "invite", "product_id": False})
        page = self._get("/builds/9961").text
        self.assertIn("acb-voile", page)
        self.assertNotIn("/shop/cart/update", page)
        self.assertEqual(self._get(self.viewer).status_code, 404)

    # --- the cut-down viewer ------------------------------------------------------------

    def _donnees(self, html, nom):
        debut = html.index("const %s = " % nom) + len("const %s = " % nom)
        return json.JSONDecoder().raw_decode(html, debut)[0]

    def test_l_apercu_ne_porte_que_les_chapitres_offerts(self):
        reponse = self._get(self.viewer + "?apercu=1")
        self.assertEqual(reponse.status_code, 200)
        html = reponse.text
        data, guide = self._donnees(html, "DATA"), self._donnees(html, "GUIDE_DATA")
        self.assertEqual(len(data["layers"]), 1)
        self.assertEqual(data["block_count"], 2)
        self.assertEqual([z["nom"] for z in guide["zones"]], ["La quille"])
        self.assertEqual([s["zone"] for s in guide["steps"]], [0])
        self.assertNotIn("minecraft:bloc_1", html)
        self.assertIn("document.title = 'viewer';", html, "the viewer's code is untouched")

    def test_le_viewer_complet_reste_ferme(self):
        self.assertEqual(self._get(self.viewer).status_code, 303)

    def test_le_decalage_du_viewer_compte_dans_la_coupe(self):
        self.build.layer_offset = 1
        data = self._donnees(self._get(self.viewer + "?apercu=1").text, "DATA")
        self.assertEqual(len(data["layers"]), 2)

    def test_sans_chapitre_offert_pas_d_apercu(self):
        self.build.chapter_ids.write({"free": False})
        self.assertEqual(self._get(self.viewer + "?apercu=1").status_code, 404)
        self.assertNotIn("data-apercu=", self._get("/builds/9961").text)

    def test_seule_la_tete_des_chapitres_offerts_compte(self):
        """A free chapter after a locked one cannot be played without the locked one."""
        self.build.chapter_ids[0].free = False
        self.build.chapter_ids[2].free = True
        self.assertFalse(self.build._chapitres_offerts())

    def test_un_viewer_d_une_autre_forme_ne_donne_pas_d_apercu(self):
        self.piece.datas = base64.b64encode(b"<html>no data here</html>")
        self.assertIsNone(self.build._viewer_apercu())

    def test_un_acquereur_recoit_le_viewer_complet_meme_avec_apercu(self):
        admin = self._connecter_admin()
        self.build._action_add_members(admin.partner_id)
        data = self._donnees(self._get(self.viewer + "?apercu=1").text, "DATA")
        self.assertEqual(len(data["layers"]), 3)

    def test_les_gardes_du_site_valent_pour_l_ecran_et_l_apercu(self):
        self.serie.website_ids = [(3, self.site.id)]
        for url in ("/builds/9961", self.viewer + "?apercu=1"):
            self.assertEqual(self._get(url).status_code, 404, url)

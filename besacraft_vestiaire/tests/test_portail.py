import base64
import re

from odoo.tests import common, tagged

from .test_images import png


@tagged("post_install", "-at_install")
class TestPortail(common.HttpCase):
    def setUp(self):
        super().setUp()
        self.user = self.env["res.users"].create({
            "name": "Zoé", "login": "zoe-portail", "password": "zoe-portail-123",
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})
        self.zoe = self.user.partner_id
        self.zoe.write({"minecraft_uuid": "cc67e9f6625340d4813855e5fecc4c10",
                        "minecraft_login": "zoejeudy"})
        autre = self.env["res.partner"].create({"name": "Autre"})
        self.skin_autre = self.env["besacraft.vestiaire.skin"].create({
            "partner_id": autre.id, "image": base64.b64encode(png(64, 64))})
        Cape = self.env["besacraft.vestiaire.cape"]
        self.cape = Cape.create({"name": "Cuivre", "image": base64.b64encode(png(64, 32))})
        self.cape_etrangere = Cape.create({"name": "Or", "image": base64.b64encode(png(64, 32))})
        self.zoe._vestiaire_offrir_cape(self.cape)

    def _skin(self, name, actif=False):
        return self.env["besacraft.vestiaire.skin"].create({
            "partner_id": self.zoe.id, "name": name, "actif": actif,
            "image": base64.b64encode(png(64, 64))})

    def test_page_visible(self):
        self.authenticate("zoe-portail", "zoe-portail-123")
        self.assertEqual(self.url_open("/my/vestiaire").status_code, 200)

    def _csrf(self):
        page = self.url_open("/my/vestiaire").text
        return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)

    def test_depot_d_un_skin(self):
        self.authenticate("zoe-portail", "zoe-portail-123")
        self.url_open("/my/vestiaire/skin/ajouter",
                      data={"name": "Rose", "modele": "slim", "csrf_token": self._csrf()},
                      files={"image": ("rose.png", png(64, 64), "image/png")})
        self.assertEqual(self.zoe.vestiaire_skin_ids.name, "Rose")
        self.assertEqual(self.zoe.vestiaire_skin_ids.modele, "slim")
        self.assertTrue(self.zoe.vestiaire_skin_ids.actif)

    def test_un_mauvais_fichier_est_refuse_proprement(self):
        self.authenticate("zoe-portail", "zoe-portail-123")
        page = self.url_open("/my/vestiaire/skin/ajouter",
                             data={"name": "X", "csrf_token": self._csrf()},
                             files={"image": ("x.png", b"pas une image", "image/png")})
        self.assertEqual(page.status_code, 200)
        self.assertFalse(self.zoe.vestiaire_skin_ids)

    def test_l_erreur_d_image_est_en_francais(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.user.lang = "fr_FR"
        self.authenticate("zoe-portail", "zoe-portail-123")
        page = self.url_open("/my/vestiaire/skin/ajouter",
                             data={"name": "X", "csrf_token": self._csrf()},
                             files={"image": ("x.png", b"pas une image", "image/png")})
        self.assertIn("Le fichier n&#39;est pas une image valide.", page.text)

    def test_un_champ_image_qui_n_est_pas_un_fichier(self):
        self.authenticate("zoe-portail", "zoe-portail-123")
        page = self.url_open("/my/vestiaire/skin/ajouter",
                             data={"name": "X", "image": "texte", "csrf_token": self._csrf()})
        self.assertEqual(page.status_code, 200)
        self.assertFalse(self.zoe.vestiaire_skin_ids)

    def test_une_cape_inconnue_ne_change_rien(self):
        self.zoe.sudo().vestiaire_cape_id = self.cape
        self.authenticate("zoe-portail", "zoe-portail-123")
        self.url_open("/my/vestiaire/cape", data={"cape_id": "999999", "csrf_token": self._csrf()})
        self.assertEqual(self.zoe.vestiaire_cape_id, self.cape)

    def test_le_deuxieme_skin_n_est_pas_actif(self):
        premier = self._skin("Premier", actif=True)
        self.authenticate("zoe-portail", "zoe-portail-123")
        self.url_open("/my/vestiaire/skin/ajouter",
                      data={"name": "Second", "csrf_token": self._csrf()},
                      files={"image": ("s.png", png(64, 32), "image/png")})
        self.assertEqual(len(self.zoe.vestiaire_skin_ids), 2)
        self.assertEqual(self.zoe.vestiaire_skin_ids.filtered("actif"), premier)

    def test_on_ne_touche_pas_au_skin_d_un_autre(self):
        self.authenticate("zoe-portail", "zoe-portail-123")
        csrf = self._csrf()
        self.url_open("/my/vestiaire/skin/%s/activer" % self.skin_autre.id,
                      data={"csrf_token": csrf})
        self.assertFalse(self.skin_autre.actif)
        self.url_open("/my/vestiaire/skin/%s/supprimer" % self.skin_autre.id,
                      data={"csrf_token": csrf})
        self.assertTrue(self.skin_autre.exists())

    def test_activer_et_supprimer_son_skin(self):
        premier = self._skin("Premier", actif=True)
        second = self._skin("Second")
        self.authenticate("zoe-portail", "zoe-portail-123")
        csrf = self._csrf()
        self.url_open("/my/vestiaire/skin/%s/activer" % second.id, data={"csrf_token": csrf})
        self.assertTrue(second.actif)
        self.assertFalse(premier.actif)
        self.url_open("/my/vestiaire/skin/%s/supprimer" % premier.id, data={"csrf_token": csrf})
        self.assertFalse(premier.exists())

    def test_porter_une_cape_possedee_puis_aucune(self):
        self.authenticate("zoe-portail", "zoe-portail-123")
        csrf = self._csrf()
        self.url_open("/my/vestiaire/cape", data={"cape_id": self.cape.id, "csrf_token": csrf})
        self.assertEqual(self.zoe.vestiaire_cape_id, self.cape)
        self.url_open("/my/vestiaire/cape", data={"cape_id": "", "csrf_token": csrf})
        self.assertFalse(self.zoe.vestiaire_cape_id)

    def test_une_cape_non_possedee_est_refusee(self):
        self.authenticate("zoe-portail", "zoe-portail-123")
        self.url_open("/my/vestiaire/cape",
                      data={"cape_id": self.cape_etrangere.id, "csrf_token": self._csrf()})
        self.assertFalse(self.zoe.vestiaire_cape_id)

    def test_un_compte_non_valide_est_renvoye_vers_my(self):
        self.zoe.minecraft_uuid = False
        self.authenticate("zoe-portail", "zoe-portail-123")
        reponse = self.url_open("/my/vestiaire", allow_redirects=False)
        self.assertEqual(reponse.status_code, 303)
        self.assertTrue(reponse.headers["Location"].endswith("/my"))

    def test_l_entree_du_vestiaire_dans_my(self):
        self.authenticate("zoe-portail", "zoe-portail-123")
        self.assertIn("/my/vestiaire", self.url_open("/my").text)
        self.zoe.minecraft_uuid = False
        self.assertNotIn("/my/vestiaire", self.url_open("/my").text)

    def test_le_modele_du_skin_est_traduit(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.user.lang = "fr_FR"
        self._skin("Mon skin")
        self.authenticate("zoe-portail", "zoe-portail-123")
        page = self.url_open("/my/vestiaire").text
        self.assertIn(">Classique<", page)
        self.assertNotIn(">Classic<", page)

    def test_nosniff_sur_l_apercu(self):
        skin = self._skin("Rose")
        self.authenticate("zoe-portail", "zoe-portail-123")
        r = self.url_open("/my/vestiaire/skin/%s/apercu" % skin.id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")

    def test_apercu_d_un_skin_etranger_en_404_sans_avertissement(self):
        self.authenticate("zoe-portail", "zoe-portail-123")
        with self.assertNoLogs("odoo.http", level="WARNING"):
            r = self.url_open("/my/vestiaire/skin/%s/apercu" % self.skin_autre.id)
        self.assertEqual(r.status_code, 404)

    def test_le_groupe_createur_n_eleve_pas_un_portail_en_interne(self):
        self.env.ref("besacraft_vestiaire.group_vestiaire_createur").users = [(4, self.user.id)]
        self.assertTrue(self.user.share)
        self.assertFalse(self.user.has_group("base.group_user"))

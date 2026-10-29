import base64

from odoo.tests import common, tagged

from .test_images import png


@tagged("post_install", "-at_install")
class TestCsl(common.HttpCase):
    def setUp(self):
        super().setUp()
        self.zoe = self.env["res.partner"].create({
            "name": "Zoé", "minecraft_login": "ZoeJeudy",
            "minecraft_uuid": "cc67e9f6625340d4813855e5fecc4c10"})
        self.env["res.users"].create({
            "name": "Zoé", "login": "zoe-csl", "partner_id": self.zoe.id,
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})
        self.skin = self.env["besacraft.vestiaire.skin"].create({
            "partner_id": self.zoe.id, "image": base64.b64encode(png(64, 64)),
            "modele": "slim", "actif": True})
        self.cape = self.env["besacraft.vestiaire.cape"].create({
            "name": "Cuivre", "image": base64.b64encode(png(64, 32)),
            "image_elytre": base64.b64encode(png(128, 64))})
        self.zoe._vestiaire_offrir_cape(self.cape)
        self.zoe.vestiaire_cape_id = self.cape

    def _compte(self, login, uuid, actif=True):
        partner = self.env["res.partner"].create({
            "name": login, "minecraft_login": login, "minecraft_uuid": uuid})
        user = self.env["res.users"].create({
            "name": login, "login": "%s-%s-csl" % (login, uuid[:4]), "partner_id": partner.id,
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})
        user.active = actif
        return partner

    def test_profil_complet(self):
        r = self.url_open("/csl/ZoeJeudy.json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Cache-Control"], "no-cache")
        self.assertEqual(r.json(), {
            "username": "ZoeJeudy",
            "skins": {"slim": self.skin.empreinte},
            "cape": self.cape.empreinte,
            "elytra": self.cape.empreinte_elytre})

    def test_casse_ignoree(self):
        self.assertEqual(self.url_open("/csl/zoejeudy.json").status_code, 200)

    def test_sans_cape_ni_skin_les_cles_sont_absentes(self):
        self.zoe.vestiaire_cape_id = False
        self.skin.unlink()
        self.assertEqual(self.url_open("/csl/ZoeJeudy.json").json(), {"username": "ZoeJeudy"})

    def test_inconnu_et_non_valide_en_404(self):
        self.assertEqual(self.url_open("/csl/Personne.json").status_code, 404)
        self.zoe.user_ids.active = False
        self.assertEqual(self.url_open("/csl/ZoeJeudy.json").status_code, 404)

    def test_texture_servie_avec_cache(self):
        r = self.url_open("/csl/textures/%s" % self.skin.empreinte)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "image/png")
        self.assertIn("immutable", r.headers["Cache-Control"])
        self.assertEqual(self.url_open("/csl/textures/%s" % self.cape.empreinte_elytre).status_code, 200)

    def test_texture_inconnue_ou_non_valide_en_404(self):
        self.assertEqual(self.url_open("/csl/textures/%s" % ("0" * 64)).status_code, 404)
        self.assertEqual(self.url_open("/csl/textures/pas-une-empreinte").status_code, 404)
        self.zoe.user_ids.active = False
        self.assertEqual(self.url_open("/csl/textures/%s" % self.skin.empreinte).status_code, 404)

    def test_pseudo_sans_joker_sql(self):
        self.assertEqual(self.url_open("/csl/%25.json").status_code, 404)
        self._compte("ZoeXJeudy", "11111111111111111111111111111111")
        self.assertEqual(self.url_open("/csl/Zoe_Jeudy.json").status_code, 404)
        self.assertEqual(self.url_open("/csl/ZoeXJeudy.json").status_code, 200)

    def test_pseudo_en_double_prend_le_compte_valide(self):
        invalide = self._compte("Doublon", "22222222222222222222222222222222", actif=False)
        valide = self._compte("Doublon", "33333333333333333333333333333333")
        self.assertLess(invalide.id, valide.id)
        self.assertEqual(self.url_open("/csl/Doublon.json").status_code, 200)

    def test_texture_partagee_prend_le_proprietaire_valide(self):
        autre = self._compte("Autre", "44444444444444444444444444444444", actif=False)
        self.env["besacraft.vestiaire.skin"].create({
            "partner_id": autre.id, "image": base64.b64encode(png(64, 64)),
            "modele": "slim", "actif": True})
        self.assertEqual(self.skin.empreinte, autre.vestiaire_skin_ids.empreinte)
        self.assertEqual(self.url_open("/csl/textures/%s" % self.skin.empreinte).status_code, 200)

    def test_texture_inactive_non_servie(self):
        self.skin.actif = False
        self.assertEqual(self.url_open("/csl/textures/%s" % self.skin.empreinte).status_code, 404)

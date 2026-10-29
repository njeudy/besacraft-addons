from odoo.addons.besacraft_minecraft_api.controllers import base
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestApi(common.HttpCase):
    def setUp(self):
        super().setUp()
        base._passages.clear()
        self.addCleanup(base._passages.clear)
        self.zoe = self.env["res.partner"].create({
            "name": "Zoé", "minecraft_login": "zoejeudy",
            "minecraft_uuid": "cc67e9f6625340d4813855e5fecc4c10"})
        self.jeton = self.env["besacraft.mc.session"]._ouvrir(self.zoe).token

    def _moi(self, jeton):
        return self.url_open("/mc/v1/vestiaire/moi",
                             headers={"Authorization": "Bearer %s" % jeton})

    def test_sans_jeton_401(self):
        self.assertEqual(self._moi("invente").status_code, 401)

    def test_contact_sans_utilisateur_403_avec_lien(self):
        r = self._moi(self.jeton)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["erreur"], "compte_non_valide")
        self.assertIn("/vestiaire/demande?code=", r.json()["url"])

    def test_compte_valide(self):
        self.env["res.users"].create({
            "name": "Zoé", "login": "zoe-api", "partner_id": self.zoe.id,
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})
        r = self._moi(self.jeton)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"pseudo": "zoejeudy", "skin": None, "cape": None})

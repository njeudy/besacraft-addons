import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.besacraft_minecraft_api.controllers import base
from odoo.tests import common, tagged

MOJANG = ("odoo.addons.besacraft_minecraft_api.models"
          ".besacraft_mc_session.requests.get")
JSON = {"Content-Type": "application/json"}
UUID = "cc67e9f6625340d4813855e5fecc4c10"


class _Reponse:
    status_code = 200
    content = b"x"

    def json(self):
        return {"id": UUID, "name": "zoejeudy"}


@tagged("post_install", "-at_install")
class TestCode(common.HttpCase):
    def setUp(self):
        super().setUp()
        base._passages.clear()
        self.addCleanup(base._passages.clear)
        self.Code = self.env["besacraft.vestiaire.code"]

    def _session(self):
        server_id = self.url_open("/mc/v1/defi", data="{}", headers=JSON).json()["server_id"]
        return self.url_open("/mc/v1/session", headers=JSON, data=json.dumps(
            {"pseudo": "zoejeudy", "server_id": server_id}))

    def test_un_code_expire_ne_se_retrouve_pas(self):
        code = self.Code._emettre(UUID, "zoejeudy")
        self.assertEqual(self.Code._trouver(code.code), code)
        code.expire_le = fields.Datetime.now() - timedelta(minutes=1)
        self.assertFalse(self.Code._trouver(code.code))

    def test_un_code_inconnu_ne_se_retrouve_pas(self):
        self.assertFalse(self.Code._trouver("inexistant00"))
        self.assertFalse(self.Code._trouver(""))

    def test_le_code_fait_douze_caracteres(self):
        self.assertRegex(self.Code._emettre(UUID, "zoejeudy").code, r"^[A-Za-z0-9]{12}$")

    @patch(MOJANG, return_value=_Reponse())
    def test_un_pseudo_change_est_mis_a_jour(self, _get):
        zoe = self.env["res.partner"].create({
            "name": "Zoé", "minecraft_uuid": UUID, "minecraft_login": "ancien_pseudo"})
        self.assertEqual(self._session().status_code, 200)
        zoe.invalidate_recordset()
        self.assertEqual(zoe.minecraft_login, "zoejeudy")

    @patch(MOJANG, return_value=_Reponse())
    def test_un_joueur_sans_contact_recoit_un_lien_de_demande(self, _get):
        reponse = self._session()
        self.assertEqual(reponse.status_code, 404)
        corps = reponse.json()
        self.assertEqual(corps["erreur"], "compte_non_lie")
        self.assertIn("/vestiaire/demande?code=", corps["url"])
        code = self.Code._trouver(corps["code"])
        self.assertEqual(code.uuid, UUID)
        self.assertEqual(code.pseudo, "zoejeudy")

import json
from datetime import timedelta
from unittest.mock import patch

import requests

from odoo import fields
from odoo.tests import common, tagged

CHEMIN_SESSION = ("odoo.addons.besacraft_minecraft_api.models"
                  ".besacraft_mc_session.requests.get")
JSON = {"Content-Type": "application/json"}


@tagged("post_install", "-at_install")
class TestAuth(common.HttpCase):
    def setUp(self):
        super().setUp()
        self.partenaire = self.env["res.partner"].create({
            "name": "Zunk", "minecraft_uuid": "069a79f444e94726a5befca90e38aaf5"})

    def _defi(self):
        return self.url_open("/mc/v1/defi", data="{}", headers=JSON).json()

    def _session(self, pseudo, server_id):
        return self.url_open("/mc/v1/session", headers=JSON, data=json.dumps(
            {"pseudo": pseudo, "server_id": server_id}))

    def test_le_defi_rend_un_server_id(self):
        reponse = self.url_open("/mc/v1/defi", data="{}", headers=JSON)
        self.assertEqual(reponse.status_code, 200)
        self.assertRegex(reponse.json()["server_id"], r"^[0-9a-f]{32}$")

    @patch(CHEMIN_SESSION)
    def test_session_ouverte_sur_un_uuid_certifie(self, faux_get):
        faux_get.return_value.status_code = 200
        faux_get.return_value.content = b"{}"
        faux_get.return_value.json.return_value = {
            "id": "069a79f444e94726a5befca90e38aaf5", "name": "Zunk"}
        reponse = self._session("Zunk", self._defi()["server_id"])
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.json()["token"])

    @patch(CHEMIN_SESSION)
    def test_uuid_annonce_different_de_celui_certifie(self, faux_get):
        """Mojang has the last word: an UUID we were not given is refused."""
        faux_get.return_value.status_code = 200
        faux_get.return_value.content = b"{}"
        faux_get.return_value.json.return_value = {"id": "f" * 32}
        reponse = self._session("Zunk", self._defi()["server_id"])
        self.assertEqual(reponse.status_code, 404)

    def test_defi_inconnu(self):
        self.assertEqual(self._session("Zunk", "0" * 32).status_code, 403)

    def test_un_defi_ne_sert_qu_une_fois(self):
        """A replayed serverId is as good as an invented one."""
        with patch(CHEMIN_SESSION) as faux_get:
            faux_get.return_value.status_code = 200
            faux_get.return_value.content = b"{}"
            faux_get.return_value.json.return_value = {
                "id": "069a79f444e94726a5befca90e38aaf5"}
            server_id = self._defi()["server_id"]
            self.assertEqual(self._session("Zunk", server_id).status_code, 200)
            self.assertEqual(self._session("Zunk", server_id).status_code, 403)

    @patch(CHEMIN_SESSION)
    def test_mojang_injoignable(self, faux_get):
        """Spec, « Quand ça casse » : refusing is the safe answer, not a 500."""
        faux_get.side_effect = requests.RequestException("timeout")
        self.assertEqual(self._session("Zunk", self._defi()["server_id"]).status_code, 403)

    @patch(CHEMIN_SESSION)
    def test_joueur_certifie_mais_compte_non_lie(self, faux_get):
        """Spec, « Quand ça casse » : the most common first contact says where to go."""
        faux_get.return_value.status_code = 200
        faux_get.return_value.content = b"{}"
        faux_get.return_value.json.return_value = {"id": "a" * 32, "name": "Inconnu"}
        reponse = self._session("Inconnu", self._defi()["server_id"])
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(reponse.json()["erreur"], "compte_non_lie")

    def test_une_requete_sans_pseudo_est_une_mauvaise_requete(self):
        self.assertEqual(self.url_open(
            "/mc/v1/session", headers=JSON,
            data=json.dumps({"server_id": "0" * 32})).status_code, 400)

    def test_le_jeton_ouvre_et_le_jeton_expire_n_ouvre_plus(self):
        """Review Focus #2 côté modèle : la date d'expiration fait foi."""
        Session = self.env["besacraft.mc.session"]
        session = Session._ouvrir(self.partenaire)
        self.assertEqual(Session._partenaire_du_jeton(session.token), self.partenaire)
        session.expire_le = fields.Datetime.now() - timedelta(hours=1)
        self.assertFalse(Session._partenaire_du_jeton(session.token))
        self.assertFalse(Session._partenaire_du_jeton("nimportequoi"))
        self.assertFalse(Session._partenaire_du_jeton(""))

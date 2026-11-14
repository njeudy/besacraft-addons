import json

from odoo.addons.besacraft_minecraft_api.controllers import base
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestApiPoints(common.HttpCase):
    def setUp(self):
        super().setUp()
        base._passages.clear()
        self.addCleanup(base._passages.clear)
        Cosmetique = self.env["besacraft.vestiaire.cosmetique"]
        Cosmetique.search([]).write({"de_base": False})
        self.zoe = self.env["res.partner"].create({
            "name": "Zoé", "minecraft_login": "zoejeudy",
            "minecraft_uuid": "cc67e9f6625340d4813855e5fecc4c10"})
        self.env["res.users"].create({
            "name": "Zoé", "login": "zoe-api-points", "partner_id": self.zoe.id,
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})
        self.jeton = self.env["besacraft.mc.session"]._ouvrir(self.zoe).token
        self.chapeau = Cosmetique.create({"code": "t_chapeau", "name": "Hat",
                                          "emplacement": "chapeau", "prix": 100})
        self.ailes = Cosmetique.create({"code": "t_ailes", "name": "Wings",
                                        "emplacement": "ailes", "de_base": True})
        self.salut = Cosmetique.create({"code": "t_salut", "name": "Wave", "genre": "emote",
                                        "de_base": True})
        Cosmetique.create({"code": "t_cache", "name": "Hidden", "prix": 10, "publie": False})

    def _appel(self, methode, chemin, corps=None, jeton=None):
        return self.opener.request(
            methode, self.base_url() + chemin,
            data=None if corps is None else (corps if isinstance(corps, str) else json.dumps(corps)),
            headers={"Authorization": "Bearer %s" % (jeton or self.jeton),
                     "Content-Type": "application/json"}, timeout=30)

    def test_moi_enrichi(self):
        self.zoe._vestiaire_crediter(70, "cadeau", "Bravo")
        self.zoe._vestiaire_equiper(["t_ailes"], ["t_salut"])
        corps = self._appel("GET", "/mc/v1/vestiaire/moi").json()
        self.assertEqual(corps["points"], 70)
        self.assertEqual(sorted(corps["possede"]), ["t_ailes", "t_salut"])
        self.assertEqual(corps["tenue"], ["t_ailes"])
        self.assertEqual(corps["roue"], ["t_salut"] + [None] * 7)
        self.assertEqual(corps["nouvelles"], [{"points": 70, "libelle": "Bravo"}])
        self.assertEqual(self._appel("GET", "/mc/v1/vestiaire/moi").json()["nouvelles"], [])

    def test_catalogue(self):
        corps = self._appel("GET", "/mc/v1/vestiaire/catalogue").json()
        par_code = {c["code"]: c for c in corps["cosmetiques"]}
        self.assertEqual(set(par_code), {"t_chapeau", "t_ailes", "t_salut"})
        self.assertEqual(par_code["t_chapeau"], {
            "code": "t_chapeau", "genre": "cosmetique", "nom": "Hat", "emplacement": "chapeau",
            "prix": 100, "de_base": False, "possede": False})
        self.assertTrue(par_code["t_ailes"]["possede"])

    def test_equipement(self):
        r = self._appel("PUT", "/mc/v1/vestiaire/equipement",
                        {"tenue": ["t_ailes", "t_chapeau"], "roue": ["t_salut"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"tenue": ["t_ailes"], "roue": ["t_salut"] + [None] * 7})
        self.assertEqual(self._appel("PUT", "/mc/v1/vestiaire/equipement", "pas du json")
                         .status_code, 400)
        self.assertEqual(self._appel("PUT", "/mc/v1/vestiaire/equipement", {"tenue": "x"})
                         .status_code, 400)

    def test_achat(self):
        self.zoe._vestiaire_crediter(130, "cadeau", "Bravo")
        r = self._appel("POST", "/mc/v1/vestiaire/achat", {"code": "t_chapeau", "prix": 100})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["points"], 30)
        self.assertIn("t_chapeau", r.json()["possede"])
        r = self._appel("POST", "/mc/v1/vestiaire/achat", {"code": "t_chapeau", "prix": 100})
        self.assertEqual((r.status_code, r.json()["erreur"]), (409, "deja_possede"))

    def test_achat_refuse(self):
        self.zoe._vestiaire_crediter(30, "cadeau", "Bravo")
        r = self._appel("POST", "/mc/v1/vestiaire/achat", {"code": "t_chapeau", "prix": 100})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json(), {"erreur": "solde_insuffisant", "points": 30, "prix": 100})
        r = self._appel("POST", "/mc/v1/vestiaire/achat", {"code": "t_chapeau", "prix": 90})
        self.assertEqual(r.json()["erreur"], "prix_change")
        self.assertEqual(self._appel("POST", "/mc/v1/vestiaire/achat",
                                     {"code": "t_cache", "prix": 10}).status_code, 404)
        self.assertEqual(self._appel("POST", "/mc/v1/vestiaire/achat",
                                     {"code": "t_chapeau", "prix": "100"}).status_code, 400)

    def test_compte_non_valide_et_sans_jeton(self):
        self.zoe.user_ids.active = False
        for methode, chemin in [("GET", "/mc/v1/vestiaire/catalogue"),
                                ("PUT", "/mc/v1/vestiaire/equipement"),
                                ("POST", "/mc/v1/vestiaire/achat")]:
            r = self._appel(methode, chemin, {})
            self.assertEqual(r.status_code, 403, chemin)
            self.assertEqual(r.json()["erreur"], "compte_non_valide")
            self.assertEqual(self._appel(methode, chemin, {}, jeton="faux").status_code, 401)


@tagged("post_install", "-at_install")
class TestApiServeur(common.HttpCase):
    def setUp(self):
        super().setUp()
        base._passages.clear()
        self.addCleanup(base._passages.clear)
        self.zoe = self.env["res.partner"].create({
            "name": "Zoé", "minecraft_login": "zoejeudy",
            "minecraft_uuid": "cc67e9f6625340d4813855e5fecc4c10"})
        self.cle = self.env["besacraft.vestiaire.cle.serveur"].create({"name": "zunk"})
        self.secret = self.cle._generer()
        self.env["besacraft.vestiaire.bareme"].create({"motif": "mission", "points": 15,
                                                       "name": "Mission du carnet"})

    def _gain(self, corps, secret=None):
        return self.opener.post(self.base_url() + "/mc/v1/serveur/gain", data=json.dumps(corps),
                                headers={"Authorization": "Bearer %s" % (secret or self.secret)},
                                timeout=30)

    def test_gain_rejouable(self):
        corps = {"uuid": "cc67e9f6-6253-40d4-8138-55e5fecc4c10", "motif": "mission",
                 "reference": "zunk:ep3:pont"}
        self.assertEqual(self._gain(corps).json(), {"points": 15, "deja_credite": False})
        self.assertEqual(self._gain(corps).json(), {"points": 15, "deja_credite": True})
        self.assertEqual(self.zoe.vestiaire_points, 15)
        self.assertTrue(self.cle.derniere_utilisation)

    def test_gain_refuse(self):
        self.assertEqual(self._gain({"uuid": "x"}, secret="faux").status_code, 401)
        self.assertEqual(self._gain({"uuid": "x", "motif": "mission"}).status_code, 400)
        self.assertEqual(self._gain({"uuid": "00000000000000000000000000000000",
                                     "motif": "mission", "reference": "r"}).status_code, 404)
        r = self._gain({"uuid": self.zoe.minecraft_uuid, "motif": "cadeau", "reference": "r"})
        self.assertEqual((r.status_code, r.json()["erreur"]), (400, "motif_refuse"))
        r = self._gain({"uuid": self.zoe.minecraft_uuid, "motif": "defi", "reference": "r"})
        self.assertEqual((r.status_code, r.json()["erreur"]), (422, "bareme_absent"))
        self.cle.active = False
        self.assertEqual(self._gain({"uuid": self.zoe.minecraft_uuid, "motif": "mission",
                                     "reference": "r"}).status_code, 401)

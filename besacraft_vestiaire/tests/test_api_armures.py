import json

from odoo.addons.besacraft_minecraft_api.controllers import base
from odoo.tests import common, tagged

from ..tools import armures as outils


def armure(plastron, casque=None, style="pieces", **autres):
    return dict({"nom": None, "plastron": plastron, "teinte_plastron": None, "casque": casque,
                 "teinte_casque": None, "style": style}, **autres)


@tagged("post_install", "-at_install")
class TestApiArmures(common.HttpCase):
    def setUp(self):
        super().setUp()
        base._passages.clear()
        self.addCleanup(base._passages.clear)
        Cosmetique = self.env["besacraft.vestiaire.cosmetique"]
        Cosmetique.search([]).write({"de_base": False})
        self.zoe = self.env["res.partner"].create({
            "name": "Zoé", "minecraft_login": "joueuressai",
            "minecraft_uuid": "5e1f0a2b7c3d4e8f9a6b1c2d3e4f5a6b"})
        self.env["res.users"].create({
            "name": "Zoé", "login": "zoe-api-armures", "partner_id": self.zoe.id,
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})
        self.jeton = self.env["besacraft.mc.session"]._ouvrir(self.zoe).token
        self.plastron = Cosmetique.create({"code": "t_plastron", "name": "Breastplate", "emplacement": "torse",
                                           "piece_armure": "plastron", "de_base": True})
        self.casque = Cosmetique.create({"code": "t_casque", "name": "Helmet", "emplacement": "tete",
                                         "piece_armure": "casque", "de_base": True})
        self.cher = Cosmetique.create({"code": "t_cher", "name": "Gold", "emplacement": "torse",
                                       "piece_armure": "plastron", "prix": 500})
        self.ailes = Cosmetique.create({"code": "t_ailes", "name": "Wings", "emplacement": "ailes",
                                        "de_base": True})

    def _appel(self, methode, chemin, corps=None):
        return self.opener.request(
            methode, self.base_url() + chemin,
            data=None if corps is None else (corps if isinstance(corps, str) else json.dumps(corps)),
            headers={"Authorization": "Bearer %s" % self.jeton, "Content-Type": "application/json"},
            timeout=30)

    def _equiper(self, **corps):
        return self._appel("PUT", "/mc/v1/vestiaire/equipement", dict({"tenue": [], "roue": []}, **corps))

    def test_stand_vide_au_depart(self):
        corps = self._appel("GET", "/mc/v1/vestiaire/moi").json()
        self.assertEqual(corps["armures"], [])
        self.assertEqual(corps["armure_derniere"], -1)

    def test_stand_garde_et_relu(self):
        r = self._equiper(armures=[armure("t_plastron", "t_casque", "nano", teinte_plastron="laiton",
                                          nom="Iron Man")], armure_derniere=0)
        self.assertEqual(r.status_code, 200)
        attendu = [armure("t_plastron", "t_casque", "nano", teinte_plastron="laiton", nom="Iron Man")]
        self.assertEqual(r.json()["armures"], attendu)
        corps = self._appel("GET", "/mc/v1/vestiaire/moi").json()
        self.assertEqual(corps["armures"], attendu)
        self.assertEqual(corps["armure_derniere"], 0)

    def test_couleur_du_gyrophare_gardee(self):
        r = self._equiper(armures=[armure("t_plastron", "t_casque", gyrophare="rouge")], armure_derniere=0)
        attendu = [armure("t_plastron", "t_casque", gyrophare="rouge")]
        self.assertEqual(r.json()["armures"], attendu)
        self.assertEqual(self._appel("GET", "/mc/v1/vestiaire/moi").json()["armures"], attendu)
        self.assertEqual(self.zoe._vestiaire_armures(), (attendu, 0))

    def test_client_sans_armures_ne_les_efface_pas(self):
        self._equiper(armures=[armure("t_plastron")], armure_derniere=0)
        r = self._equiper(tenue=["t_ailes"])  # a 2.5.0 game: no "armures" key
        self.assertEqual(r.json()["tenue"], ["t_ailes"])
        self.assertEqual(r.json()["armures"], [armure("t_plastron")])
        self.assertEqual(self._appel("GET", "/mc/v1/vestiaire/moi").json()["armure_derniere"], 0)

    def test_pieces_non_possedees_ecartees(self):
        r = self._equiper(armures=[armure("t_cher"), armure("t_ailes"), armure("t_casque"),
                                   armure("t_plastron", "t_cher"), "bruit"], armure_derniere=3)
        self.assertEqual(r.json()["armures"], [armure("t_plastron")])
        self.assertEqual(r.json()["armure_derniere"], -1)

    def test_stand_plafonne_et_sans_doublon(self):
        styles = ["pieces", "nano", "forge", "engrenages", "portail", "vapeur", "eclair", "x", "y", "z"]
        r = self._equiper(armures=[armure("t_plastron", style=s) for s in styles] + [armure("t_plastron")])
        self.assertEqual(len(r.json()["armures"]), outils.STAND_MAX)

    def test_armures_pas_une_liste(self):
        self.assertEqual(self._equiper(armures="t_plastron").status_code, 400)

    def test_armure_perdue_disparait_et_la_derniere_suit(self):
        self.zoe._vestiaire_equiper_armures([armure("t_plastron", style="nano"), armure("t_plastron", "t_casque")],
                                            1)
        self.casque.publie = False  # the helmet is no longer owned: it falls, alone
        self.plastron.publie = True
        armures, derniere = self.zoe._vestiaire_armures()
        self.assertEqual(armures, [armure("t_plastron", style="nano"), armure("t_plastron")])
        self.assertEqual(derniere, 1)
        self.plastron.publie = False
        self.assertEqual(self.zoe._vestiaire_armures(), ([], -1))

    def test_pieces_des_armures_livrees(self):
        self.assertEqual(self.env.ref("besacraft_vestiaire.cosmetique_pao_armure").piece_armure, "plastron")
        self.assertEqual(self.env.ref("besacraft_vestiaire.cosmetique_zoe_casque_neon").piece_armure, "casque")
        self.assertEqual(self.env.ref("besacraft_vestiaire.cosmetique_zoe_armure_ironman").piece_armure, "plastron")
        self.assertEqual(self.env.ref("besacraft_vestiaire.cosmetique_zoe_casque_ironman").piece_armure, "casque")


class TestOutilsArmures(common.BaseCase):
    """The normalisation alone, without a database."""

    PIECES = {"p": "plastron", "c": "casque"}

    def test_formes_corrigees(self):
        gardees = outils.normaliser([{"plastron": "p", "casque": "c", "teinte_plastron": "Pas Bon",
                                      "style": "nano", "nom": "n" * 60}], self.PIECES)
        self.assertEqual(gardees, [{"nom": "n" * outils.NOM_MAX, "plastron": "p", "teinte_plastron": None,
                                    "casque": "c", "teinte_casque": None, "style": "nano"}])

    def test_couleur_du_gyrophare(self):
        gardees = outils.normaliser([{"plastron": "p", "gyrophare": "bleu"}, {"plastron": "p", "gyrophare": 3},
                                     {"plastron": "p", "style": "nano", "gyrophare": "Pas Bon"}], self.PIECES)
        self.assertEqual(gardees[0]["gyrophare"], "bleu")
        self.assertEqual(len(gardees), 2, "the beacon colour does not make another armour")
        self.assertNotIn("gyrophare", gardees[1], "no key when no valid colour: older games read the same")

    def test_derniere(self):
        self.assertEqual(outils.derniere(0, [1]), 0)
        self.assertEqual(outils.derniere(1, [1]), -1)
        self.assertEqual(outils.derniere(True, [1]), -1)
        self.assertEqual(outils.derniere("0", [1]), -1)

import json

from odoo.addons.besacraft_minecraft_api.controllers import base
from odoo.tests import common, tagged

from ..tools import fonctions as outils

TOUTES = list(outils.FONCTIONS)


@tagged("post_install", "-at_install")
class TestFonctionsPures(common.BaseCase):
    def test_vide_vaut_tout(self):
        self.assertEqual(outils.effectives([], []), TOUTES)

    def test_intersection(self):
        self.assertEqual(outils.effectives(["hud", "chantier", "vol"], ["chantier", "hud"]),
                         ["hud", "chantier"])

    def test_debloque_seul(self):
        self.assertEqual(outils.effectives([], ["chantier"]), ["chantier"])

    def test_inconnu_ignore(self):
        self.assertEqual(outils.effectives(["hud", "laser"], []), ["hud"])


@tagged("post_install", "-at_install")
class TestApiFonctions(common.HttpCase):
    def setUp(self):
        super().setUp()
        base._passages.clear()
        self.addCleanup(base._passages.clear)
        Cosmetique = self.env["besacraft.vestiaire.cosmetique"]
        Cosmetique.search([]).write({"de_base": False})
        self.joueur = self.env["res.partner"].create({
            "name": "Joueur", "minecraft_login": "joueuressai",
            "minecraft_uuid": "5e1f0a2b7c3d4e8f9a6b1c2d3e4f5a6b"})
        self.env["res.users"].create({
            "name": "Joueur", "login": "joueur-api-fonctions", "partner_id": self.joueur.id,
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})
        self.jeton = self.env["besacraft.mc.session"]._ouvrir(self.joueur).token
        self.cle = self.env["besacraft.vestiaire.cle.serveur"].create({"name": "zunk"})
        self.secret = self.cle._generer()
        f = {code: self.env.ref("besacraft_vestiaire.fonction_%s" % code) for code in TOUTES}
        self.libre = Cosmetique.create({"code": "t_libre", "name": "Free", "emplacement": "torse",
                                        "piece_armure": "plastron"})
        self.chantier = Cosmetique.create({
            "code": "t_chantier", "name": "Site helmet", "emplacement": "tete", "piece_armure": "casque",
            "fonction_ids": [(6, 0, (f["hud"] | f["chantier"] | f["scanner"]).ids)]})
        self.base = Cosmetique.create({"code": "t_base", "name": "For all", "emplacement": "tete",
                                       "piece_armure": "casque", "de_base": True})
        self.ailes = Cosmetique.create({"code": "t_ailes", "name": "Wings", "emplacement": "ailes",
                                        "de_base": True})
        Possession = self.env["besacraft.vestiaire.possession"]
        Possession.create({"partner_id": self.joueur.id, "cosmetique_id": self.libre.id})
        Possession.create({"partner_id": self.joueur.id, "cosmetique_id": self.chantier.id,
                           "fonction_ids": [(6, 0, (f["hud"] | f["chantier"]).ids)]})

    def _get(self, chemin, bearer):
        return self.opener.request("GET", self.base_url() + chemin,
                                   headers={"Authorization": "Bearer %s" % bearer}, timeout=30)

    def test_moi_donne_les_fonctions(self):
        corps = self._get("/mc/v1/vestiaire/moi", self.jeton).json()
        self.assertEqual(corps["fonctions"], {
            "t_libre": TOUTES,
            "t_chantier": ["hud", "chantier"],
            "t_base": TOUTES,
        })

    def test_serveur_lit_les_fonctions(self):
        r = self._get("/mc/v1/serveur/fonctions/%s" % self.joueur.minecraft_uuid, self.secret)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["fonctions"]["t_chantier"], ["hud", "chantier"])

    def test_serveur_joueur_inconnu_n_a_que_le_commun(self):
        r = self._get("/mc/v1/serveur/fonctions/00000000000000000000000000000001", self.secret)
        self.assertEqual(r.json()["fonctions"], {"t_base": TOUTES})

    def test_serveur_sans_cle_refuse(self):
        r = self._get("/mc/v1/serveur/fonctions/%s" % self.joueur.minecraft_uuid, self.jeton)
        self.assertEqual(r.status_code, 401)

    def test_piece_non_publiee_absente(self):
        self.chantier.publie = False
        corps = self._get("/mc/v1/vestiaire/moi", self.jeton).json()
        self.assertNotIn("t_chantier", corps["fonctions"])

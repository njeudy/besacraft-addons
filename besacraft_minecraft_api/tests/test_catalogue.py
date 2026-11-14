from datetime import timedelta

from odoo import fields
from odoo.tests import common, tagged

BUILD_JSON = {
    "name": "Taverne",
    "size": [3, 2, 3],
    "palette": [{"id": "minecraft:air"}, {"id": "minecraft:dirt"},
                {"id": "minecraft:oak_log"}],
    "layers": [
        {"y": 0, "counts": {"minecraft:dirt": 3},
         "blocks": [[0, 0, 1], [1, 0, 1], [2, 0, 1], [1, 1, 0]]},
        {"y": 1, "counts": {"minecraft:oak_log": 2},
         "blocks": [[0, 0, 2], [2, 2, 2]]},
    ],
    "items": {"minecraft:dirt": {"name": "Terre", "mod": "Minecraft"}},
}


@tagged("post_install", "-at_install")
class TestCatalogue(common.HttpCase):
    def setUp(self):
        super().setUp()
        self.partenaire = self.env["res.partner"].create({
            "name": "Zunk", "minecraft_uuid": "069a79f444e94726a5befca90e38aaf5"})
        self.session = self.env["besacraft.mc.session"]._ouvrir(self.partenaire)
        self.entete = {"Authorization": "Bearer %s" % self.session.token}
        serie = self.env.ref("besacraft_builds.serie_survie")
        self.build_a = self.env["besacraft.build"].import_build_json(
            BUILD_JSON, None, "9701", serie)
        self.build_b = self.env["besacraft.build"].import_build_json(
            dict(BUILD_JSON, name="Moulin"), None, "9702", serie)

    def test_builds_ne_rend_que_les_siens(self):
        """A member sees their builds and no one else's."""
        self.build_a._action_add_members(self.partenaire)
        reponse = self.url_open("/mc/v1/builds", headers=self.entete)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual([b["code"] for b in reponse.json()["builds"]], [self.build_a.code])

    def test_fiche_porte_la_liste_a_farmer(self):
        self.build_a._action_add_members(self.partenaire)
        fiche = self.url_open(
            "/mc/v1/build/%s" % self.build_a.code, headers=self.entete).json()
        self.assertEqual(fiche["blocs"], self.build_a.block_count)
        self.assertIn("minecraft:dirt", fiche["a_farmer"])
        self.assertEqual(len(fiche["couches"]), self.build_a.layer_count)

    def test_fiche_dun_build_dont_on_nest_pas_membre(self):
        reponse = self.url_open("/mc/v1/build/%s" % self.build_a.code, headers=self.entete)
        self.assertEqual(reponse.status_code, 403)

    def test_code_inexistant(self):
        """Review Focus #1."""
        self.assertEqual(
            self.url_open("/mc/v1/build/999999", headers=self.entete).status_code, 404)

    def test_code_non_numerique(self):
        """Review Focus #1: no Python traceback on a junk code."""
        self.assertEqual(
            self.url_open("/mc/v1/build/abc", headers=self.entete).status_code, 404)

    def test_jeton_inconnu_sur_une_route_protegee(self):
        """Review Focus #2: a made-up token leaks nothing."""
        reponse = self.url_open(
            "/mc/v1/builds", headers={"Authorization": "Bearer nimportequoi"})
        self.assertEqual(reponse.status_code, 401)

    def test_jeton_absent_sur_une_route_protegee(self):
        """Review Focus #2: no header at all is not an anonymous read."""
        self.assertEqual(self.url_open("/mc/v1/builds").status_code, 401)

    def test_jeton_expire(self):
        """Review Focus #2: an expired session is as good as none."""
        self.session.expire_le = fields.Datetime.now() - timedelta(hours=1)
        self.assertEqual(self.url_open("/mc/v1/builds", headers=self.entete).status_code, 401)

    def test_un_jeton_ne_voit_pas_les_builds_dun_autre(self):
        """Review Focus #2: the token decides whose list comes back, nothing else."""
        self.build_a._action_add_members(self.partenaire)
        autre = self.env["res.partner"].create({"name": "Autre"})
        self.build_b._action_add_members(autre)
        codes = [b["code"] for b in
                 self.url_open("/mc/v1/builds", headers=self.entete).json()["builds"]]
        self.assertEqual(codes, [self.build_a.code])

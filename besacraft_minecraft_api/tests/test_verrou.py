from odoo.tests import common, tagged

# Six couches, pour que « deux couches plus loin » ait un sens. L'index 0 est de l'air :
# la route doit le retirer, comme l'hologramme public le fait déjà.
PALETTE = [{"id": "minecraft:air", "key": "minecraft:air"},
           {"id": "minecraft:dirt", "key": "minecraft:dirt"},
           {"id": "minecraft:oak_log", "key": "minecraft:oak_log"}]
BUILD_JSON = {
    "name": "Tour",
    "size": [3, 6, 3],
    "palette": PALETTE,
    "layers": [{"y": y, "counts": {"minecraft:dirt": 2},
                "blocks": [[0, 0, 1], [1, 1, 1], [2, 2, 0]]} for y in range(6)],
    "items": {"minecraft:dirt": {"name": "Terre", "mod": "Minecraft"}},
}


@tagged("post_install", "-at_install")
class TestVerrou(common.HttpCase):
    def setUp(self):
        super().setUp()
        self.partenaire = self.env["res.partner"].create({
            "name": "Zunk", "minecraft_uuid": "069a79f444e94726a5befca90e38aaf5"})
        self.entete = {"Authorization": "Bearer %s" % self.env[
            "besacraft.mc.session"]._ouvrir(self.partenaire).token}
        self.build_a = self.env["besacraft.build"].import_build_json(
            BUILD_JSON, None, "9711", self.env.ref("besacraft_builds.serie_survie"))

    def _couche(self, n, code=None):
        return self.url_open("/mc/v1/build/%s/couche/%s" % (code or self.build_a.code, n),
                             headers=self.entete)

    def test_la_couche_suivante_passe(self):
        """n = layer_reached + 1 is the one the player is allowed to lay."""
        membre = self.build_a._action_add_members(self.partenaire)
        membre.layer_reached = 3
        reponse = self._couche(4)
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.json()["blocs"])

    def test_la_couche_porte_les_types_de_blocs(self):
        """What separates this route from the public hologram: the palette comes out."""
        self.build_a._action_add_members(self.partenaire)
        blocs = self._couche(1).json()["blocs"]
        # L'air est retiré : trois positions dans le fichier, deux posées.
        self.assertEqual(blocs, [[0, 0, "minecraft:dirt"], [1, 1, "minecraft:dirt"]])

    def test_une_couche_deja_faite_passe(self):
        """Going back to re-read a finished layer must stay possible."""
        membre = self.build_a._action_add_members(self.partenaire)
        membre.layer_reached = 3
        self.assertEqual(self._couche(2).status_code, 200)

    def test_deux_couches_plus_loin_est_refuse(self):
        """The lock, in the only route that lets geometry out."""
        membre = self.build_a._action_add_members(self.partenaire)
        membre.layer_reached = 3
        self.assertEqual(self._couche(5).status_code, 403)

    def test_la_premiere_couche_passe_des_le_depart(self):
        """layer_reached = 0 must still allow layer 1: the footprint of the preview."""
        self.build_a._action_add_members(self.partenaire)
        self.assertEqual(self._couche(1).status_code, 200)

    def test_sans_etre_membre_aucune_geometrie(self):
        """The lock is not the only gate: membership comes first."""
        self.assertEqual(self._couche(1).status_code, 403)

    def test_sans_jeton_aucune_geometrie(self):
        self.assertEqual(self.url_open(
            "/mc/v1/build/%s/couche/1" % self.build_a.code).status_code, 401)

    def test_couche_zero_ou_negative(self):
        """Review Focus #3."""
        self.build_a._action_add_members(self.partenaire)
        for n in (0, -1):
            self.assertEqual(self._couche(n).status_code, 404, n)

    def test_couche_au_dela_du_batiment(self):
        """Review Focus #3: no IndexError past the last layer."""
        membre = self.build_a._action_add_members(self.partenaire)
        membre.layer_reached = 99
        self.assertEqual(self._couche(99).status_code, 404)

    def test_build_sans_plan_stocke(self):
        """Review Focus #4: the builds imported before the plan was kept."""
        self.build_a._action_add_members(self.partenaire)
        self.build_a.build_json_attachment_id.unlink()
        reponse = self._couche(1)
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(reponse.json()["erreur"], "plan_absent")

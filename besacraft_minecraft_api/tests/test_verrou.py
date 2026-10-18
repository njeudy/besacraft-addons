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


@tagged("post_install", "-at_install")
class TestProgression(common.HttpCase):
    """`/faite` : ce que le joueur a posé, et ce que le verrou lui ouvre ensuite."""

    def setUp(self):
        super().setUp()
        self.partenaire = self.env["res.partner"].create({
            "name": "Zunk", "minecraft_uuid": "069a79f444e94726a5befca90e38aaf5"})
        self.entete_json = {
            "Authorization": "Bearer %s" % self.env[
                "besacraft.mc.session"]._ouvrir(self.partenaire).token,
            "Content-Type": "application/json"}
        self.build_a = self.env["besacraft.build"].import_build_json(
            BUILD_JSON, None, "9721", self.env.ref("besacraft_builds.serie_survie"))

    def _faite(self, n):
        reponse = self.url_open("/mc/v1/build/%s/couche/%s/faite" % (self.build_a.code, n),
                                data="{}", headers=self.entete_json)
        self.env["besacraft.build.member"].invalidate_model()
        return reponse

    def test_faite_avance_la_progression(self):
        membre = self.build_a._action_add_members(self.partenaire)
        self.assertEqual(self._faite(1).status_code, 200)
        self.assertEqual(membre.layer_reached, 1)
        self.assertEqual(membre.member_status, "ongoing")

    def test_faite_ne_fait_jamais_redescendre(self):
        """Review Focus #5: two calls out of order must not lose progress."""
        membre = self.build_a._action_add_members(self.partenaire)
        membre.layer_reached = 5
        self._faite(2)
        self.assertEqual(membre.layer_reached, 5)

    def test_faite_met_a_jour_le_pourcentage(self):
        membre = self.build_a._action_add_members(self.partenaire)
        self._faite(self.build_a.layer_count)
        self.assertEqual(membre.completion, 100)
        self.assertEqual(membre.member_status, "completed")

    def test_faite_ouvre_la_couche_suivante(self):
        """The lock and the progress are two sides of one state: prove they agree."""
        self.build_a._action_add_members(self.partenaire)
        self.assertEqual(self.url_open(
            "/mc/v1/build/%s/couche/2" % self.build_a.code,
            headers=self.entete_json).status_code, 403)
        self._faite(1)
        self.assertEqual(self.url_open(
            "/mc/v1/build/%s/couche/2" % self.build_a.code,
            headers=self.entete_json).status_code, 200)

    def test_faite_hors_du_batiment(self):
        """Review Focus #3 côté écriture : un n absurde ne crée pas une progression absurde."""
        membre = self.build_a._action_add_members(self.partenaire)
        for n in (0, 99):
            self.assertEqual(self._faite(n).status_code, 404, n)
        self.assertEqual(membre.layer_reached, 0)

    def test_faite_sans_etre_membre(self):
        autre = self.env["res.partner"].create({
            "name": "Autre", "minecraft_uuid": "b" * 32})
        jeton = self.env["besacraft.mc.session"]._ouvrir(autre).token
        reponse = self.url_open(
            "/mc/v1/build/%s/couche/1/faite" % self.build_a.code, data="{}",
            headers={"Authorization": "Bearer %s" % jeton,
                     "Content-Type": "application/json"})
        self.assertEqual(reponse.status_code, 403)

    def test_une_lecture_perimee_ne_fait_pas_redescendre(self):
        """Review Focus #5, la vraie course : deux requêtes qui écrivent en même temps.

        The direct UPDATE stands for the neighbouring transaction that committed a
        higher layer while this one still held the old value. The decision has to be
        taken on the locked row, not on what the request read on the way in -- in
        READ COMMITTED nothing else stops the slower writer from winning.
        """
        membre = self.build_a._action_add_members(self.partenaire)
        self.assertEqual(membre.layer_reached, 0)
        self.env.cr.execute(
            "UPDATE besacraft_build_member SET layer_reached = 5 WHERE id = %s",
            (membre.id,))
        membre.marquer_couche_faite(4)
        membre.invalidate_recordset()
        self.assertEqual(membre.layer_reached, 5)

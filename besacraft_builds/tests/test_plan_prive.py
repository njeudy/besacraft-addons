from odoo.tests import HttpCase, tagged

PALETTE = [{"id": "minecraft:air", "key": "minecraft:air"},
           {"id": "minecraft:dirt", "key": "minecraft:dirt"}]
BUILD_JSON = {
    "name": "Cabane", "size": [2, 2, 2], "palette": PALETTE,
    "layers": [{"y": y, "counts": {"minecraft:dirt": 1},
                "blocks": [[0, 0, 1], [1, 1, 0]]} for y in range(2)],
    "items": {"minecraft:dirt": {"name": "Terre", "mod": "Minecraft"}},
}


@tagged("post_install", "-at_install")
class TestPlanPrive(HttpCase):
    """The full plan carries block types: it must not leave by the web.

    The hologram served publicly only has positions, and that is what makes it
    harmless. The attachment is the other half, and today nothing but a line of the
    Odoo core keeps it in -- this test is what turns red the day that line moves.
    """

    def setUp(self):
        super().setUp()
        self.build = self.env["besacraft.build"].import_build_json(
            BUILD_JSON, None, "9731", self.env.ref("besacraft_builds.serie_survie"))
        self.piece = self.build.build_json_attachment_id
        self.assertTrue(self.piece, "le plan doit être attaché pour que le test ait un sens")

    def _telecharger(self):
        return self.url_open("/web/content/%d" % self.piece.id, allow_redirects=False)

    def test_un_visiteur_ne_telecharge_pas_le_plan(self):
        reponse = self._telecharger()
        self.assertNotEqual(reponse.status_code, 200)
        self.assertNotIn("minecraft:dirt", reponse.text)

    def test_un_client_portail_ne_telecharge_pas_le_plan(self):
        societe = (self.env.ref("website.default_website").company_id
                   or self.env["res.company"].search([], limit=1))
        self.env["res.users"].create({
            "name": "Zoé", "login": "zoe-plan", "password": "zoe-plan",
            "company_id": societe.id, "company_ids": [(6, 0, societe.ids)],
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})
        self.authenticate("zoe-plan", "zoe-plan")
        reponse = self._telecharger()
        self.assertNotEqual(reponse.status_code, 200)
        self.assertNotIn("minecraft:dirt", reponse.text)

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

BUILD_JSON = {
    "name": "Taverne",
    "size": [17, 14, 19],
    "block_count": 834,
    "layers": [
        {"y": 0, "counts": {"minecraft:dirt": 163, "minecraft:oak_log": 12}},
        {"y": 1, "counts": {"minecraft:oak_log": 30}},
    ],
    "items": {
        "minecraft:dirt": {"name": "Terre", "mod": "Minecraft"},
        "minecraft:oak_log": {"name": "Bûche de chêne", "mod": "Minecraft"},
    },
}

# La première couche est enterrée : la vidéo ne compte que la seconde.
PLAN_JSON = {"total": 30, "couches": 1, "depuis": 1}


@tagged("post_install", "-at_install")
class TestImport(TransactionCase):
    def _import(self, donnees=None, plan=PLAN_JSON):
        return self.env["besacraft.build"].import_build_json(
            donnees or BUILD_JSON, plan, code="9342",
            serie=self.env.ref("besacraft_builds.serie_survie"))

    def test_l_import_cree_le_build(self):
        build = self._import()
        self.assertEqual(build.code, "9342")
        self.assertEqual((build.size_x, build.size_y, build.size_z), (17, 14, 19))

    def test_le_total_est_celui_de_la_video_pas_celui_du_fichier(self):
        """build.json compte le décor et les fondations enterrées ; la vidéo non.
        Sur la taverne réelle : 1691 blocs / 14 couches contre 708 / 9 annoncés."""
        build = self._import()
        self.assertEqual(build.block_count, 30)
        self.assertEqual(build.layer_count, 1)
        self.assertEqual(len(build.layer_ids), 1)

    def test_sans_plan_on_importe_tout(self):
        build = self._import(plan=None)
        self.assertEqual(build.block_count, 205)
        self.assertEqual(build.layer_count, 2)

    def test_les_quantites_sont_celles_du_fichier(self):
        """Regle de la marque : jamais recalculees."""
        build = self._import(plan=None)
        premiere = build.layer_ids[0]
        self.assertEqual(premiere.block_count, 175)
        self.assertEqual(
            {l.item_key: l.qty for l in premiere.line_ids},
            {"minecraft:dirt": 163, "minecraft:oak_log": 12})

    def test_les_noms_viennent_de_items(self):
        build = self._import(plan=None)
        ligne = build.layer_ids[0].line_ids.filtered(lambda l: l.item_key == "minecraft:dirt")
        self.assertEqual(ligne.name_fr, "Terre")
        self.assertEqual(ligne.mod, "Minecraft")

    def test_reimporter_ne_duplique_pas_le_build(self):
        build = self._import()
        again = self._import()
        self.assertEqual(build, again)
        self.assertEqual(len(again.layer_ids), 1)

    def test_les_titres_saisis_a_la_main_survivent_a_un_reimport(self):
        """Un réimport rafraîchit les quantités, il ne doit pas effacer l'éditorial."""
        build = self._import()
        build.layer_ids[0].title = "Les murs"
        self._import()
        self.assertEqual(build.layer_ids[0].title, "Les murs")


@tagged("post_install", "-at_install")
class TestImportDepuisBuildplan(TransactionCase):
    """Le point d'entrée JSON-RPC : mêmes données, adressées par codes."""

    def _import(self, serie_code="survie"):
        return self.env["besacraft.build"].import_depuis_buildplan(
            BUILD_JSON, PLAN_JSON, code="9343", serie_code=serie_code)

    def test_il_resout_la_serie_par_son_code(self):
        resultat = self._import()
        self.assertEqual(resultat["code"], "9343")
        self.assertEqual(resultat["serie"], "Survie & Schematics")
        self.assertEqual(resultat["block_count"], 30)

    def test_une_serie_inconnue_est_refusee(self):
        """Plutôt que de classer le tuto au hasard : le message liste les codes connus."""
        with self.assertRaises(ValidationError) as leve:
            self._import(serie_code="mediévale")
        self.assertIn("hardcore", str(leve.exception))

    def test_le_build_atterrit_sur_le_site_besacraft(self):
        """Sans défaut, website_id vide veut dire « les six sites de la base »."""
        site = self.env["website"].search([], limit=1)
        site.besacraft_enabled = True
        autre = self.env["besacraft.build"].create({
            "name": "Test", "code": "9344",
            "serie_id": self.env.ref("besacraft_builds.serie_survie").id,
        })
        self.assertEqual(autre.website_id, site)

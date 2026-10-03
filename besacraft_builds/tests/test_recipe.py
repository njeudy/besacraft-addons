from odoo.tests import HttpCase, TransactionCase, tagged

ICONE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg=="

# A trimmed recipes.json: one shaped recipe, one recipe by inputs, a raw block with a
# hint, and an item whose icon is only a relative path.
RECETTES = {
    "trees": {
        "minecraft:oak_stairs": {
            "id": "minecraft:oak_stairs", "name": "Escalier en chêne", "needed": 37,
            "raw": False,
            "recipe": {
                "id": "minecraft:oak_stairs", "type": "minecraft:crafting_shaped",
                "station": "Table de craft", "station_item": "minecraft:crafting_table",
                "yield": 4, "crafts": 10,
                "grid": [["minecraft:oak_planks", None, None],
                         ["minecraft:oak_planks", "minecraft:oak_planks", None],
                         ["minecraft:oak_planks", "minecraft:oak_planks", "minecraft:oak_planks"]],
            },
            "children": [],
            "alternatives": ["Scierie"],
        },
        "domum_ornamentum:framed_planks": {
            "id": "domum_ornamentum:framed_planks", "name": "Planches encadrées",
            "needed": 12, "raw": False,
            "recipe": {
                "id": "domum_ornamentum:framed_planks", "type": "domum_ornamentum:architects_cutter",
                "station": "Architect's Cutter",
                "station_item": "domum_ornamentum:architectscutter",
                "yield": 1, "crafts": 12,
                "inputs": [{"id": "minecraft:oak_planks", "count": 1, "fluid_mb": 0},
                           {"id": "minecraft:spruce_planks", "count": 1, "fluid_mb": 0}],
            },
            "children": [],
        },
        "minecraft:gravel": {
            "id": "minecraft:gravel", "name": "Gravier", "needed": 9, "raw": True,
            "hint": "à obtenir · minage",
        },
        "minecraft:stone": {
            "id": "minecraft:stone", "name": "Roche", "needed": 5, "raw": True,
        },
    },
    "raw_totals": {"minecraft:oak_log": 12, "minecraft:gravel": 9,
                   "minecraft:spruce_log": 3, "minecraft:stone": 5},
    "items": {
        "minecraft:oak_planks": {"name": "Planches de chêne", "icon": "icons/oak_planks.png",
                                 "icon_data": ICONE},
        "minecraft:spruce_planks": {"name": "Planches de sapin", "icon": None,
                                    "icon_data": ICONE},
        "minecraft:crafting_table": {"name": "Table de craft", "icon": None,
                                     "icon_data": ICONE},
        "domum_ornamentum:architectscutter": {"name": "Architect's Cutter", "icon": None,
                                              "icon_data": None},
        "minecraft:oak_log": {"name": "Bûche de chêne", "icon": None, "icon_data": ICONE},
        "minecraft:spruce_log": {"name": "Bûche de sapin", "icon": "icons/spruce_log.png",
                                 "icon_data": None},
        "minecraft:gravel": {"name": "Gravier", "icon": None, "icon_data": ICONE},
        "minecraft:stone": {"name": "Roche", "icon": None, "icon_data": ICONE},
    },
}


@tagged("post_install", "-at_install")
class TestRecettes(TransactionCase):
    def setUp(self):
        super().setUp()
        self.build = self.env["besacraft.build"].create({
            "name": "Moulin", "code": "9944",
            "serie_id": self.env.ref("besacraft_builds.serie_survie").id,
        })

    def test_recipes_json_se_stocke_tel_quel(self):
        """The import script writes the decoded file over JSON-RPC and reads it back."""
        self.build.write({"recipe_data": RECETTES, "has_recipes": True})
        self.build.invalidate_recordset()
        self.assertEqual(self.build.recipe_data, RECETTES)
        self.assertTrue(self.build.has_recipes)

    def test_recette_en_grille(self):
        """A shaped recipe counts its grid: 6 planks per craft, 4 stairs out."""
        self.build.recipe_data = RECETTES
        recette = self.build._tuto_recipe_for("minecraft:oak_stairs")
        self.assertFalse(recette["raw"])
        self.assertEqual(recette["station"], "Table de craft")
        self.assertEqual(recette["station_icon"], ICONE)
        self.assertEqual(recette["yield"], 4)
        self.assertEqual(recette["alternatives"], ["Scierie"])
        self.assertEqual(
            [(i["id"], i["name"], i["count"], i["icon"]) for i in recette["inputs"]],
            [("minecraft:oak_planks", "Planches de chêne", 6, ICONE)])

    def test_recette_par_entrees(self):
        """A recipe without a grid, like the Architect's Cutter, takes its inputs' counts."""
        self.build.recipe_data = RECETTES
        recette = self.build._tuto_recipe_for("domum_ornamentum:framed_planks")
        self.assertEqual(recette["station"], "Architect's Cutter")
        self.assertFalse(recette["station_icon"])
        self.assertEqual(recette["yield"], 1)
        self.assertEqual(
            [(i["name"], i["count"]) for i in recette["inputs"]],
            [("Planches de chêne", 1), ("Planches de sapin", 1)])

    def test_bloc_brut_avec_et_sans_indication(self):
        self.build.recipe_data = RECETTES
        gravier = self.build._tuto_recipe_for("minecraft:gravel")
        self.assertTrue(gravier["raw"])
        self.assertEqual(gravier["hint"], "à obtenir · minage")
        self.assertEqual(gravier["inputs"], [])
        roche = self.build._tuto_recipe_for("minecraft:stone")
        self.assertTrue(roche["raw"])
        self.assertEqual(roche["hint"], "")

    def test_bloc_absent_ou_build_sans_recettes(self):
        self.assertIsNone(self.build._tuto_recipe_for("minecraft:oak_stairs"))
        self.assertEqual(self.build._tuto_raw_materials(), [])
        self.build.recipe_data = RECETTES
        self.assertIsNone(self.build._tuto_recipe_for("minecraft:dirt"))

    def test_matieres_premieres_triees_par_quantite(self):
        """Largest first; a relative icon path is dropped, it would 404 on the site."""
        self.build.recipe_data = RECETTES
        matieres = self.build._tuto_raw_materials()
        self.assertEqual(
            [(m["name"], m["count"]) for m in matieres],
            [("Bûche de chêne", 12), ("Gravier", 9), ("Roche", 5), ("Bûche de sapin", 3)])
        self.assertEqual(matieres[0]["icon"], ICONE)
        self.assertFalse(matieres[-1]["icon"])

    def test_recettes_d_une_couche_suivent_ses_lignes(self):
        self.build.recipe_data = RECETTES
        couche = self.env["besacraft.build.layer"].create({
            "build_id": self.build.id, "sequence": 1,
            "line_ids": [
                (0, 0, {"item_key": "minecraft:oak_stairs", "name_fr": "Escalier", "qty": 8}),
                (0, 0, {"item_key": "minecraft:dirt", "name_fr": "Terre", "qty": 2}),
            ]})
        recettes = self.build._tuto_layer_recipes(couche)
        self.assertEqual([r["line"].item_key for r in recettes], ["minecraft:oak_stairs"])


@tagged("post_install", "-at_install")
class TestRecettesPage(HttpCase):
    def setUp(self):
        super().setUp()
        self.site = self.env.ref("website.default_website")
        self.site.besacraft_enabled = True
        self.build = self.env["besacraft.build"].create({
            "name": "Moulin", "code": "9912", "enroll": "public", "is_published": True,
            "serie_id": self.env.ref("besacraft_builds.serie_survie").id,
            "website_id": self.site.id,
            "recipe_data": RECETTES,
        })
        self.env["besacraft.build.layer"].create({
            "build_id": self.build.id, "sequence": 1, "title": "Fondations",
            "line_ids": [
                (0, 0, {"item_key": "minecraft:oak_stairs", "name_fr": "Escalier en chêne",
                        "qty": 8}),
                (0, 0, {"item_key": "minecraft:gravel", "name_fr": "Gravier", "qty": 3}),
            ]})

    def test_la_page_montre_les_recettes(self):
        self.build.has_recipes = True
        page = self.url_open("/t/9912").text
        self.assertIn("Recettes de la couche", page)
        self.assertIn("Table de craft", page)
        self.assertIn("donne 4", page)
        self.assertIn("à obtenir · minage", page)
        self.assertIn("Matières premières pour tout le build", page)
        self.assertIn("Bûche de chêne", page)
        self.assertIn(ICONE, page)

    def test_sans_drapeau_la_page_ne_montre_pas_de_recettes(self):
        """has_recipes is what the import sets once recipes.json exists: it decides."""
        page = self.url_open("/t/9912").text
        self.assertNotIn("Recettes de la couche", page)
        self.assertNotIn("Matières premières pour tout le build", page)

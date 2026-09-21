from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLayer(TransactionCase):
    def setUp(self):
        super().setUp()
        self.build = self.env["besacraft.build"].create({
            "name": "Taverne", "code": "9042",
            "serie_id": self.env.ref("besacraft_builds.serie_survie").id,
        })

    def test_une_couche_porte_ses_lignes(self):
        couche = self.env["besacraft.build.layer"].create({
            "build_id": self.build.id, "sequence": 1, "block_count": 163,
            "line_ids": [(0, 0, {"item_key": "minecraft:dirt", "name_fr": "Terre", "qty": 163})],
        })
        self.assertEqual(len(couche.line_ids), 1)
        self.assertEqual(couche.line_ids.qty, 163)

    def test_les_couches_sont_triees_par_sequence(self):
        for seq in (3, 1, 2):
            self.env["besacraft.build.layer"].create({"build_id": self.build.id, "sequence": seq})
        self.assertEqual(self.build.layer_ids.mapped("sequence"), [1, 2, 3])

    def test_supprimer_un_build_supprime_ses_couches(self):
        couche = self.env["besacraft.build.layer"].create({"build_id": self.build.id, "sequence": 1})
        self.build.unlink()
        self.assertFalse(couche.exists())

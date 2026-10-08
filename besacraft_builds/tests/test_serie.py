from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSerie(TransactionCase):
    def test_les_series_sont_livrees(self):
        """The series ship with the module: the build form is useless without them."""
        series = self.env["besacraft.serie"].search([])
        self.assertEqual(set(series.mapped("code")),
                         {"1722", "hardcore", "schematics", "steampunk"})
        self.assertEqual(set(series.mapped("visual_mode")), {"notice", "chronique", "airain"})

    def test_chaque_serie_porte_ses_couleurs(self):
        serie = self.env.ref("besacraft_builds.serie_survie")
        self.assertEqual(serie.color, "#478BB2")
        self.assertEqual(serie.visual_mode, "notice")

    def test_zunk_garde_son_code(self):
        """Renommée, pas recodée : les étiquettes `serie:hardcore` des tâches tiennent."""
        serie = self.env.ref("besacraft_builds.serie_hardcore")
        self.assertEqual((serie.name, serie.code), ("Les aventures de Zunk", "hardcore"))

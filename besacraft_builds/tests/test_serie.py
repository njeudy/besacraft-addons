from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSerie(TransactionCase):
    def test_les_trois_series_sont_livrees(self):
        """The three series ship with the module: the build form is useless without them."""
        series = self.env["besacraft.serie"].search([])
        self.assertEqual(len(series), 3)
        self.assertEqual(set(series.mapped("visual_mode")), {"notice", "chronique", "airain"})

    def test_chaque_serie_porte_ses_couleurs(self):
        serie = self.env.ref("besacraft_builds.serie_survie")
        self.assertEqual(serie.color, "#478BB2")
        self.assertEqual(serie.visual_mode, "notice")

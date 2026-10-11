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
        """Renamed, not recoded: the `serie:hardcore` tags on the tasks still match."""
        serie = self.env.ref("besacraft_builds.serie_hardcore")
        self.assertEqual((serie.name, serie.code), ("Les aventures de Zunk", "hardcore"))

    def test_le_badge_steampunk_est_en_cuivre(self):
        """The copper block's own tone. It shipped as a charter bronze first, which said
        nothing about what the series builds."""
        serie = self.env.ref("besacraft_builds.serie_steampunk")
        self.assertEqual(serie.color, "#C06C50")

    def test_deux_series_ne_partagent_pas_leur_badge(self):
        """A badge names its series at a glance; two series in one colour cannot. Steampunk
        and Zunk are the close pair -- copper against red -- so this is where it would go."""
        couleurs = self.env["besacraft.serie"].search([]).mapped("color")
        self.assertEqual(len(set(couleurs)), len(couleurs), couleurs)

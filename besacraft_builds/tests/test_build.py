from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBuild(TransactionCase):
    def _build(self, **kw):
        valeurs = {"name": "L'Hôtel de Ville", "code": "043",
                   "serie_id": self.env.ref("besacraft_builds.serie_survie").id}
        valeurs.update(kw)
        return self.env["besacraft.build"].create(valeurs)

    def test_le_code_est_unique(self):
        self._build()
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self._build(name="Autre")

    def test_l_url_perd_les_zeros_de_tete(self):
        """Le code s'écrit 043 sur la fiche mais l'URL publique est /t/43."""
        self.assertEqual(self._build().website_url, "/t/43")

    def test_le_code_n_accepte_que_des_chiffres(self):
        with self.assertRaises(ValidationError):
            self._build(code="4x3")

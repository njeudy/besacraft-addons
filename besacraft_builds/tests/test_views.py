from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestViews(TransactionCase):
    def test_les_vues_se_chargent(self):
        """Une vue qui référence un champ absent ne casse qu'à l'ouverture : on l'ouvre ici."""
        for mode in ("form", "list", "kanban"):
            arch = self.env["besacraft.build"].get_view(view_type=mode)
            self.assertTrue(arch.get("arch"))

    def test_l_action_pointe_le_bon_modele(self):
        action = self.env.ref("besacraft_builds.action_build")
        self.assertEqual(action.res_model, "besacraft.build")

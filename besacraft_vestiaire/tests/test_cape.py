import base64

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .test_images import png


@tagged("post_install", "-at_install")
class TestCape(TransactionCase):
    def setUp(self):
        super().setUp()
        self.zoe = self.env["res.partner"].create({"name": "Zoé"})
        self.cape = self.env["besacraft.vestiaire.cape"].create({
            "name": "Cuivre", "image": base64.b64encode(png(64, 32)), "publiee": True})

    def test_empreintes(self):
        self.assertRegex(self.cape.empreinte, r"^[0-9a-f]{64}$")
        self.assertFalse(self.cape.empreinte_elytre)

    def test_on_ne_porte_que_ce_qu_on_possede(self):
        with self.assertRaises(ValidationError):
            self.zoe.vestiaire_cape_id = self.cape
        self.zoe._vestiaire_offrir_cape(self.cape)
        self.zoe.vestiaire_cape_id = self.cape
        self.assertEqual(self.zoe._vestiaire_capes(), self.cape)

    def test_offrir_deux_fois_ne_double_pas(self):
        self.zoe._vestiaire_offrir_cape(self.cape)
        self.zoe._vestiaire_offrir_cape(self.cape)
        self.assertEqual(len(self.zoe.vestiaire_possession_ids), 1)
        self.assertEqual(self.zoe.vestiaire_possession_ids.origine, "offert")

    def test_cape_mal_dimensionnee(self):
        with self.assertRaises(ValidationError):
            self.env["besacraft.vestiaire.cape"].create(
                {"name": "X", "image": base64.b64encode(png(64, 64))})

    def test_cape_base64_invalide(self):
        with self.assertRaises(ValidationError):
            self.env["besacraft.vestiaire.cape"].create(
                {"name": "X", "image": "!!!notbase64"})
        with self.assertRaises(ValidationError):
            self.cape.write({"image_elytre": "!!!notbase64"})

    def test_offrir_via_assistant(self):
        autre = self.env["res.partner"].create({"name": "Léo"})
        assistant = self.env["besacraft.vestiaire.offrir"].create(
            {"partner_ids": [(6, 0, (self.zoe | autre).ids)], "cape_id": self.cape.id})
        assistant.action_offrir()
        self.assertEqual(self.zoe._vestiaire_capes(), self.cape)
        self.assertEqual(autre._vestiaire_capes(), self.cape)

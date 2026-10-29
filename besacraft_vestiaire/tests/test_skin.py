import base64

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .test_images import png


@tagged("post_install", "-at_install")
class TestSkin(TransactionCase):
    def setUp(self):
        super().setUp()
        self.zoe = self.env["res.partner"].create({"name": "Zoé"})
        self.Skin = self.env["besacraft.vestiaire.skin"]

    def _skin(self, **valeurs):
        return self.Skin.create(dict({"partner_id": self.zoe.id, "name": "Rose",
                                      "image": base64.b64encode(png(64, 64))}, **valeurs))

    def test_empreinte_calculee(self):
        self.assertRegex(self._skin().empreinte, r"^[0-9a-f]{64}$")

    def test_un_seul_skin_actif(self):
        premier = self._skin(actif=True)
        second = self._skin(actif=True)
        self.assertFalse(premier.actif)
        self.assertTrue(second.actif)
        self.assertEqual(self.zoe._vestiaire_skin_actif(), second)

    def test_image_refusee(self):
        with self.assertRaises(ValidationError):
            self._skin(image=base64.b64encode(png(10, 10)))

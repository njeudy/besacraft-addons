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

    def test_lot_de_creation_un_seul_actif(self):
        autre = self.env["res.partner"].create({"name": "Léo"})
        valeurs = [{"partner_id": p.id, "name": n, "actif": True,
                    "image": base64.b64encode(png(64, 64))}
                   for p, n in ((self.zoe, "a"), (self.zoe, "b"), (autre, "c"), (autre, "d"))]
        skins = self.Skin.create(valeurs)
        self.assertEqual(skins.mapped("actif"), [False, True, False, True])
        self.assertEqual(self.zoe._vestiaire_skin_actif(), skins[1])
        self.assertEqual(autre._vestiaire_skin_actif(), skins[3])

    def test_ecriture_multiple_un_seul_actif(self):
        premier, second = self._skin(), self._skin()
        (premier | second).write({"actif": True})
        self.assertEqual(len(self.zoe.vestiaire_skin_ids.filtered("actif")), 1)

    def test_changement_de_contact_garde_un_actif(self):
        leo = self.env["res.partner"].create({"name": "Léo"})
        actif_leo = self.Skin.create({"partner_id": leo.id, "name": "x", "actif": True,
                                      "image": base64.b64encode(png(64, 64))})
        mien = self._skin(actif=True)
        mien.partner_id = leo
        self.assertEqual(len(leo.vestiaire_skin_ids.filtered("actif")), 1)
        self.assertTrue(mien.actif)
        self.assertFalse(actif_leo.actif)

    def test_base64_invalide(self):
        with self.assertRaises(ValidationError):
            self._skin(image="!!!notbase64")

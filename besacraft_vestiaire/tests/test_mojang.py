import base64
import json
from unittest.mock import patch

import requests

from odoo.tests import TransactionCase, tagged

from .test_images import png

GET = "odoo.addons.besacraft_vestiaire.tools.mojang.requests.get"
UUID = "cc67e9f6625340d4813855e5fecc4c10"


class _R:
    def __init__(self, code=200, data=None, contenu=b""):
        self.status_code, self._data, self.content = code, data, contenu

    def json(self):
        return self._data


def profil(slim):
    textures = {"textures": {"SKIN": {"url": "http://textures.minecraft.net/texture/abc"}}}
    if slim:
        textures["textures"]["SKIN"]["metadata"] = {"model": "slim"}
    valeur = base64.b64encode(json.dumps(textures).encode()).decode()
    return {"id": UUID, "properties": [{"name": "textures", "value": valeur}]}


@tagged("post_install", "-at_install")
class TestMojang(TransactionCase):
    def setUp(self):
        super().setUp()
        self.zoe = self.env["res.partner"].create({"name": "Zoé", "minecraft_uuid": UUID})
        self.env["res.users"].create({
            "name": "Zoé", "login": "zoe-mojang", "partner_id": self.zoe.id,
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})

    @patch(GET)
    def test_skin_fin_importe(self, get):
        get.side_effect = [_R(data=profil(slim=True)), _R(contenu=png(64, 64))]
        self.assertEqual(self.zoe._vestiaire_importer_skin_mojang(), 1)
        skin = self.zoe._vestiaire_skin_actif()
        self.assertEqual(skin.modele, "slim")

    @patch(GET)
    def test_skin_classique_importe(self, get):
        get.side_effect = [_R(data=profil(slim=False)), _R(contenu=png(64, 64))]
        self.zoe._vestiaire_importer_skin_mojang()
        self.assertEqual(self.zoe._vestiaire_skin_actif().modele, "classic")

    @patch(GET)
    def test_deja_un_skin_rien_a_faire(self, get):
        self.env["besacraft.vestiaire.skin"].create({
            "partner_id": self.zoe.id, "image": base64.b64encode(png(64, 64)), "actif": True})
        self.assertEqual(self.zoe._vestiaire_importer_skin_mojang(), 0)
        get.assert_not_called()

    @patch(GET, side_effect=requests.ConnectionError("hors ligne"))
    def test_mojang_injoignable_ne_casse_rien(self, _get):
        self.assertEqual(self.zoe._vestiaire_importer_skin_mojang(), 0)
        self.assertFalse(self.zoe.vestiaire_skin_ids)

    @patch(GET, return_value=_R(code=204))
    def test_profil_sans_skin(self, _get):
        self.assertEqual(self.zoe._vestiaire_importer_skin_mojang(), 0)

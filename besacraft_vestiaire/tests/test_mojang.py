import base64
import json
from unittest.mock import patch

import requests

from odoo.tests import TransactionCase, tagged

from .test_images import png

GET = "odoo.addons.besacraft_vestiaire.tools.mojang.requests.get"
UUID = "cc67e9f6625340d4813855e5fecc4c10"


class _R:
    def __init__(self, code=200, data=None, contenu=b"", entetes=None):
        self.status_code, self._data, self.content = code, data, contenu
        self.headers = entetes or {}

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i + chunk_size]

    def close(self):
        pass

    def json(self):
        return self._data


def profil(slim, url="http://textures.minecraft.net/texture/abc"):
    textures = {"textures": {"SKIN": {"url": url}}}
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

    @patch(GET)
    def test_image_recuperee_en_https_sans_redirection(self, get):
        get.side_effect = [_R(data=profil(slim=False)), _R(contenu=png(64, 64))]
        self.zoe._vestiaire_importer_skin_mojang()
        args, kwargs = get.call_args_list[1]
        self.assertEqual(args[0], "https://textures.minecraft.net/texture/abc")
        self.assertIs(kwargs.get("allow_redirects"), False)
        self.assertIs(kwargs.get("stream"), True)

    @patch(GET)
    def test_hote_etranger_refuse(self, get):
        get.side_effect = [_R(data=profil(slim=False, url="http://evil.example/skin.png"))]
        self.assertEqual(self.zoe._vestiaire_importer_skin_mojang(), 0)
        self.assertEqual(get.call_count, 1)

    @patch(GET)
    def test_schema_non_http_refuse(self, get):
        get.side_effect = [_R(data=profil(slim=False, url="file://textures.minecraft.net/x"))]
        self.assertEqual(self.zoe._vestiaire_importer_skin_mojang(), 0)
        self.assertEqual(get.call_count, 1)

    @patch(GET)
    def test_image_trop_grosse_refusee(self, get):
        get.side_effect = [_R(data=profil(slim=False)), _R(contenu=b"0" * (1024 * 1024 + 1))]
        self.assertEqual(self.zoe._vestiaire_importer_skin_mojang(), 0)

    @patch(GET)
    def test_content_length_annonce_trop_grand(self, get):
        get.side_effect = [_R(data=profil(slim=False)),
                           _R(contenu=png(64, 64), entetes={"Content-Length": str(2 * 1024 * 1024)})]
        self.assertEqual(self.zoe._vestiaire_importer_skin_mojang(), 0)

    @patch(GET)
    def test_blob_textures_pas_un_dict(self, get):
        valeur = base64.b64encode(json.dumps(["x"]).encode()).decode()
        get.side_effect = [_R(data={"properties": [{"name": "textures", "value": valeur}]})]
        self.assertEqual(self.zoe._vestiaire_importer_skin_mojang(), 0)

    @patch(GET)
    def test_skin_pas_un_dict(self, get):
        valeur = base64.b64encode(json.dumps({"textures": {"SKIN": "oops"}}).encode()).decode()
        get.side_effect = [_R(data={"properties": [{"name": "textures", "value": valeur}]})]
        self.assertEqual(self.zoe._vestiaire_importer_skin_mojang(), 0)

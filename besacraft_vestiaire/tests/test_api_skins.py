import base64
import json

from odoo.addons.besacraft_minecraft_api.controllers import base
from odoo.tests import common, tagged

from .test_images import png


@tagged("post_install", "-at_install")
class TestApiSkins(common.HttpCase):
    def setUp(self):
        super().setUp()
        base._passages.clear()
        self.addCleanup(base._passages.clear)
        portail = self.env.ref("base.group_portal")
        self.zoe, self.leo = [self.env["res.partner"].create({
            "name": nom, "minecraft_login": nom.lower(), "minecraft_uuid": uuid})
            for nom, uuid in (("Zoe", "5e1f0a2b7c3d4e8f9a6b1c2d3e4f5a6b"),
                              ("Leo", "6e1f0a2b7c3d4e8f9a6b1c2d3e4f5a6b"))]
        for partner in (self.zoe, self.leo):
            self.env["res.users"].create({
                "name": partner.name, "login": "%s-skins" % partner.minecraft_login,
                "partner_id": partner.id, "groups_id": [(6, 0, [portail.id])]})
        Skin = self.env["besacraft.vestiaire.skin"]
        self.rose = Skin.create({"partner_id": self.zoe.id, "name": "Rose", "actif": True,
                                 "image": base64.b64encode(png(64, 64))})
        self.tigre = Skin.create({"partner_id": self.zoe.id, "name": "Tigre", "modele": "slim",
                                  "image": base64.b64encode(png(64, 32))})
        self.autre = Skin.create({"partner_id": self.leo.id, "name": "Leo",
                                  "image": base64.b64encode(png(64, 64))})
        self.entete = {"Authorization": "Bearer %s"
                       % self.env["besacraft.mc.session"]._ouvrir(self.zoe).token}

    def _put(self, corps):
        return self.opener.request(
            "PUT", self.base_url() + "/mc/v1/vestiaire/skin", data=json.dumps(corps),
            headers=dict(self.entete, **{"Content-Type": "application/json"}), timeout=30)

    def test_liste_ses_skins_seulement(self):
        r = self.url_open("/mc/v1/vestiaire/skins", headers=self.entete)
        self.assertEqual(r.status_code, 200)
        skins = r.json()["skins"]
        self.assertEqual({s["id"] for s in skins}, {self.rose.id, self.tigre.id})
        tigre = next(s for s in skins if s["id"] == self.tigre.id)
        self.assertEqual((tigre["nom"], tigre["modele"], tigre["actif"]), ("Tigre", "slim", False))
        self.assertEqual(tigre["empreinte"], self.tigre.empreinte)

    def test_sans_jeton_401(self):
        self.assertEqual(self.url_open("/mc/v1/vestiaire/skins").status_code, 401)

    def test_image_d_un_skin_inactif(self):
        r = self.url_open("/mc/v1/vestiaire/skin/%d/image" % self.tigre.id, headers=self.entete)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "image/png")
        self.assertEqual(r.content, base64.b64decode(self.tigre.image))

    def test_image_d_un_autre_joueur_404(self):
        r = self.url_open("/mc/v1/vestiaire/skin/%d/image" % self.autre.id, headers=self.entete)
        self.assertEqual(r.status_code, 404)

    def test_utiliser_un_skin(self):
        r = self._put({"id": self.tigre.id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.zoe._vestiaire_skin_actif(), self.tigre)
        self.assertFalse(self.rose.actif)
        self.assertEqual([s["actif"] for s in r.json()["skins"] if s["id"] == self.tigre.id], [True])

    def test_revenir_au_skin_mojang(self):
        self.assertEqual(self._put({"id": None}).status_code, 200)
        self.assertFalse(self.zoe._vestiaire_skin_actif())

    def test_skin_d_un_autre_joueur_refuse(self):
        r = self._put({"id": self.autre.id})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.zoe._vestiaire_skin_actif(), self.rose)
        self.assertFalse(self.autre.actif)

    def test_id_invalide_400(self):
        self.assertEqual(self._put({"id": "1"}).status_code, 400)
        self.assertEqual(self._put({"id": True}).status_code, 400)

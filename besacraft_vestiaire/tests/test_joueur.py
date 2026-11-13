import base64

from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from .test_images import png
from .test_points import PointsCommon


@tagged("post_install", "-at_install")
class TestJoueur(PointsCommon):
    """The computed fields behind the Players and Cosmetics kanban views."""

    def test_comptes_possedes(self):
        # PointsCommon: two wings and a cat head owned by everyone, plus one base emote.
        self.assertEqual(self.zoe.vestiaire_cosmetique_count, 3)
        self.assertEqual(self.zoe.vestiaire_emote_count, 1)
        self.zoe._vestiaire_offrir_cosmetique(self.chapeau)
        self.zoe._vestiaire_offrir_cosmetique(self.guitare)
        self.zoe.invalidate_recordset(["vestiaire_cosmetique_count", "vestiaire_emote_count"])
        self.assertEqual(self.zoe.vestiaire_cosmetique_count, 4)
        self.assertEqual(self.zoe.vestiaire_emote_count, 2)

    def test_objet_non_publie_pas_compte(self):
        self.zoe._vestiaire_offrir_cosmetique(self.chapeau)
        self.chapeau.publie = False
        self.tete.publie = False
        self.zoe.invalidate_recordset(["vestiaire_cosmetique_count"])
        self.assertEqual(self.zoe.vestiaire_cosmetique_count, 2)

    def test_comptes_sur_un_lot(self):
        leo = self.env["res.partner"].create({"name": "Léo", "minecraft_uuid":
                                              "0f0e0d0c0b0a49088776655443322110"})
        self.zoe._vestiaire_offrir_cosmetique(self.chapeau)
        lot = self.zoe | leo
        self.assertEqual(lot.mapped("vestiaire_cosmetique_count"), [4, 3])

    def test_possesseurs(self):
        self.assertEqual(self.chapeau.possesseur_count, 0)
        leo = self.env["res.partner"].create({"name": "Léo"})
        (self.zoe | leo)._vestiaire_offrir_cosmetique(self.chapeau)
        self.chapeau.invalidate_recordset(["possesseur_count"])
        self.assertEqual(self.chapeau.possesseur_count, 2)
        self.assertEqual(self.guitare.possesseur_count, 0)

    def test_compte_valide(self):
        self.assertTrue(self.zoe.vestiaire_compte_valide)
        sans_compte = self.env["res.partner"].create({
            "name": "Léo", "minecraft_uuid": "0f0e0d0c0b0a49088776655443322110"})
        self.assertFalse(sans_compte.vestiaire_compte_valide)

    def test_apercu_du_skin_actif(self):
        self.assertFalse(self.zoe.vestiaire_skin_apercu)
        Skin = self.env["besacraft.vestiaire.skin"]
        image = base64.b64encode(png(64, 64))
        Skin.create({"partner_id": self.zoe.id, "name": "Old", "image": image})
        actif = Skin.create({"partner_id": self.zoe.id, "name": "Rose", "image": image,
                             "actif": True})
        self.zoe.invalidate_recordset(["vestiaire_skin_apercu"])
        self.assertEqual(self.zoe.vestiaire_skin_apercu, actif.image)

    def test_menus_et_actions(self):
        configuration = self.env.ref("besacraft_vestiaire.menu_vestiaire_configuration")
        self.assertEqual(self.env.ref("besacraft_vestiaire.menu_vestiaire_bareme").parent_id,
                         configuration)
        self.assertEqual(self.env.ref("besacraft_vestiaire.menu_vestiaire_cles").parent_id,
                         configuration)
        joueurs = self.env.ref("besacraft_vestiaire.vestiaire_joueur_action")
        self.assertEqual(joueurs.view_mode.split(",")[0], "kanban")
        Partner = self.env["res.partner"]
        self.assertIn(self.zoe, Partner.search(safe_eval(joueurs.domain)))
        self.assertNotIn(Partner.create({"name": "Not a player"}),
                         Partner.search(safe_eval(joueurs.domain)))
        emotes = self.env.ref("besacraft_vestiaire.vestiaire_emote_action")
        Cosmetique = self.env["besacraft.vestiaire.cosmetique"]
        self.assertEqual(set(Cosmetique.search(safe_eval(emotes.domain)).mapped("genre")),
                         {"emote"})

    def test_vues_par_defaut_des_contacts_inchangees(self):
        # The Players views carry a high priority so the Contacts app keeps its own.
        Partner = self.env["res.partner"]
        for vue in ("kanban", "list", "search"):
            self.assertNotIn("vestiaire", Partner.get_view(view_type=vue)["arch"],
                             f"default {vue} view of res.partner must stay untouched")

    def test_apercu_url_follows_code_and_kind(self):
        Cosmetique = self.env["besacraft.vestiaire.cosmetique"]
        cosmetique = Cosmetique.create({"code": "test_apercu", "name": "Preview", "genre": "cosmetique"})
        emote = Cosmetique.create({"code": "test_salut", "name": "Wave", "genre": "emote"})
        self.assertEqual(cosmetique.apercu_url, "/besacraft_vestiaire/static/img/cosmetiques/test_apercu.png")
        self.assertEqual(emote.apercu_url, "/besacraft_vestiaire/static/img/emotes/test_salut.gif")

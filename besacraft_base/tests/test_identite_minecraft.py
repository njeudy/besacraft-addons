from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.addons.besacraft_base.controlers.portal import CustomerPortal
from odoo.tests import common, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestIdentiteMinecraft(common.TransactionCase):
    """The Minecraft UUID decides who a player is, so it must name one partner.

    Mojang proves the player owns the UUID; Odoo decides which customer that UUID
    belongs to. The second half is only as strong as this table.
    """

    @mute_logger("odoo.sql_db")
    def test_un_uuid_ne_peut_designer_qu_un_partenaire(self):
        self.env["res.partner"].create({"name": "Zunk", "minecraft_uuid": "a" * 32})
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.env["res.partner"].create({"name": "Sosie", "minecraft_uuid": "a" * 32})
            self.env.flush_all()

    def test_les_partenaires_sans_uuid_cohabitent(self):
        """Non-regression: most customers never play, and NULL must stay free."""
        self.env["res.partner"].create({"name": "Sans compte 1"})
        self.env["res.partner"].create({"name": "Sans compte 2"})
        self.env.flush_all()

    def test_le_portail_n_ecrit_pas_l_uuid(self):
        """The UUID is derived from the login, never posted.

        Odoo writes every key of `_get_optional_fields()` found in the POST body, so
        leaving the UUID there lets any customer claim another player's identity --
        the `disabled` attribute on the input only binds the browser.
        """
        champs = CustomerPortal()._get_optional_fields()
        self.assertNotIn("minecraft_uuid", champs)
        self.assertIn("minecraft_login", champs)


@tagged("post_install", "-at_install")
class TestResolutionDuPseudo(common.TransactionCase):
    """Writing the UUID: one lookup per contact, and one single written form."""

    def test_la_forme_stockee_est_celle_de_mojang(self):
        """playerdb.co answers with dashes, Mojang without: one of them has to give.

        The game is the side that cannot be changed, so its form wins -- otherwise
        the portal and the mod hold the same identity under two different keys and
        no player is ever found.
        """
        Partenaire = self.env["res.partner"]
        self.assertEqual(
            Partenaire.normaliser_uuid_minecraft("46029DC4-4a8d-4b6e-95c2-9debad8d61c4"),
            "46029dc44a8d4b6e95c29debad8d61c4")
        self.assertEqual(
            Partenaire.normaliser_uuid_minecraft("069a79f444e94726a5befca90e38aaf5"),
            "069a79f444e94726a5befca90e38aaf5")
        self.assertFalse(Partenaire.normaliser_uuid_minecraft(""))
        self.assertFalse(Partenaire.normaliser_uuid_minecraft(False))

    def test_chaque_contact_resout_son_propre_pseudo(self):
        """Resolving on `self` gave every contact of the set the first one's UUID.

        That is how fourteen different players ended up sharing one identity on the
        dev database -- the very impersonation this module must not allow, reached
        by accident rather than by attack.
        """
        Partenaire = self.env["res.partner"]
        un = Partenaire.create({"name": "Un", "minecraft_login": "besacraft01"})
        deux = Partenaire.create({"name": "Deux", "minecraft_login": "besacraft02"})
        connus = {"besacraft01": "a" * 32, "besacraft02": "b" * 32}

        def faux_info(self):
            return {"username": self.minecraft_login,
                    "id": connus[self.minecraft_login], "avatar": False}

        with patch.object(type(un), "get_minecraft_player_info", faux_info), \
                patch.object(type(un), "set_image_from_url", lambda self, url: False):
            (un | deux).set_minecraft_player_info()
        self.assertEqual(un.minecraft_uuid, "a" * 32)
        self.assertEqual(deux.minecraft_uuid, "b" * 32)

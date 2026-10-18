import secrets
from datetime import timedelta

from odoo import api, fields, models

DUREE = 60  # seconds: long enough for a round trip to Mojang, short enough to be useless later


class BesacraftMcChallenge(models.Model):
    """A one-shot serverId the player's session signs, so Mojang can vouch for them.

    Same handshake as a game server's: we hand out a random id, the client tells
    Mojang it joined that id, and we ask Mojang who did. Nothing secret travels.
    """

    _name = "besacraft.mc.challenge"
    _description = "Minecraft Auth Challenge"

    server_id = fields.Char(required=True, index=True)
    expire_le = fields.Datetime(required=True)

    @api.model
    def _nouveau(self):
        return self.create({
            "server_id": secrets.token_hex(16),
            "expire_le": fields.Datetime.now() + timedelta(seconds=DUREE),
        })

    @api.model
    def _consommer(self, server_id):
        """Return True once for a live challenge, then destroy it."""
        defi = self.search([("server_id", "=", server_id),
                            ("expire_le", ">", fields.Datetime.now())], limit=1)
        if not defi:
            return False
        defi.unlink()
        return True

    @api.model
    def _purger(self):
        self.search([("expire_le", "<", fields.Datetime.now())]).unlink()

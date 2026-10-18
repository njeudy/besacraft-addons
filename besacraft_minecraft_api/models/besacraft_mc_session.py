import logging
import secrets
from datetime import timedelta

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

HASJOINED = "https://sessionserver.mojang.com/session/minecraft/hasJoined"
DUREE_JOURS = 30


class BesacraftMcSession(models.Model):
    _name = "besacraft.mc.session"
    _description = "Minecraft API Session"

    token = fields.Char(required=True, index=True, copy=False)
    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    expire_le = fields.Datetime(required=True)

    @api.model
    def _uuid_certifie(self, pseudo, server_id):
        """The UUID Mojang says answered our challenge, or False.

        We never trust the UUID the client announces: that is the whole point of the
        handshake. A network failure returns False too -- refusing is the safe answer.
        """
        try:
            reponse = requests.get(
                HASJOINED, params={"username": pseudo, "serverId": server_id}, timeout=10)
        except requests.RequestException as erreur:
            _logger.warning("Mojang unreachable: %s", erreur)
            return False
        if reponse.status_code != 200 or not reponse.content:
            return False
        return (reponse.json() or {}).get("id") or False

    @api.model
    def _ouvrir(self, partner):
        return self.create({
            "token": secrets.token_urlsafe(32),
            "partner_id": partner.id,
            "expire_le": fields.Datetime.now() + timedelta(days=DUREE_JOURS),
        })

    @api.model
    def _partenaire_du_jeton(self, token):
        if not token:
            return self.env["res.partner"]
        session = self.search([("token", "=", token),
                               ("expire_le", ">", fields.Datetime.now())], limit=1)
        return session.partner_id

    @api.model
    def _purger(self):
        self.search([("expire_le", "<", fields.Datetime.now())]).unlink()

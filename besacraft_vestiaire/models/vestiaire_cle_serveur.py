import hashlib
import secrets

from odoo import _, api, fields, models


class BesacraftVestiaireCleServeur(models.Model):
    """The key of one of our Minecraft servers. It can only report rewards; the
    amount always comes from the scale."""

    _name = "besacraft.vestiaire.cle.serveur"
    _description = "Wardrobe server key"

    name = fields.Char(required=True)
    cle_hash = fields.Char(string="Key hash", readonly=True, copy=False, index=True)
    active = fields.Boolean(default=True)
    derniere_utilisation = fields.Datetime(string="Last used", readonly=True)

    @api.model
    def _hacher(self, cle):
        return hashlib.sha256(cle.encode()).hexdigest()

    def _generer(self):
        self.ensure_one()
        cle = secrets.token_urlsafe(32)
        self.cle_hash = self._hacher(cle)
        return cle

    def action_generer(self):
        """Show the new key once: only its hash is kept."""
        cle = self._generer()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("New key for %s", self.name),
                "message": _("Copy it now, it will not be shown again: %s", cle),
                "sticky": True,
                "type": "warning",
            },
        }

    @api.model
    def _par_cle(self, cle):
        if not cle:
            return self.browse()
        return self.search([("cle_hash", "=", self._hacher(cle))], limit=1)

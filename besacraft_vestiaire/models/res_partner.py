from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _vestiaire_valide(self):
        """A wardrobe account is a contact with a Minecraft UUID and an active user."""
        self.ensure_one()
        return bool(self.minecraft_uuid) and bool(self.user_ids)

    @api.model
    def _vestiaire_par_uuid(self, uuid):
        uuid = self.normaliser_uuid_minecraft(uuid)
        if not uuid:
            return self.browse()
        return self.search([("minecraft_uuid", "=", uuid)], limit=1)

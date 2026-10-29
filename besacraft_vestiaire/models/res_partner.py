from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    vestiaire_parent_email = fields.Char(string="Parent email")
    vestiaire_skin_ids = fields.One2many("besacraft.vestiaire.skin", "partner_id", string="Skins")

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

    def _vestiaire_skin_actif(self):
        self.ensure_one()
        return self.vestiaire_skin_ids.filtered("actif")[:1]

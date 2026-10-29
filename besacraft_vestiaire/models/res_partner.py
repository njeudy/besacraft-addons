import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import mojang

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    vestiaire_parent_email = fields.Char(string="Parent email")
    vestiaire_skin_ids = fields.One2many("besacraft.vestiaire.skin", "partner_id", string="Skins")
    vestiaire_possession_ids = fields.One2many("besacraft.vestiaire.possession", "partner_id",
                                               string="Owned items")
    vestiaire_cape_id = fields.Many2one("besacraft.vestiaire.cape", string="Worn cape")

    @api.constrains("vestiaire_cape_id")
    def _check_cape_possedee(self):
        for partner in self:
            if partner.vestiaire_cape_id and partner.vestiaire_cape_id not in partner._vestiaire_capes():
                raise ValidationError(_("You can only wear a cape you own."))

    def _vestiaire_capes(self):
        self.ensure_one()
        return self.vestiaire_possession_ids.cape_id

    def _vestiaire_offrir_cape(self, cape):
        for partner in self:
            if cape not in partner._vestiaire_capes():
                self.env["besacraft.vestiaire.possession"].create(
                    {"partner_id": partner.id, "cape_id": cape.id, "origine": "offert"})

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

    def _vestiaire_importer_skin_mojang(self):
        """Seed a first skin from Mojang for valid accounts that have none. Re-runnable."""
        crees = 0
        for partner in self.filtered(lambda p: p._vestiaire_valide() and not p.vestiaire_skin_ids):
            texture = mojang.texture_skin(partner.minecraft_uuid)
            if not texture:
                continue
            data, modele = texture
            try:
                with self.env.cr.savepoint():
                    self.env["besacraft.vestiaire.skin"].create({
                        "partner_id": partner.id, "name": "Mojang",
                        "image": base64.b64encode(data), "modele": modele, "actif": True})
            except ValidationError as erreur:
                _logger.warning("Mojang skin of %s refused: %s", partner.minecraft_login, erreur)
                continue
            crees += 1
        return crees

    def action_vestiaire_importer_skin_mojang(self):
        self._vestiaire_importer_skin_mojang()
        return True

    @api.model
    def _vestiaire_cron_importer_skins(self):
        self.search([("minecraft_uuid", "!=", False), ("user_ids", "!=", False),
                     ("vestiaire_skin_ids", "=", False)])._vestiaire_importer_skin_mojang()

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..tools import images


class BesacraftVestiaireSkin(models.Model):
    _name = "besacraft.vestiaire.skin"
    _description = "Wardrobe skin"
    _order = "actif desc, id desc"

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True, default="Skin")
    image = fields.Binary(required=True, attachment=True)
    modele = fields.Selection([("classic", "Classic"), ("slim", "Slim")],
                              string="Model", required=True, default="classic")
    empreinte = fields.Char(string="Hash", compute="_compute_empreinte", store=True, index=True)
    actif = fields.Boolean(string="Active")

    @api.depends("image")
    def _compute_empreinte(self):
        for skin in self:
            try:
                skin.empreinte = images.empreinte(images.decoder(skin.image)) if skin.image else False
            except ValidationError:
                skin.empreinte = False  # reported by the _check_image constraint

    @api.constrains("image")
    def _check_image(self):
        for skin in self:
            images.verifier_skin(images.decoder(skin.image))

    @api.model_create_multi
    def create(self, vals_list):
        skins = super().create(vals_list)
        skins.filtered("actif")._garder_un_seul_actif()
        return skins

    def write(self, vals):
        res = super().write(vals)
        if vals.get("actif") or "partner_id" in vals:
            self.filtered("actif")._garder_un_seul_actif()
        return res

    def _garder_un_seul_actif(self):
        """Per contact, the last of these records wins; every other active skin is switched off."""
        gagnants = {}
        for skin in self.sorted("id"):
            gagnants[skin.partner_id.id] = skin
        for partner_id, gagnant in gagnants.items():
            self.search([("partner_id", "=", partner_id), ("id", "!=", gagnant.id),
                         ("actif", "=", True)]).write({"actif": False})

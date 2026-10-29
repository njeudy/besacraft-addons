import base64

from odoo import api, fields, models

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
            skin.empreinte = images.empreinte(base64.b64decode(skin.image)) if skin.image else False

    @api.constrains("image")
    def _check_image(self):
        for skin in self:
            images.verifier_skin(base64.b64decode(skin.image))

    @api.model_create_multi
    def create(self, vals_list):
        skins = super().create(vals_list)
        skins.filtered("actif")._desactiver_les_autres()
        return skins

    def write(self, vals):
        res = super().write(vals)
        if vals.get("actif"):
            self._desactiver_les_autres()
        return res

    def _desactiver_les_autres(self):
        for skin in self:
            self.search([("partner_id", "=", skin.partner_id.id), ("id", "!=", skin.id),
                         ("actif", "=", True)]).write({"actif": False})

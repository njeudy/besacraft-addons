from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..tools import images


class BesacraftVestiaireCape(models.Model):
    _name = "besacraft.vestiaire.cape"
    _description = "Wardrobe cape"

    name = fields.Char(required=True, translate=True)
    image = fields.Binary(required=True, attachment=True)
    image_elytre = fields.Binary(string="Elytra image", attachment=True)
    empreinte = fields.Char(string="Hash", compute="_compute_empreintes", store=True, index=True)
    empreinte_elytre = fields.Char(string="Elytra hash", compute="_compute_empreintes",
                                   store=True, index=True)
    publiee = fields.Boolean(string="Published", default=True)

    @staticmethod
    def _empreinte_ou_faux(valeur):
        if not valeur:
            return False
        try:
            return images.empreinte(images.decoder(valeur))
        except ValidationError:
            return False  # reported by the _check_images constraint

    @api.depends("image", "image_elytre")
    def _compute_empreintes(self):
        for cape in self:
            cape.empreinte = self._empreinte_ou_faux(cape.image)
            cape.empreinte_elytre = self._empreinte_ou_faux(cape.image_elytre)

    @api.constrains("image", "image_elytre")
    def _check_images(self):
        for cape in self:
            for valeur in (cape.image, cape.image_elytre):
                if valeur:
                    images.verifier_cape(images.decoder(valeur))

    @api.model
    def _verifier_valeurs(self, vals):
        # The attachment layer decodes the base64 before any constraint runs.
        for champ in ("image", "image_elytre"):
            if vals.get(champ):
                images.verifier_cape(images.decoder(vals[champ]))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._verifier_valeurs(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._verifier_valeurs(vals)
        return super().write(vals)

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BesacraftBuildChapter(models.Model):
    """A chapter of a build: a named run of layers, which the shop may give away.

    Until now chapters only lived in buildplan's guide; the product sheet lists them and
    marks the free ones, so they are stored here, imported from chapters.json.
    """

    _name = "besacraft.build.chapter"
    _description = "Build Chapter"
    _order = "build_id, sequence, id"

    build_id = fields.Many2one("besacraft.build", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char("Title", required=True, translate=True)
    first_layer = fields.Integer(help="First layer (or step) of the chapter, as numbered in "
                                      "the tutorial.")
    last_layer = fields.Integer(help="Last layer (or step) of the chapter, included.")
    free = fields.Boolean(help="Given away: readable without buying the tutorial.")

    @api.constrains("first_layer", "last_layer")
    def _check_bornes(self):
        for chapitre in self:
            if chapitre.last_layer and chapitre.first_layer > chapitre.last_layer:
                raise ValidationError(
                    "A chapter cannot end before the layer it starts with.")

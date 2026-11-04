from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BesacraftVestiaireOffrir(models.TransientModel):
    _name = "besacraft.vestiaire.offrir"
    _description = "Give a wardrobe item or points"

    partner_ids = fields.Many2many(
        "res.partner", string="Players",
        default=lambda self: self.env.context.get("active_ids")
        if self.env.context.get("active_model") == "res.partner" else False)
    quoi = fields.Selection([("cape", "A cape"), ("cosmetique", "A cosmetic or an emote"),
                             ("points", "Points")], string="Give", required=True, default="cape")
    cape_id = fields.Many2one("besacraft.vestiaire.cape", string="Cape")
    cosmetique_id = fields.Many2one("besacraft.vestiaire.cosmetique", string="Cosmetic or emote")
    points = fields.Integer()
    libelle = fields.Char(string="Message to the player",
                          help="Shown in game, e.g. 'Well done for the Battant bridge!'")

    @api.onchange("quoi")
    def _onchange_quoi(self):
        if self.quoi != "cape":
            self.cape_id = False
        if self.quoi != "cosmetique":
            self.cosmetique_id = False

    def action_offrir(self):
        self.ensure_one()
        if self.quoi == "cape":
            if not self.cape_id:
                raise UserError(_("Choose a cape."))
            self.partner_ids._vestiaire_offrir_cape(self.cape_id)
        elif self.quoi == "cosmetique":
            if not self.cosmetique_id:
                raise UserError(_("Choose a cosmetic or an emote."))
            self.partner_ids._vestiaire_offrir_cosmetique(self.cosmetique_id)
        else:
            if self.points <= 0:
                raise UserError(_("Give a positive number of points."))
            for partner in self.partner_ids:
                partner._vestiaire_crediter(self.points, "cadeau", self.libelle or _("Gift"))
        return {"type": "ir.actions.act_window_close"}

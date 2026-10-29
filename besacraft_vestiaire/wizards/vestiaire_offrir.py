from odoo import fields, models


class BesacraftVestiaireOffrir(models.TransientModel):
    _name = "besacraft.vestiaire.offrir"
    _description = "Give a cape"

    partner_ids = fields.Many2many(
        "res.partner", string="Players",
        default=lambda self: self.env.context.get("active_ids")
        if self.env.context.get("active_model") == "res.partner" else False)
    cape_id = fields.Many2one("besacraft.vestiaire.cape", string="Cape", required=True)

    def action_offrir(self):
        self.ensure_one()
        self.partner_ids._vestiaire_offrir_cape(self.cape_id)
        return {"type": "ir.actions.act_window_close"}

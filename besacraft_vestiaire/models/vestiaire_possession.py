from odoo import fields, models


class BesacraftVestiairePossession(models.Model):
    _name = "besacraft.vestiaire.possession"
    _description = "Wardrobe ownership"

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    cape_id = fields.Many2one("besacraft.vestiaire.cape", required=True, ondelete="cascade")
    origine = fields.Selection([("offert", "Gift")], string="Origin",
                               required=True, default="offert")
    date = fields.Datetime(default=fields.Datetime.now, required=True)

    _sql_constraints = [("unique_cape", "unique(partner_id, cape_id)",
                         "A player owns a cape only once.")]

    def unlink(self):
        for possession in self:
            partner = possession.partner_id.sudo()
            if partner.vestiaire_cape_id == possession.cape_id:
                partner.vestiaire_cape_id = False
        return super().unlink()

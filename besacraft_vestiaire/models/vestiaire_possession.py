from odoo import fields, models


class BesacraftVestiairePossession(models.Model):
    _name = "besacraft.vestiaire.possession"
    _description = "Wardrobe ownership"

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    cape_id = fields.Many2one("besacraft.vestiaire.cape", ondelete="cascade")
    cosmetique_id = fields.Many2one("besacraft.vestiaire.cosmetique", string="Cosmetic or emote",
                                    ondelete="cascade")
    origine = fields.Selection([("offert", "Gift"), ("achat", "Purchase"), ("gagne", "Reward")],
                               string="Origin", required=True, default="offert")
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    annonce = fields.Boolean(string="Announced in game")

    _sql_constraints = [
        ("unique_cape", "unique(partner_id, cape_id)", "A player owns a cape only once."),
        ("unique_cosmetique", "unique(partner_id, cosmetique_id)",
         "A player owns a cosmetic only once."),
        ("un_objet", "check((cape_id IS NULL) <> (cosmetique_id IS NULL))",
         "An ownership is either a cape or a cosmetic."),
    ]

    def unlink(self):
        for possession in self:
            partner = possession.partner_id.sudo()
            if possession.cape_id and partner.vestiaire_cape_id == possession.cape_id:
                partner.vestiaire_cape_id = False
        partners = self.partner_id.sudo()
        resultat = super().unlink()
        partners._vestiaire_ranger()
        return resultat

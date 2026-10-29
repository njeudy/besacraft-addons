import secrets
import string
from datetime import timedelta

from odoo import api, fields, models

ALPHABET = string.ascii_letters + string.digits
DUREE_HEURES = 24


class BesacraftVestiaireCode(models.Model):
    _name = "besacraft.vestiaire.code"
    _description = "Wardrobe account request code"

    code = fields.Char(required=True, index=True, copy=False)
    uuid = fields.Char(required=True)
    pseudo = fields.Char(required=True)
    expire_le = fields.Datetime(required=True)

    _sql_constraints = [("code_unique", "unique(code)", "Request codes are unique.")]

    @api.model
    def _emettre(self, uuid, pseudo):
        return self.create({
            "code": "".join(secrets.choice(ALPHABET) for _ in range(12)),
            "uuid": self.env["res.partner"].normaliser_uuid_minecraft(uuid),
            "pseudo": pseudo,
            "expire_le": fields.Datetime.now() + timedelta(hours=DUREE_HEURES),
        })

    @api.model
    def _trouver(self, code):
        if not code:
            return self.browse()
        return self.search([("code", "=", code),
                            ("expire_le", ">", fields.Datetime.now())], limit=1)

    @api.model
    def _url(self, code):
        site = self.env["website"].sudo().search([("domain", "ilike", "besacraft.fr")], limit=1)
        racine = (site.domain or self.env["ir.config_parameter"].sudo()
                  .get_param("web.base.url")).rstrip("/")
        return "%s/vestiaire/demande?code=%s" % (racine, code)

    @api.model
    def _purger(self):
        self.search([("expire_le", "<", fields.Datetime.now())]).unlink()

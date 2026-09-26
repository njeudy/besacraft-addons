from odoo import models


class Website(models.Model):
    """Register the tutorials with the site's search box."""

    _inherit = "website"

    def _search_get_details(self, search_type, order, options):
        result = super()._search_get_details(search_type, order, options)
        # Seulement là où le catalogue est servi : ailleurs les pages répondent 404, et
        # proposer un résultat qui mène à une page introuvable est pire que rien.
        if self.besacraft_enabled and search_type in ("builds", "all"):
            result.append(
                self.env["besacraft.build"]._search_get_detail(self, order, options))
        return result

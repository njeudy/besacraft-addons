from odoo import models


class Website(models.Model):
    """Register the tutorials with the site's search box."""

    _inherit = "website"

    def _besacraft_series(self):
        """The series this site publishes. Empty means the site has no catalogue.

        Derived rather than switched on by a flag of its own: a flag and the series could
        disagree, and both ways look broken -- a flag with no series serves an empty shelf,
        a series without the flag is published to a site that 404s.
        """
        self.ensure_one()
        return self.env["besacraft.serie"].sudo().search([("website_ids", "in", self.id)])

    def _search_get_details(self, search_type, order, options):
        result = super()._search_get_details(search_type, order, options)
        # Seulement là où le catalogue est servi : ailleurs les pages répondent 404, et
        # proposer un résultat qui mène à une page introuvable est pire que rien.
        if search_type in ("builds", "all") and self._besacraft_series():
            result.append(
                self.env["besacraft.build"]._search_get_detail(self, order, options))
        return result

from odoo import fields, models


class Website(models.Model):
    """Which of this database's sites is the Besacraft one."""

    _inherit = "website"

    # Scoping the RECORDS was not enough: with website_id set on every build, the other
    # sites served /builds as an empty shelf, chrome and all. A catalogue that exists but
    # holds nothing is worse than no catalogue -- it looks broken. The routes now answer
    # 404 wherever this flag is off, so the feature simply does not exist there.
    #
    # A flag rather than a check on the theme: a site can be redressed without ceasing to
    # be Besacraft, and a module has no business reading a theme's name.
    besacraft_enabled = fields.Boolean(
        "Besacraft build catalogue",
        help="Serve /builds and the tutorial pages on this website.",
    )

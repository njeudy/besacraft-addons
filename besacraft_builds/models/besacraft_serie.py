from odoo import fields, models


class BesacraftSerie(models.Model):
    """One of the channel's series. Drives the badge colour and the visual mode.

    The visual mode is not decoration: it selects which of the three validated art
    directions a page renders in, so it belongs to the data, not to a template.
    """

    _name = "besacraft.serie"
    _description = "Build Series"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    color = fields.Char("Badge Colour", required=True, help="Hex, e.g. #478BB2.")
    badge_ink = fields.Char("Badge Ink", required=True, help="Text colour over the badge.")
    visual_mode = fields.Selection(
        [("notice", "Notice"), ("chronique", "Chronique"), ("airain", "Coeur d'Airain")],
        required=True, default="notice",
    )
    # The series, not the build, says where a tutorial is shown: the same database serves
    # several sites, and a site carries whole series -- the author's own site shows them
    # all, the Besacraft site only its own. Filing each build under one site could not say
    # « both », and left the choice to whoever imported the build.
    website_ids = fields.Many2many(
        "website", string="Websites",
        help="Sites whose catalogue lists this series. A site with no series has no "
             "catalogue at all: /builds and the tutorial pages answer 404 there.")

    subtitle = fields.Char(translate=True, help="One line under the series name.")
    # Éditable sur le site (t-field) : la page de série est un texte qu'on retouche en ligne,
    # pas un gabarit à redéployer.
    description = fields.Html(translate=True)
    logo = fields.Image(max_width=1024, max_height=1024)
    episode_ids = fields.One2many("besacraft.episode", "serie_id")
    episode_count = fields.Integer(compute="_compute_episode_count")

    def _compute_episode_count(self):
        groupes = self.env["besacraft.episode"].sudo()._read_group(
            [("serie_id", "in", self.ids)], ["serie_id"], ["__count"])
        par_serie = {serie.id: n for serie, n in groupes}
        for serie in self:
            serie.episode_count = par_serie.get(serie.id, 0)

    _sql_constraints = [("code_uniq", "unique(code)", "A series code must be unique.")]

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

CODE_RE = re.compile(r"^\d+$")


class BesacraftBuild(models.Model):
    """A build tutorial: what buildplan produced, ready to be published.

    Counts come from the plan and are never recomputed here -- the files are the
    reference, and a rounding of our own would silently contradict the video and
    the printed notice.
    """

    _name = "besacraft.build"
    _description = "Build Tutorial"
    _inherit = ["website.published.mixin"]
    _order = "code"

    name = fields.Char(required=True, translate=True,
                       help="Editorial title, accented. Not the schematic's technical name.")
    code = fields.Char(required=True, index=True, copy=False,
                       help="Tutorial number, zero-padded to three digits: 043 -> /t/43.")
    serie_id = fields.Many2one("besacraft.serie", required=True, ondelete="restrict")
    accroche = fields.Text("Tagline", translate=True)
    level = fields.Selection(
        [("debutant", "Beginner"), ("confirme", "Confident"), ("forgeron", "Blacksmith")],
        default="debutant", required=True,
    )
    state = fields.Selection(
        [("brouillon", "Draft"), ("tourne", "Filmed"), ("publie", "Published")],
        default="brouillon", required=True,
    )
    block_count = fields.Integer(help="From the plan. Never recomputed.")
    layer_count = fields.Integer(help="From the plan. Never recomputed.")
    size_x = fields.Integer()
    size_y = fields.Integer()
    size_z = fields.Integer()
    palette_label = fields.Char(help='Free text, e.g. "11 block types".')
    has_recipes = fields.Boolean(help="True when recipes.json was generated; drives the recipe UI.")
    overview_image = fields.Image("Overview")
    youtube_url = fields.Char()
    viewer_attachment_id = fields.Many2one("ir.attachment", ondelete="set null")
    build_json_attachment_id = fields.Many2one("ir.attachment", ondelete="set null")
    layer_ids = fields.One2many("besacraft.build.layer", "build_id")

    _sql_constraints = [("code_uniq", "unique(code)", "A tutorial number must be unique.")]

    @api.constrains("code")
    def _check_code(self):
        for build in self:
            if not CODE_RE.match(build.code or ""):
                raise ValidationError("The tutorial number must contain digits only.")

    def _compute_website_url(self):
        # website.published.mixin's hook: the public URL drops the padding zeros.
        super()._compute_website_url()
        for build in self:
            build.website_url = "/t/%d" % int(build.code) if build.code else ""

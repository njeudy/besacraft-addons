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
    layer_offset = fields.Integer(
        "Viewer Offset",
        help="Foundation layers sunk below ground level, which the tutorial skips but the "
             "viewer still counts. Layer 1 here is layer 1+offset there.")
    overview_image = fields.Image("Overview")
    youtube_url = fields.Char()
    viewer_attachment_id = fields.Many2one("ir.attachment", ondelete="set null")
    build_json_attachment_id = fields.Many2one("ir.attachment", ondelete="set null")
    layer_ids = fields.One2many("besacraft.build.layer", "build_id")
    enroll = fields.Selection(
        [("public", "Free"), ("payment", "On payment"), ("invite", "On invitation")],
        default="public", required=True,
        help="Free: anyone. On payment: access is granted when the order is confirmed.",
    )
    product_id = fields.Many2one(
        "product.product", string="Product",
        help="The product that grants access. Required when enroll is 'payment'.",
    )
    member_ids = fields.One2many("besacraft.build.member", "build_id", string="Access Lines")
    # Computed, never stored: a Many2many stored on besacraft_build_member would fight the
    # model that already owns that table -- Odoo builds the m2m table without an id column,
    # and every search on the model then fails on "column ... .id does not exist".
    # website_slides computes slide.channel.partner_ids for exactly this reason.
    partner_ids = fields.Many2many(
        "res.partner", string="Members", compute="_compute_partner_ids", search="_search_partner_ids",
    )

    _sql_constraints = [
        ("code_uniq", "unique(code)", "A tutorial number must be unique."),
        ("product_required_on_payment",
         "CHECK (enroll != 'payment' OR product_id IS NOT NULL)",
         "A paying build needs a product."),
    ]

    @api.constrains("code")
    def _check_code(self):
        for build in self:
            if not CODE_RE.match(build.code or ""):
                raise ValidationError("The tutorial number must contain digits only.")

    @api.depends("member_ids.partner_id")
    def _compute_partner_ids(self):
        for build in self:
            build.partner_ids = build.member_ids.partner_id

    def _search_partner_ids(self, operator, value):
        membres = self.env["besacraft.build.member"].sudo().search(
            [("partner_id", operator, value)])
        return [("id", "in", membres.build_id.ids)]

    def _action_add_members(self, partners, member_status="joined"):
        """Grant access. Idempotent: an existing member is left untouched."""
        Member = self.env["besacraft.build.member"].sudo()
        a_creer = []
        for build in self:
            deja = Member.search([("build_id", "=", build.id),
                                  ("partner_id", "in", partners.ids)]).mapped("partner_id")
            for partner in partners - deja:
                a_creer.append({"build_id": build.id, "partner_id": partner.id,
                                "member_status": member_status})
        return Member.create(a_creer) if a_creer else Member

    def is_accessible_by(self, partner):
        """True when this partner may see the viewer and the notice."""
        self.ensure_one()
        if self.enroll == "public":
            return True
        if not partner:
            return False
        return bool(self.env["besacraft.build.member"].sudo().search_count(
            [("build_id", "=", self.id), ("partner_id", "=", partner.id)]))

    def _compute_website_url(self):
        # website.published.mixin's hook: the public URL drops the padding zeros.
        super()._compute_website_url()
        for build in self:
            build.website_url = "/t/%d" % int(build.code) if build.code else ""

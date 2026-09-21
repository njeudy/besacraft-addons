from odoo import fields, models


class BesacraftBuildMember(models.Model):
    """Link between a build and a res.partner, carrying what a bare relation cannot.

    Same shape as slide.channel.partner: without this table we could only store who
    has access, not where they got to in the build -- which is the whole point of a
    layer-by-layer tutorial.
    """

    _name = "besacraft.build.member"
    _description = "Build Access"
    _table = "besacraft_build_member"
    _rec_name = "partner_id"

    build_id = fields.Many2one("besacraft.build", required=True, ondelete="cascade", index=True)
    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    member_status = fields.Selection(
        [("invited", "Invited"), ("joined", "Joined"),
         ("ongoing", "Ongoing"), ("completed", "Completed")],
        default="joined", required=True,
    )
    layer_reached = fields.Integer(default=0, help="Last layer the member reached.")
    completion = fields.Integer("% Completed", default=0, aggregator="avg")

    _sql_constraints = [
        ("build_partner_uniq", "unique(build_id, partner_id)",
         "This person already has access to this build."),
    ]

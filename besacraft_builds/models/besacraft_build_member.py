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

    def marquer_couche_faite(self, n):
        """Record layer `n` as laid, and never let the progress go backwards.

        Public on purpose: the in-game API calls it, and the manual button will too.

        The row is locked and re-read before the comparison. Two clients posting two
        layers at the same instant run in two transactions, and in READ COMMITTED both
        would otherwise read the old value and the slower writer would win -- closing
        the lock again on a layer the player had already passed. Nothing in the ORM
        prevents that, and nothing raises: the progress would simply drop.
        """
        self.ensure_one()
        self.flush_recordset()
        self.env.cr.execute(
            "SELECT layer_reached FROM besacraft_build_member WHERE id = %s FOR UPDATE",
            (self.id,))
        atteint = self.env.cr.fetchone()[0] or 0
        self.invalidate_recordset(["layer_reached"])
        if n <= atteint:
            return
        total = self.build_id.layer_count
        valeurs = {"layer_reached": n,
                   "completion": int(round(100 * n / (total or 1)))}
        if n >= total:
            valeurs["member_status"] = "completed"
        elif self.member_status == "joined":
            valeurs["member_status"] = "ongoing"
        self.write(valeurs)

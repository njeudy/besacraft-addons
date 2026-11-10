from odoo import api, fields, models


class BesacraftEpisodeAppearance(models.Model):
    """When a build shows up in an episode, so the product sheet can open the video there.

    A model of its own next to `besacraft.episode.build_ids` rather than an explicit table
    behind that Many2many: turning the existing relation into a model would mean migrating
    its table (no id column) on every database, for a timecode that most links will never
    have. `build_ids` stays the answer to "which builds are in this episode"; a moment only
    adds where, and saving one files the build in the episode if it was not already.
    """

    _name = "besacraft.episode.appearance"
    _description = "Build Appearance in an Episode"
    _order = "episode_id, minute, id"

    episode_id = fields.Many2one("besacraft.episode", required=True, ondelete="cascade",
                                 index=True)
    build_id = fields.Many2one("besacraft.build", required=True, ondelete="cascade",
                               index=True)
    # Minutes with the decimals as seconds: the float_time widget then reads and writes it
    # as mm:ss, which is how a moment is copied from the YouTube player.
    minute = fields.Float("On Screen At", help="Where the build shows up in the video, "
                                               "as minutes:seconds.")
    seconds = fields.Integer(compute="_compute_seconds")
    timecode = fields.Char(compute="_compute_seconds")

    _sql_constraints = [
        ("episode_build_uniq", "unique(episode_id, build_id)",
         "A build has one moment per episode."),
    ]

    @api.depends("minute")
    def _compute_seconds(self):
        for moment in self:
            total = max(0, round(moment.minute * 60))
            moment.seconds = total
            moment.timecode = "%d:%02d" % divmod(total, 60)

    def _ranger_le_build(self):
        for moment in self:
            if moment.build_id not in moment.episode_id.build_ids:
                moment.episode_id.build_ids = [(4, moment.build_id.id)]

    @api.model_create_multi
    def create(self, vals_list):
        moments = super().create(vals_list)
        moments._ranger_le_build()
        return moments

    def write(self, vals):
        res = super().write(vals)
        if {"episode_id", "build_id"} & set(vals):
            self._ranger_le_build()
        return res

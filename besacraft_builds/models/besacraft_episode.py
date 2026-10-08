import re

from odoo import api, fields, models

# Les quatre formes d'adresse qu'on colle depuis YouTube : l'identifiant fait toujours
# onze caractères de ce jeu-là, quel que soit le préfixe.
YOUTUBE_RE = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:[^#]*&)?v=|shorts/|embed/|live/)"
    r"|youtu\.be/)([A-Za-z0-9_-]{11})")


class BesacraftEpisode(models.Model):
    """An episode of a series, published like a blog post.

    The video itself lives on YouTube: the site only embeds it, so a visitor's browser
    talks to YouTube only once the player is asked for.
    """

    _name = "besacraft.episode"
    _description = "Series Episode"
    _inherit = ["website.published.mixin"]
    _order = "date desc, number desc, id desc"

    name = fields.Char(required=True, translate=True)
    serie_id = fields.Many2one("besacraft.serie", required=True, ondelete="cascade", index=True)
    number = fields.Integer("Episode Number")
    sequence = fields.Integer(default=10)
    date = fields.Date()
    duration_minutes = fields.Integer("Duration (min)")
    summary = fields.Text(translate=True)
    youtube_url = fields.Char("YouTube URL")
    embed_url = fields.Char(compute="_compute_embed_url")
    poster = fields.Image(max_width=1920, max_height=1920)
    build_ids = fields.Many2many(
        "besacraft.build", string="Builds Seen in the Episode",
        relation="besacraft_episode_build_rel", column1="episode_id", column2="build_id")

    @staticmethod
    def _youtube_id(url):
        """The 11-character video id of a YouTube address, or False."""
        trouve = YOUTUBE_RE.search(url or "")
        return trouve.group(1) if trouve else False

    @api.depends("youtube_url")
    def _compute_embed_url(self):
        for episode in self:
            video = self._youtube_id(episode.youtube_url)
            episode.embed_url = ("https://www.youtube-nocookie.com/embed/%s" % video
                                 if video else False)

    def _compute_website_url(self):
        super()._compute_website_url()
        for episode in self:
            episode.website_url = ("/builds/serie/%s/episodes#episode-%d"
                                   % (episode.serie_id.code, episode.id)
                                   if episode.id and episode.serie_id else "")

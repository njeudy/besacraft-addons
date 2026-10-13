from odoo.tests import HttpCase, TransactionCase, tagged

from ..models.youtube import youtube_id


@tagged("post_install", "-at_install")
class TestYoutubeId(TransactionCase):
    """Reading the id out of whatever YouTube address was pasted."""

    def test_les_cinq_formes_donnent_le_meme_identifiant(self):
        for url in (
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?list=PL1&v=dQw4w9WgXcQ&t=12",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        ):
            self.assertEqual(youtube_id(url), "dQw4w9WgXcQ", url)

    def test_une_adresse_etrangere_ne_donne_rien(self):
        """Better no link than a link out to whatever was pasted by mistake."""
        self.assertFalse(youtube_id("https://example.com/shorts/dQw4w9WgXcQ"))
        self.assertFalse(youtube_id("https://vimeo.com/123456789"))
        self.assertFalse(youtube_id(""))
        self.assertFalse(youtube_id(False))

    def test_l_episode_lit_toujours_son_identifiant(self):
        """The helper moved out of the episode model; its own reading must not change."""
        episode = self.env["besacraft.episode"].create({
            "name": "Episode", "serie_id": self.env.ref("besacraft_builds.serie_hardcore").id,
            "youtube_url": "https://youtu.be/dQw4w9WgXcQ"})
        self.assertEqual(episode.embed_url,
                         "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")


@tagged("post_install", "-at_install")
class TestSeriePlaylists(TransactionCase):
    def test_une_serie_porte_ses_deux_playlists(self):
        """Episodes and shorts do not go to the same playlist: a 60-second timelapse
        between two 20-minute episodes breaks the run."""
        serie = self.env.ref("besacraft_builds.serie_hardcore")
        serie.write({"youtube_playlist": "Les aventures de Zunk",
                     "youtube_shorts_playlist": "Un build en 60 secondes"})
        self.assertEqual(serie.youtube_playlist, "Les aventures de Zunk")
        self.assertEqual(serie.youtube_shorts_playlist, "Un build en 60 secondes")

    def test_les_playlists_ne_sont_pas_livrees_par_le_module(self):
        """They name playlists of one channel, and a module update would overwrite a name
        changed by hand -- same trap as the series names."""
        series = self.env["besacraft.serie"].search([])
        self.assertFalse(any(series.mapped("youtube_playlist")))
        self.assertFalse(any(series.mapped("youtube_shorts_playlist")))


@tagged("post_install", "-at_install")
class TestShortYoutube(HttpCase):
    def setUp(self):
        super().setUp()
        self.site = self.env.ref("website.default_website")
        self.serie = self.env.ref("besacraft_builds.serie_survie")
        self.serie.website_ids = [(4, self.site.id)]
        self.build = self.env["besacraft.build"].create({
            "name": "Build court", "code": "9931", "enroll": "public",
            "is_published": True, "serie_id": self.serie.id,
            "block_count": 80, "layer_count": 2,
            "short_video": "AAAAGGZ0eXBpc29t"})

    def test_le_champ_calcule_lit_l_adresse_collee(self):
        self.build.short_youtube_url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        self.assertEqual(self.build.short_youtube_id, "dQw4w9WgXcQ")

    def test_sans_adresse_la_page_ne_montre_aucun_lien_youtube(self):
        page = self.url_open("/builds/9931").text
        self.assertNotIn("youtube.com/shorts/", page)

    def test_la_page_renvoie_vers_le_short_publie(self):
        """The player stays local -- the link only points at the publication."""
        self.build.short_youtube_url = "https://youtu.be/dQw4w9WgXcQ"
        page = self.url_open("/builds/9931").text
        self.assertIn("https://www.youtube.com/shorts/dQw4w9WgXcQ", page)
        self.assertIn("/builds/9931/court", page, "le lecteur reste servi par Odoo")

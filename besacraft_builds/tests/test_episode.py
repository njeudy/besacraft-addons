from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEpisode(TransactionCase):
    def setUp(self):
        super().setUp()
        self.serie = self.env.ref("besacraft_builds.serie_hardcore")
        self.Episode = self.env["besacraft.episode"]

    def _episode(self, **kw):
        valeurs = {"name": "15 morts", "serie_id": self.serie.id, "number": 1}
        valeurs.update(kw)
        return self.Episode.create(valeurs)

    def test_l_adresse_d_embed_vient_de_chaque_forme_d_url(self):
        formes = (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ&t=10",
            "https://youtu.be/dQw4w9WgXcQ?si=abc",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
        )
        for url in formes:
            self.assertEqual(
                self._episode(youtube_url=url).embed_url,
                "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", url)

    def test_sans_video_pas_d_embed(self):
        self.assertFalse(self._episode().embed_url)
        self.assertFalse(self._episode(youtube_url="https://example.com/x").embed_url)

    def test_les_episodes_se_rangent_du_plus_recent_au_plus_ancien(self):
        ancien = self._episode(name="A", number=1, date="2026-01-01")
        recent = self._episode(name="B", number=2, date="2026-03-01")
        meme_jour = self._episode(name="C", number=3, date="2026-03-01")
        classes = self.Episode.search([("id", "in", (ancien | recent | meme_jour).ids)])
        self.assertEqual(classes.mapped("name"), ["C", "B", "A"])

    def test_l_url_pointe_l_ancre_de_l_episode(self):
        episode = self._episode()
        self.assertEqual(
            episode.website_url,
            "/builds/serie/hardcore/episodes#episode-%d" % episode.id)

    def test_un_episode_est_non_publie_par_defaut(self):
        episode = self._episode()
        self.assertFalse(episode.is_published)
        episode.is_published = True
        self.assertTrue(episode.is_published)

    def test_supprimer_la_serie_supprime_ses_episodes(self):
        serie = self.env["besacraft.serie"].create({
            "name": "Temp", "code": "tmp-ep", "color": "#000000", "badge_ink": "#FFFFFF"})
        episode = self._episode(serie_id=serie.id)
        serie.unlink()
        self.assertFalse(episode.exists())

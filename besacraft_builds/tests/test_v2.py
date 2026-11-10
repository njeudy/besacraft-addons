import base64
import json

from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

from .test_import import BUILD_JSON, PLAN_JSON

# Les premiers octets d'un glb : l'en-tête « glTF », version 2. Le contenu n'est pas lu.
GLB = base64.b64encode(b"glTF\x02\x00\x00\x00" + b"\x00" * 16).decode()
# Un pixel WebP valide : un champ Image refuse ce qu'il ne sait pas décoder.
WEBP = ("UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEAAwA0JaQAA3AA/vuUAAA=")


@tagged("post_install", "-at_install")
class TestRoutesV2(HttpCase):
    """The v2 routes keep the guards of the existing ones: site, site's series, published."""

    def setUp(self):
        super().setUp()
        self.site = self.env.ref("website.default_website")
        self.serie = self.env.ref("besacraft_builds.serie_survie")
        self.autre = self.env.ref("besacraft_builds.serie_hardcore")
        # Seule la série du test est publiée ici : une base de dev en coche d'autres.
        self.env["besacraft.serie"].search([]).write({"website_ids": [(3, self.site.id)]})
        self.serie.website_ids = [(4, self.site.id)]
        self.produit = self.env["product.product"].create({
            "name": "Tuto v2", "type": "service", "is_besacraft_tutorial": True,
            "list_price": 6.0, "is_published": True})
        Build = self.env["besacraft.build"]
        self.payant = Build.create({
            "name": "Navire payant", "code": "9931", "enroll": "payment",
            "product_id": self.produit.id, "is_published": True, "serie_id": self.serie.id})
        self.gratuit = Build.create({
            "name": "Moulin gratuit", "code": "9932", "enroll": "public",
            "is_published": True, "serie_id": self.serie.id})
        self.dehors = Build.create({
            "name": "Phare hors site", "code": "9933", "enroll": "payment",
            "product_id": self.produit.id, "is_published": True, "serie_id": self.autre.id})
        for build in (self.payant, self.dehors):
            build.poser_paquet({"vitrine.glb": GLB})

    def _statut(self, url):
        return self.url_open(url, allow_redirects=False).status_code

    def _retirer_la_serie(self):
        self.serie.website_ids = [(3, self.site.id)]

    # --- pages qui répondent --------------------------------------------------------------

    def test_les_collections_listent_les_builds_du_site(self):
        page = self.url_open("/builds/collections")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Navire payant", page.text)
        self.assertIn("Moulin gratuit", page.text)
        self.assertNotIn("Phare hors site", page.text)

    def test_le_shop_ne_range_que_les_builds_vendables_du_site(self):
        page = self.url_open("/builds/shop")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Navire payant", page.text)
        self.assertNotIn("Moulin gratuit", page.text, "un build gratuit ne se vend pas")
        self.assertNotIn("Phare hors site", page.text)
        self.assertIn('data-serie="%s"' % self.serie.code, page.text)

    def test_la_vitrine_sert_le_glb(self):
        reponse = self.url_open("/besacraft/vitrine/9931.glb")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.headers.get("Content-Type"), "model/gltf-binary")
        self.assertEqual(reponse.content[:4], b"glTF")

    def test_la_vitrine_d_un_build_sans_glb_est_introuvable(self):
        self.assertEqual(self._statut("/besacraft/vitrine/9932.glb"), 404)

    # --- gardes ------------------------------------------------------------------------------

    def test_un_build_hors_des_series_du_site_est_introuvable_partout(self):
        self.assertNotIn("Phare hors site", self.url_open("/builds/collections").text)
        self.assertNotIn("Phare hors site", self.url_open("/builds/shop").text)
        self.assertEqual(self._statut("/t/9933"), 404)
        self.assertEqual(self._statut("/builds/9933"), 404)
        self.assertEqual(self._statut("/besacraft/vitrine/9933.glb"), 404)

    def test_un_build_non_publie_n_a_pas_de_vitrine(self):
        self.payant.is_published = False
        self.assertEqual(self._statut("/besacraft/vitrine/9931.glb"), 404)
        self.assertNotIn("Navire payant", self.url_open("/builds/shop").text)

    def test_une_serie_non_cochee_pour_le_site_ferme_chaque_nouvelle_route(self):
        """La série du build est décochée, une autre reste publiée : le site garde un
        catalogue, mais le build n'y a plus sa place."""
        self.autre.website_ids = [(4, self.site.id)]
        self._retirer_la_serie()
        self.assertNotIn("Navire payant", self.url_open("/builds/collections").text)
        self.assertNotIn("Navire payant", self.url_open("/builds/shop").text)
        self.assertEqual(self._statut("/besacraft/vitrine/9931.glb"), 404)
        self.assertEqual(self._statut("/besacraft/vitrine/9933.glb"), 200,
                         "le témoin : la série cochée, elle, sert sa vitrine")

    def test_un_site_sans_serie_repond_404_partout(self):
        self._retirer_la_serie()
        for url in ("/builds/collections", "/builds/shop", "/besacraft/vitrine/9931.glb",
                    "/besacraft/vitrine/9933.glb", "/builds", "/t/9931"):
            self.assertEqual(self._statut(url), 404, url)


@tagged("post_install", "-at_install")
class TestPaquetV2(TransactionCase):
    """The optional files of a tutorial package: vitrine.glb, detoure.webp, face.webp,
    chapters.json."""

    def _import(self, paquet=None):
        resume = self.env["besacraft.build"].import_depuis_buildplan(
            BUILD_JSON, PLAN_JSON, "9941", "schematics", paquet=paquet)
        return self.env["besacraft.build"].browse(resume["id"])

    def test_un_paquet_sans_les_nouveaux_fichiers_s_importe(self):
        build = self._import()
        self.assertFalse(build.vitrine_glb_attachment_id)
        self.assertFalse(build.cutout_image)
        self.assertFalse(build.box_face_image)
        self.assertFalse(build.chapter_ids)
        # L'appel historique, sans l'argument, reste valable.
        self.env["besacraft.build"].import_depuis_buildplan(
            BUILD_JSON, PLAN_JSON, "9941", "schematics")

    def test_un_paquet_vide_ou_inconnu_ne_change_rien(self):
        build = self._import()
        self.assertTrue(build.poser_paquet({}))
        self.assertTrue(build.poser_paquet({"autre.txt": "eA=="}))
        self.assertFalse(build.chapter_ids)

    def test_le_paquet_complet_remplit_les_champs(self):
        chapitres = [{"title": "Fondations", "first": 1, "last": 4, "free": True},
                     {"title": "Murs", "first": 5, "last": 12}]
        build = self._import({
            "vitrine.glb": GLB, "detoure.webp": WEBP, "face.webp": WEBP,
            "chapters.json": base64.b64encode(json.dumps(chapitres).encode()).decode(),
        })
        self.assertTrue(build.cutout_image)
        self.assertTrue(build.box_face_image)
        piece = build.vitrine_glb_attachment_id
        self.assertEqual(piece.mimetype, "model/gltf-binary")
        self.assertEqual(base64.b64decode(piece.datas)[:4], b"glTF")
        self.assertEqual(build.chapter_ids.mapped("name"), ["Fondations", "Murs"])
        self.assertEqual(build.chapter_ids.mapped("free"), [True, False])
        self.assertEqual(build.chapter_ids[1].first_layer, 5)

    def test_reimporter_la_vitrine_reecrit_la_meme_piece(self):
        build = self._import({"vitrine.glb": GLB})
        piece = build.vitrine_glb_attachment_id
        autre = base64.b64encode(b"glTF\x02\x00\x00\x00autre").decode()
        build.poser_paquet({"vitrine.glb": autre})
        self.assertEqual(build.vitrine_glb_attachment_id, piece)
        self.assertEqual(base64.b64decode(piece.datas)[8:], b"autre")

    def test_un_paquet_sans_chapitres_garde_ceux_deja_poses(self):
        build = self._import({"chapters.json": [{"titre": "Toit", "debut": 1, "fin": 2}]})
        build.poser_paquet({"face.webp": WEBP})
        self.assertEqual(build.chapter_ids.mapped("name"), ["Toit"])

    def test_chapters_json_remplace_les_chapitres(self):
        build = self._import({"chapters.json": [{"title": "A"}, {"title": "B"}]})
        build.poser_paquet({"chapters.json": {"chapters": [{"title": "C"}]}})
        self.assertEqual(build.chapter_ids.mapped("name"), ["C"])

    def test_un_chapters_json_illisible_est_refuse(self):
        build = self._import()
        with self.assertRaises(ValidationError):
            build.poser_paquet({"chapters.json": base64.b64encode(b"{pas du json").decode()})
        with self.assertRaises(ValidationError):
            build.poser_paquet({"chapters.json": [{"first": 1}]})


@tagged("post_install", "-at_install")
class TestChapitres(TransactionCase):
    def setUp(self):
        super().setUp()
        self.build = self.env["besacraft.build"].create({
            "name": "Chapitré", "code": "9951",
            "serie_id": self.env.ref("besacraft_builds.serie_survie").id})

    def test_les_chapitres_sont_ordonnes_par_sequence(self):
        Chapitre = self.env["besacraft.build.chapter"]
        for sequence, nom in ((30, "Toit"), (10, "Fondations"), (20, "Murs")):
            Chapitre.create({"build_id": self.build.id, "sequence": sequence, "name": nom})
        # Le cache du One2many garde l'ordre des créations : relire la base, comme la page.
        self.build.invalidate_recordset(["chapter_ids"])
        self.assertEqual(self.build.chapter_ids.mapped("name"),
                         ["Fondations", "Murs", "Toit"])

    def test_un_chapitre_ne_finit_pas_avant_de_commencer(self):
        with self.assertRaises(ValidationError):
            self.env["besacraft.build.chapter"].create({
                "build_id": self.build.id, "name": "Envers",
                "first_layer": 8, "last_layer": 3})

    def test_les_chapitres_partent_avec_le_build(self):
        chapitre = self.env["besacraft.build.chapter"].create({
            "build_id": self.build.id, "name": "Seul"})
        self.build.unlink()
        self.assertFalse(chapitre.exists())

import base64
import hashlib
import io
import json
import zipfile

from PIL import Image

from odoo.addons.besacraft_minecraft_api.controllers import base
from odoo.addons.besacraft_vestiaire.tools import paquet
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, common, tagged

CODE = "echarpe_test"


def png(largeur=32, hauteur=32, couleur=(200, 30, 30, 255)):
    tampon = io.BytesIO()
    Image.new("RGBA", (largeur, hauteur), couleur).save(tampon, format="PNG")
    return tampon.getvalue()


def entree(**en_plus):
    valeur = {"id": CODE, "nom": "Écharpe d'essai", "emplacement": "cape", "accroches": ["body"],
              "declencheurs": [{"type": "IDLE", "animation": f"animation.{CODE}.idle"}],
              "variantes": [{"id": "rouge", "nom": "Rouge"}, {"id": "bleu", "nom": "Bleu"}]}
    valeur.update(en_plus)
    return valeur


def fichiers(**remplacer):
    contenu = {
        "cosmetique.json": json.dumps(entree()).encode(),
        f"geo/cosmetique/{CODE}.geo.json": json.dumps({
            "format_version": "1.12.0",
            "minecraft:geometry": [{"description": {"identifier": f"geometry.{CODE}"}, "bones": []}]}).encode(),
        f"animations/cosmetique/{CODE}.animation.json": json.dumps({
            "format_version": "1.8.0",
            "animations": {f"animation.{CODE}.idle": {"loop": True, "bones": {}}}}).encode(),
        f"textures/cosmetique/{CODE}.png": png(),
        f"textures/cosmetique/{CODE}__bleu.png": png(couleur=(30, 30, 200, 255)),
        f"textures/cosmetique/{CODE}_glowmask.png": png(couleur=(0, 0, 0, 0)),
    }
    contenu.update(remplacer)
    return {k: v for k, v in contenu.items() if v is not None}


def archive(contenu=None):
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        for chemin, octets in (contenu if contenu is not None else fichiers()).items():
            z.writestr(chemin, octets)
    return tampon.getvalue()


class TestPaquet(TransactionCase):

    def test_paquet_valide(self):
        lue, contenu = paquet.lire(self.env, archive(), CODE)
        self.assertEqual(lue["id"], CODE)
        self.assertEqual(len(contenu), 6)

    def _refuse(self, octets, code=CODE):
        with self.assertRaises(ValidationError):
            paquet.lire(self.env, octets, code)

    def test_pas_un_zip(self):
        self._refuse(b"PK pas vraiment")

    def test_aucun_code(self):
        self._refuse(archive(fichiers(**{"script.py": b"print(1)"})))
        self._refuse(archive(fichiers(**{"../evil.json": b"{}"})))
        self._refuse(archive(fichiers(**{f"geo/cosmetique/{CODE}.class": b"\xca\xfe"})))

    def test_id_incoherent(self):
        self._refuse(archive(), code="autre_id")
        self._refuse(archive(fichiers(**{"cosmetique.json": json.dumps(entree(id="autre")).encode()})))

    def test_json_invalide(self):
        self._refuse(archive(fichiers(**{f"geo/cosmetique/{CODE}.geo.json": b"{pas du json"})))
        self._refuse(archive(fichiers(**{"cosmetique.json": b"[]"})))

    def test_png_obligatoire_et_borne(self):
        self._refuse(archive(fichiers(**{f"textures/cosmetique/{CODE}.png": b"GIF89a"})))
        self._refuse(archive(fichiers(**{f"textures/cosmetique/{CODE}.png": png(1024, 16)})))
        self._refuse(archive(fichiers(**{f"textures/cosmetique/{CODE}.png": None})))

    def test_variantes_coherentes(self):
        self._refuse(archive(fichiers(**{f"textures/cosmetique/{CODE}__bleu.png": None})))
        self._refuse(archive(fichiers(**{f"textures/cosmetique/{CODE}__vert.png": png()})))
        self._refuse(archive(fichiers(**{f"textures/cosmetique/{CODE}__vert_glowmask.png": png()})))

    def test_declencheur_sans_animation(self):
        e = entree(declencheurs=[{"type": "IDLE", "animation": "animation.absente"}])
        self._refuse(archive(fichiers(**{"cosmetique.json": json.dumps(e).encode()})))

    def test_effet_et_emplacement_inconnu(self):
        for e in (entree(emplacement="effet"), entree(emplacement="nulle_part"), entree(accroches=["pied"])):
            self._refuse(archive(fichiers(**{"cosmetique.json": json.dumps(e).encode()})))

    def test_trop_de_fichiers(self):
        trop = fichiers(**{f"textures/cosmetique/{CODE}__v{i}.png": png(1, 1) for i in range(40)})
        self._refuse(archive(trop))

    def test_bombe(self):
        gros = json.dumps({"x": "a" * (paquet.DECOMPRESSE_MAX + 10)}).encode()
        self._refuse(archive(fichiers(**{"cosmetique.json": gros})))


class TestDepot(TransactionCase):

    def setUp(self):
        super().setUp()
        self.echarpe = self.env["besacraft.vestiaire.cosmetique"].create({"code": CODE, "name": "Scarf"})

    def test_depot_puis_nouvelle_version(self):
        self.echarpe.paquet = base64.b64encode(archive())
        self.assertTrue(self.echarpe.distant)
        self.assertEqual(self.echarpe.version_distante, 1)
        self.assertEqual(self.echarpe.emplacement, "cape")
        self.assertEqual(len(self.echarpe.fichier_ids), 5)
        texture = self.echarpe.fichier_ids.filtered(lambda f: f.chemin.endswith(f"{CODE}.png"))
        self.assertEqual(texture.sha256, hashlib.sha256(png()).hexdigest())
        self.assertEqual(texture.taille, len(png()))
        self.echarpe.paquet = base64.b64encode(archive(fichiers(
            **{f"textures/cosmetique/{CODE}_glowmask.png": None})))
        self.assertEqual(self.echarpe.version_distante, 2)
        self.assertEqual(len(self.echarpe.fichier_ids), 4)

    def test_depot_refuse_ne_change_rien(self):
        self.echarpe.paquet = base64.b64encode(archive())
        with self.assertRaises(ValidationError):
            self.echarpe.paquet = base64.b64encode(b"pas un zip")
        self.assertEqual(self.echarpe.version_distante, 1)

    def test_emplacements_du_mod(self):
        """Clothes, glasses and slung items of the mod's catalogue can be remote too."""
        for emplacement in ("torse", "taille", "visage", "bandouliere"):
            lue, _ = paquet.lire(self.env, archive(fichiers(**{"cosmetique.json": json.dumps(
                entree(emplacement=emplacement)).encode()})), CODE)
            self.assertEqual(lue["emplacement"], emplacement)

    def test_cheveux_et_barbe(self):
        for emplacement in ("cheveux", "barbe"):
            lue, _ = paquet.lire(self.env, archive(fichiers(**{"cosmetique.json": json.dumps(
                entree(emplacement=emplacement)).encode()})), CODE)
            self.assertEqual(lue["emplacement"], emplacement)

    def _teintable(self, teintes, **calques):
        contenu = {f"textures/cosmetique/{CODE}__bleu.png": None,
                   f"textures/cosmetique/{CODE}__principale.png": png(couleur=(170, 170, 170, 255))}
        contenu.update(calques)
        e = entree(emplacement="barbe", teintes=teintes)
        e.pop("variantes")
        contenu["cosmetique.json"] = json.dumps(e).encode()
        return archive(fichiers(**contenu))

    TEINTES = {"principale": [{"id": "noir", "nom": "Noir", "couleur": "#1F1B1A"},
                              {"id": "blanc", "nom": "Blanc", "couleur": "#EDEBE4"}],
               "secondaire": [{"id": "x", "couleur": "#000000"}],
               "lumineuse": [{"id": "x", "couleur": "#000000"}],
               "tailles": [{"id": "courte", "nom": "Courte"}, {"id": "longue", "nom": "Longue"}],
               "zones": ["Poils", "-", "-"]}

    def test_teintes_distantes(self):
        """A remote cosmetic can be tinted: its grey layers come with it, sizes included."""
        lue, contenu = paquet.lire(self.env, self._teintable(self.TEINTES, **{
            f"textures/cosmetique/{CODE}__reflets.png": png(couleur=(0, 0, 0, 0))}), CODE)
        self.assertEqual(lue["teintes"]["tailles"][1]["id"], "longue")
        self.assertIn(f"textures/cosmetique/{CODE}__reflets.png", contenu)

    def test_teintes_refusees(self):
        sans_calque = self._teintable(self.TEINTES, **{f"textures/cosmetique/{CODE}__principale.png": None})
        self._refuse_lire(sans_calque)
        mauvaise = dict(self.TEINTES, principale=[{"id": "noir", "couleur": "noir"}])
        self._refuse_lire(self._teintable(mauvaise))
        double = dict(self.TEINTES, tailles=[{"id": "a"}, {"id": "a"}])
        self._refuse_lire(self._teintable(double))
        self._refuse_lire(self._teintable(self.TEINTES, **{
            f"textures/cosmetique/{CODE}__bleu.png": png()}))

    def _refuse_lire(self, octets):
        with self.assertRaises(ValidationError):
            paquet.lire(self.env, octets, CODE)

    def test_piece_armure_distante(self):
        e = entree(emplacement="tete", armure={"piece": "casque", "deploiement": "pieces"})
        self.echarpe.paquet = base64.b64encode(archive(fichiers(**{"cosmetique.json": json.dumps(e).encode()})))
        self.assertEqual(self.echarpe.piece_armure, "casque")
        self.echarpe.paquet = base64.b64encode(archive())
        self.assertFalse(self.echarpe.piece_armure)

    def test_emote_jamais_distante(self):
        self.echarpe.genre = "emote"
        with self.assertRaises(ValidationError):
            self.echarpe.paquet = base64.b64encode(archive())

    def test_emplacement_different(self):
        self.echarpe.emplacement = "chapeau"
        with self.assertRaises(ValidationError):
            self.echarpe.paquet = base64.b64encode(archive())

    def test_retirer(self):
        self.echarpe.paquet = base64.b64encode(archive())
        self.echarpe.action_retirer_paquet()
        self.assertFalse(self.echarpe.distant)
        self.assertFalse(self.echarpe.fichier_ids)
        self.assertNotIn(self.echarpe, self.env["besacraft.vestiaire.cosmetique"]._distants_servis())


@tagged("post_install", "-at_install")
class TestApiDistant(common.HttpCase):

    def setUp(self):
        super().setUp()
        base._passages.clear()
        self.addCleanup(base._passages.clear)
        self.zoe = self.env["res.partner"].create({
            "name": "Zoé", "minecraft_login": "joueuressai",
            "minecraft_uuid": "5e1f0a2b7c3d4e8f9a6b1c2d3e4f5a6b"})
        self.jeton = self.env["besacraft.mc.session"]._ouvrir(self.zoe).token
        cle = self.env["besacraft.vestiaire.cle.serveur"].create({"name": "Essai"})
        self.cle = cle._generer()
        Cosmetique = self.env["besacraft.vestiaire.cosmetique"]
        self.echarpe = Cosmetique.create({"code": CODE, "name": "Scarf"})
        self.echarpe.paquet = base64.b64encode(archive())
        self.cache = Cosmetique.create({"code": "echarpe_cachee", "name": "Hidden", "publie": False})

    def _get(self, chemin, jeton):
        headers = {"Authorization": "Bearer %s" % jeton} if jeton else {}
        return self.url_open(chemin, headers=headers, timeout=30)

    def test_sans_jeton(self):
        self.assertEqual(self._get("/mc/v1/vestiaire/distants", None).status_code, 401)
        self.assertEqual(self._get("/mc/v1/vestiaire/distants", "faux").status_code, 401)

    def test_manifeste_puis_telechargement(self):
        for jeton in (self.jeton, self.cle):
            r = self._get("/mc/v1/vestiaire/distants", jeton)
            self.assertEqual(r.status_code, 200)
            corps = r.json()
            self.assertEqual(corps["format"], 1)
            self.assertEqual([c["code"] for c in corps["cosmetiques"]], [CODE])
            echarpe = corps["cosmetiques"][0]
            self.assertEqual(echarpe["version"], 1)
            self.assertEqual(echarpe["entree"]["version"], 1)
            self.assertEqual(echarpe["entree"]["emplacement"], "cape")
            attendus = {c: v for c, v in fichiers().items() if c != "cosmetique.json"}
            self.assertEqual({f["chemin"] for f in echarpe["fichiers"]}, set(attendus))
            for f in echarpe["fichiers"]:
                telecharge = self._get("/mc/v1/vestiaire/fichier/%s" % f["sha256"], jeton)
                self.assertEqual(telecharge.status_code, 200)
                self.assertEqual(telecharge.content, attendus[f["chemin"]])
                self.assertEqual(hashlib.sha256(telecharge.content).hexdigest(), f["sha256"])
                self.assertEqual(len(telecharge.content), f["taille"])

    def test_fichier_inconnu_ou_mal_forme(self):
        self.assertEqual(self._get("/mc/v1/vestiaire/fichier/%s" % ("0" * 64), self.jeton).status_code, 404)
        self.assertEqual(self._get("/mc/v1/vestiaire/fichier/xyz", self.jeton).status_code, 400)

    def test_non_publie_jamais_servi(self):
        self.echarpe.publie = False
        self.assertEqual(self._get("/mc/v1/vestiaire/distants", self.jeton).json()["cosmetiques"], [])
        sha = self.echarpe.fichier_ids[0].sha256
        self.assertEqual(self._get("/mc/v1/vestiaire/fichier/%s" % sha, self.jeton).status_code, 404)

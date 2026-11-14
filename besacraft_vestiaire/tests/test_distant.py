import base64
import hashlib
import io
import json
import zipfile

from PIL import Image

from odoo.addons.besacraft_vestiaire.tools import paquet
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase

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


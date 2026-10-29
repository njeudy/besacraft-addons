import io
import struct
import zlib

from PIL import Image

from odoo.addons.besacraft_vestiaire.tools import images
from odoo.exceptions import ValidationError
from odoo.tests import BaseCase


def png(largeur, hauteur):
    tampon = io.BytesIO()
    Image.new("RGBA", (largeur, hauteur)).save(tampon, format="PNG")
    return tampon.getvalue()


class TestImages(BaseCase):
    def test_skins_acceptes(self):
        images.verifier_skin(png(64, 64))
        images.verifier_skin(png(64, 32))

    def test_skin_mal_dimensionne(self):
        with self.assertRaises(ValidationError):
            images.verifier_skin(png(128, 128))

    def test_pas_un_png(self):
        with self.assertRaises(ValidationError):
            images.verifier_skin(b"GIF89a pas un png")
        tampon = io.BytesIO()
        Image.new("RGB", (64, 64)).save(tampon, format="JPEG")
        with self.assertRaises(ValidationError):
            images.verifier_skin(tampon.getvalue())

    def test_trop_lourd(self):
        with self.assertRaises(ValidationError):
            images.verifier_skin(png(64, 64) + b"\0" * (1024 * 1024))

    def test_capes(self):
        images.verifier_cape(png(64, 32))
        images.verifier_cape(png(128, 64))
        with self.assertRaises(ValidationError):
            images.verifier_cape(png(64, 64))
        with self.assertRaises(ValidationError):
            images.verifier_cape(png(96, 48))

    def test_empreinte_stable(self):
        self.assertEqual(images.empreinte(b"abc"), images.empreinte(b"abc"))
        self.assertRegex(images.empreinte(b"abc"), r"^[0-9a-f]{64}$")

    def test_bombe_de_decompression(self):
        def chunk(kind, body):
            return (struct.pack(">I", len(body)) + kind + body
                    + struct.pack(">I", zlib.crc32(kind + body)))
        data = (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", 100000, 100000, 8, 6, 0, 0, 0))
                + chunk(b"IEND", b""))
        with self.assertRaises(ValidationError):
            images.verifier_skin(data)

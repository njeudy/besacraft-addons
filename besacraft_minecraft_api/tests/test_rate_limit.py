from odoo.addons.besacraft_minecraft_api.controllers import base
from odoo.tests import common, tagged

JSON = {"Content-Type": "application/json"}


@tagged("post_install", "-at_install")
class TestRateLimit(common.HttpCase):
    def setUp(self):
        super().setUp()
        # Le compteur vit en mémoire du worker, donc d'un test à l'autre : sans ce
        # nettoyage, l'ordre d'exécution des classes déciderait du résultat.
        base._passages.clear()
        self.addCleanup(base._passages.clear)

    def _defi(self):
        return self.url_open("/mc/v1/defi", data="{}", headers=JSON).status_code

    def test_le_quota_ne_bloque_pas_un_usage_normal(self):
        self.assertEqual({self._defi() for _ in range(5)}, {200})

    def test_trop_de_defis_depuis_la_meme_ip(self):
        """An open endpoint on the production host needs a ceiling from day one."""
        self.assertIn(429, [self._defi() for _ in range(40)])

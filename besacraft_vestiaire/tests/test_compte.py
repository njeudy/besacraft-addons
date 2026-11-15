from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCompte(TransactionCase):
    def setUp(self):
        super().setUp()
        self.zoe = self.env["res.partner"].create({
            "name": "Zoé", "email": "zoe@example.org",
            "minecraft_uuid": "5e1f0a2b7c3d4e8f9a6b1c2d3e4f5a6b",
            "minecraft_login": "joueuressai"})

    def test_un_contact_sans_utilisateur_n_est_pas_valide(self):
        self.assertFalse(self.zoe._vestiaire_valide())

    def test_un_contact_avec_un_utilisateur_portail_est_valide(self):
        self.env["res.users"].create({
            "name": "Zoé", "login": "zoe@example.org", "partner_id": self.zoe.id,
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})
        self.assertTrue(self.zoe._vestiaire_valide())

    def test_un_utilisateur_archive_ne_valide_plus(self):
        user = self.env["res.users"].create({
            "name": "Zoé", "login": "zoe@example.org", "partner_id": self.zoe.id,
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])]})
        user.active = False
        self.zoe.invalidate_recordset()
        self.assertFalse(self.zoe._vestiaire_valide())

    def test_sans_uuid_pas_de_compte_vestiaire(self):
        self.zoe.minecraft_uuid = False
        self.assertFalse(self.zoe._vestiaire_valide())

    def test_retrouver_par_uuid_avec_tirets(self):
        trouve = self.env["res.partner"]._vestiaire_par_uuid(
            "5E1F0A2B-7C3D-4E8F-9A6B-1C2D3E4F5A6B")
        self.assertEqual(trouve, self.zoe)

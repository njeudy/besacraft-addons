from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, common, tagged

UUID = "cc67e9f6625340d4813855e5fecc4c10"


@tagged("post_install", "-at_install")
class TestDemande(TransactionCase):
    def setUp(self):
        super().setUp()
        self.code = self.env["besacraft.vestiaire.code"]._emettre(UUID, "zoejeudy")
        self.Demande = self.env["besacraft.vestiaire.demande"]
        self.valeurs = {"prenom": "Zoé", "email": "zoe@example.org",
                        "moins_de_15": False, "email_parent": ""}

    def test_la_demande_porte_l_uuid_du_code(self):
        demande = self.Demande._soumettre(self.code.code, self.valeurs)
        self.assertEqual(demande.uuid, UUID)
        self.assertEqual(demande.pseudo, "zoejeudy")
        self.assertEqual(demande.state, "a_valider")

    def test_moins_de_15_ans_exige_un_parent(self):
        with self.assertRaises(ValidationError):
            self.Demande._soumettre(self.code.code, dict(self.valeurs, moins_de_15=True))

    def test_une_seconde_demande_met_a_jour_la_premiere(self):
        premiere = self.Demande._soumettre(self.code.code, self.valeurs)
        seconde = self.Demande._soumettre(self.code.code, dict(self.valeurs, prenom="Zo"))
        self.assertEqual(premiere, seconde)
        self.assertEqual(seconde.prenom, "Zo")
        self.assertEqual(self.Demande.search_count([("uuid", "=", UUID)]), 1)

    def test_un_code_expire_est_refuse(self):
        self.code.unlink()
        with self.assertRaises(ValidationError):
            self.Demande._soumettre("perime000000", self.valeurs)

    def test_valider_reutilise_le_contact_qui_a_l_uuid(self):
        zoe = self.env["res.partner"].create({"name": "Zoé J", "minecraft_uuid": UUID})
        demande = self.Demande._soumettre(self.code.code, self.valeurs)
        demande.action_valider()
        self.assertEqual(demande.partner_id, zoe)
        self.assertTrue(zoe.user_ids)
        self.assertTrue(zoe._vestiaire_valide())

    def test_valider_reutilise_le_contact_qui_a_l_email(self):
        zoe = self.env["res.partner"].create({"name": "Zoé J", "email": "zoe@example.org"})
        demande = self.Demande._soumettre(self.code.code, self.valeurs)
        demande.action_valider()
        self.assertEqual(demande.partner_id, zoe)
        self.assertEqual(zoe.minecraft_uuid, UUID)
        self.assertEqual(zoe.minecraft_login, "zoejeudy")

    def test_valider_cree_un_contact_sinon(self):
        demande = self.Demande._soumettre(self.code.code, dict(
            self.valeurs, moins_de_15=True, email_parent="parent@example.org"))
        demande.action_valider()
        self.assertEqual(demande.state, "validee")
        self.assertEqual(demande.partner_id.vestiaire_parent_email, "parent@example.org")
        self.assertTrue(demande.partner_id._vestiaire_valide())

    def test_refuser_ferme_la_demande(self):
        demande = self.Demande._soumettre(self.code.code, self.valeurs)
        demande.message_refus = "Je ne te connais pas."
        demande.action_refuser()
        self.assertEqual(demande.state, "refusee")
        self.assertFalse(demande.partner_id)


@tagged("post_install", "-at_install")
class TestPageDemande(common.HttpCase):
    def test_un_lien_perime_le_dit(self):
        page = self.url_open("/vestiaire/demande?code=perime000000")
        self.assertEqual(page.status_code, 200)
        self.assertIn("expired", page.text)

    def test_un_lien_valide_montre_le_pseudo(self):
        code = self.env["besacraft.vestiaire.code"]._emettre(UUID, "zoejeudy")
        page = self.url_open("/vestiaire/demande?code=%s" % code.code)
        self.assertIn("zoejeudy", page.text)

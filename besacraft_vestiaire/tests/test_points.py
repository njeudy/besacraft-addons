from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import common, tagged
from odoo.tools import mute_logger

from ..models.res_partner import AchatRefuse


class PointsCommon(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Cosmetique = cls.env["besacraft.vestiaire.cosmetique"]
        # The v50 seed makes everything owned by everyone: start from a clean shelf.
        Cosmetique.search([]).write({"de_base": False})
        cls.zoe = cls.env["res.partner"].create({
            "name": "Zoé", "minecraft_login": "zoejeudy",
            "minecraft_uuid": "cc67e9f6625340d4813855e5fecc4c10"})
        cls.env["res.users"].create({
            "name": "Zoé", "login": "zoe-points", "partner_id": cls.zoe.id,
            "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])]})
        cls.chapeau = Cosmetique.create({"code": "t_chapeau", "name": "Hat", "genre": "cosmetique",
                                         "emplacement": "chapeau", "prix": 100})
        cls.tete = Cosmetique.create({"code": "t_tete", "name": "Cat head", "genre": "cosmetique",
                                      "emplacement": "tete", "de_base": True})
        cls.ailes = Cosmetique.create({"code": "t_ailes", "name": "Wings", "genre": "cosmetique",
                                       "emplacement": "ailes", "de_base": True})
        cls.ailes2 = Cosmetique.create({"code": "t_ailes2", "name": "Wings 2",
                                        "genre": "cosmetique", "emplacement": "ailes",
                                        "de_base": True})
        cls.salut = Cosmetique.create({"code": "t_salut", "name": "Wave", "genre": "emote",
                                       "de_base": True})
        cls.guitare = Cosmetique.create({"code": "t_guitare", "name": "Guitar", "genre": "emote",
                                         "prix": 50})


@tagged("post_install", "-at_install")
class TestPoints(PointsCommon):

    def test_amorcage_v50(self):
        seed = self.env.ref("besacraft_vestiaire.emote_bow1")
        self.assertEqual(seed.genre, "emote")
        Cosmetique = self.env["besacraft.vestiaire.cosmetique"]
        self.assertFalse(Cosmetique.search_count([("code", "=", "guitare_electrique_objet")]),
                         "emote props are not sold on their own")

    def test_solde_et_unicite_du_gain(self):
        self.zoe._vestiaire_crediter(30, "mission", "Le pont", "ep1:pont")
        self.assertFalse(self.zoe._vestiaire_crediter(30, "mission", "Le pont", "ep1:pont"))
        self.zoe._vestiaire_crediter(5, "cadeau", "Bravo")
        self.zoe._vestiaire_crediter(5, "cadeau", "Bravo encore")
        self.assertEqual(self.zoe.vestiaire_points, 40)

    def test_mouvement_ni_modifie_ni_supprime(self):
        mouvement = self.zoe._vestiaire_crediter(10, "cadeau", "Bravo")
        with self.assertRaises(UserError):
            mouvement.points = 1000
        with self.assertRaises(UserError):
            mouvement.unlink()
        mouvement.annonce = True

    def test_bareme(self):
        Bareme = self.env["besacraft.vestiaire.bareme"]
        Bareme.create({"motif": "mission", "points": 10})
        Bareme.create({"motif": "mission", "code": "boss", "points": 50, "name": "Boss"})
        self.assertEqual(self.zoe._vestiaire_gagner("mission", "ep1:a"), (10, False))
        self.assertEqual(self.zoe._vestiaire_gagner("mission", "ep1:b", "boss"), (50, False))
        self.assertEqual(self.zoe._vestiaire_gagner("mission", "ep1:b", "boss"), (50, True))
        self.assertEqual(self.zoe.vestiaire_points, 60)
        with self.assertRaises(KeyError):
            self.zoe._vestiaire_gagner("defi", "d1")

    def test_possede(self):
        possede = self.zoe._vestiaire_possede()
        self.assertIn(self.tete, possede)
        self.assertNotIn(self.chapeau, possede)
        self.tete.publie = False
        self.assertNotIn(self.tete, self.zoe._vestiaire_possede())
        self.zoe._vestiaire_offrir_cosmetique(self.guitare)
        self.assertIn(self.guitare, self.zoe._vestiaire_possede())

    def test_achat(self):
        self.zoe._vestiaire_crediter(120, "cadeau", "Bravo")
        self.assertEqual(self.zoe._vestiaire_acheter("t_chapeau", 100), 20)
        self.assertIn(self.chapeau, self.zoe._vestiaire_possede())
        self.assertEqual(self.zoe.vestiaire_points, 20)
        achat = self.zoe.vestiaire_mouvement_ids.filtered(lambda m: m.motif == "achat")
        self.assertEqual((achat.points, achat.cosmetique_id), (-100, self.chapeau))
        with self.assertRaises(AchatRefuse) as refus:
            self.zoe._vestiaire_acheter("t_chapeau", 100)
        self.assertEqual(refus.exception.erreur, "deja_possede")

    def test_achat_refuse(self):
        self.zoe._vestiaire_crediter(30, "cadeau", "Bravo")
        for code, prix, erreur in [("t_chapeau", 100, "solde_insuffisant"),
                                   ("t_chapeau", 80, "prix_change"),
                                   ("t_tete", 0, "inconnu"),
                                   ("nexiste_pas", 10, "inconnu")]:
            with self.assertRaises(AchatRefuse) as refus:
                self.zoe._vestiaire_acheter(code, prix)
            self.assertEqual(refus.exception.erreur, erreur, code)
        self.assertEqual(self.zoe.vestiaire_points, 30)
        self.chapeau.publie = False
        with self.assertRaises(AchatRefuse):
            self.zoe._vestiaire_acheter("t_chapeau", 100)

    def test_equiper(self):
        garde = self.zoe._vestiaire_equiper(
            ["t_tete", "t_chapeau", "t_ailes", "t_ailes2", "t_salut", 42],
            ["t_salut", "t_guitare", None, "t_salut", "t_tete", None, None, None, "t_salut"])
        self.assertEqual(garde["tenue"], ["t_tete", "t_ailes"])
        self.assertEqual(garde["roue"], ["t_salut", None, None, None, None, None, None, None])
        self.assertEqual(self.zoe._vestiaire_tenue(), self.tete | self.ailes)
        self.assertEqual(self.zoe._vestiaire_roue()[0], "t_salut")

    def test_tete_et_chapeau_exclusifs(self):
        self.zoe._vestiaire_offrir_cosmetique(self.chapeau)
        garde = self.zoe._vestiaire_equiper(["t_chapeau", "t_tete"], [])
        self.assertEqual(garde["tenue"], ["t_chapeau"])

    def test_objet_perdu_sort_de_la_tenue(self):
        self.zoe._vestiaire_equiper(["t_ailes"], ["t_salut"])
        self.ailes.de_base = False
        self.salut.de_base = False
        self.assertFalse(self.zoe._vestiaire_tenue())
        self.assertEqual(self.zoe._vestiaire_roue(), [None] * 8)

    def test_possession_retiree_range_la_tenue(self):
        self.zoe._vestiaire_offrir_cosmetique(self.chapeau)
        self.zoe._vestiaire_equiper(["t_chapeau"], [])
        self.zoe.vestiaire_possession_ids.filtered("cosmetique_id").unlink()
        self.assertFalse(self.zoe.vestiaire_tenue_ids)

    @mute_logger("odoo.sql_db")
    def test_possession_cape_ou_cosmetique(self):
        with self.assertRaises(IntegrityError):
            self.env["besacraft.vestiaire.possession"].create(
                {"partner_id": self.zoe.id, "origine": "offert"})
            self.env.flush_all()

    def test_nouvelles_annoncees_une_fois(self):
        self.zoe._vestiaire_crediter(50, "cadeau", "Bravo pour le pont")
        self.zoe._vestiaire_offrir_cosmetique(self.guitare)
        self.zoe._vestiaire_crediter(20, "cadeau", "x")
        nouvelles = self.zoe._vestiaire_nouvelles()
        self.assertEqual([n["points"] for n in nouvelles], [50, 20, 0])
        self.assertEqual(nouvelles[2]["code"], "t_guitare")
        self.assertEqual(self.zoe._vestiaire_nouvelles(), [])

    def test_assistant_offrir(self):
        Offrir = self.env["besacraft.vestiaire.offrir"]
        Offrir.create({"partner_ids": [(6, 0, self.zoe.ids)], "quoi": "points", "points": 25,
                       "libelle": "Merci"}).action_offrir()
        Offrir.create({"partner_ids": [(6, 0, self.zoe.ids)], "quoi": "cosmetique",
                       "cosmetique_id": self.guitare.id}).action_offrir()
        self.assertEqual(self.zoe.vestiaire_points, 25)
        self.assertIn(self.guitare, self.zoe._vestiaire_possede())
        with self.assertRaises(UserError):
            Offrir.create({"partner_ids": [(6, 0, self.zoe.ids)], "quoi": "points",
                           "points": 0}).action_offrir()

    def test_cle_serveur(self):
        Cle = self.env["besacraft.vestiaire.cle.serveur"]
        cle = Cle.create({"name": "zunk"})
        secret = cle._generer()
        self.assertEqual(Cle._par_cle(secret), cle)
        self.assertNotEqual(cle.cle_hash, secret)
        self.assertFalse(Cle._par_cle("faux"))
        cle.active = False
        self.assertFalse(Cle._par_cle(secret))

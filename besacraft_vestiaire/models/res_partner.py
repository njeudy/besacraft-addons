import base64
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import mojang

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    vestiaire_parent_email = fields.Char(string="Parent email")
    vestiaire_skin_ids = fields.One2many("besacraft.vestiaire.skin", "partner_id", string="Skins")
    vestiaire_possession_ids = fields.One2many("besacraft.vestiaire.possession", "partner_id",
                                               string="Owned items")
    vestiaire_cape_id = fields.Many2one("besacraft.vestiaire.cape", string="Worn cape")

    @api.constrains("vestiaire_cape_id")
    def _check_cape_possedee(self):
        for partner in self:
            if partner.vestiaire_cape_id and partner.vestiaire_cape_id not in partner._vestiaire_capes():
                raise ValidationError(_("You can only wear a cape you own."))

    def _vestiaire_capes(self):
        self.ensure_one()
        # Ownership is admin-only data; the wear check must work for the player too.
        return self.sudo().vestiaire_possession_ids.cape_id

    def _vestiaire_offrir_cape(self, cape):
        for partner in self:
            if cape not in partner._vestiaire_capes():
                self.env["besacraft.vestiaire.possession"].create(
                    {"partner_id": partner.id, "cape_id": cape.id, "origine": "offert"})

    def _vestiaire_valide(self):
        """A wardrobe account is a contact with a Minecraft UUID and an active user."""
        self.ensure_one()
        return bool(self.minecraft_uuid) and bool(self.user_ids)

    @api.model
    def _vestiaire_par_uuid(self, uuid):
        uuid = self.normaliser_uuid_minecraft(uuid)
        if not uuid:
            return self.browse()
        return self.search([("minecraft_uuid", "=", uuid)], limit=1)

    def _vestiaire_skin_actif(self):
        self.ensure_one()
        return self.vestiaire_skin_ids.filtered("actif")[:1]

    def _vestiaire_importer_skin_mojang(self):
        """Seed a first skin from Mojang for valid accounts that have none. Re-runnable."""
        crees = 0
        for partner in self.filtered(lambda p: p._vestiaire_valide() and not p.vestiaire_skin_ids):
            texture = mojang.texture_skin(partner.minecraft_uuid)
            if not texture:
                continue
            data, modele = texture
            try:
                with self.env.cr.savepoint():
                    self.env["besacraft.vestiaire.skin"].create({
                        "partner_id": partner.id, "name": "Mojang",
                        "image": base64.b64encode(data), "modele": modele, "actif": True})
            except ValidationError as erreur:
                _logger.warning("Mojang skin of %s refused: %s", partner.minecraft_login, erreur)
                continue
            crees += 1
        return crees

    def action_vestiaire_importer_skin_mojang(self):
        self._vestiaire_importer_skin_mojang()
        return True

    @api.model
    def _vestiaire_cron_importer_skins(self):
        self.search([("minecraft_uuid", "!=", False), ("user_ids", "!=", False),
                     ("vestiaire_skin_ids", "=", False)])._vestiaire_importer_skin_mojang()


class AchatRefuse(Exception):
    """A purchase the game must explain to the player; `erreur` is the API code."""

    def __init__(self, erreur, **details):
        super().__init__(erreur)
        self.erreur = erreur
        self.details = details


# Slots that cannot be worn together, both ways: a whole head does not fit under a hat.
INCOMPATIBLES = {"tete": {"chapeau"}, "chapeau": {"tete"}}
# Longest settings suffix kept after a code; the game never writes more than 64 characters.
REGLAGE_MAX = 60


class ResPartnerPoints(models.Model):
    _inherit = "res.partner"

    vestiaire_mouvement_ids = fields.One2many("besacraft.vestiaire.mouvement", "partner_id",
                                              string="Points movements")
    vestiaire_points = fields.Integer(string="Points", compute="_compute_vestiaire_points",
                                      store=True)
    vestiaire_tenue_ids = fields.Many2many("besacraft.vestiaire.cosmetique",
                                           "besacraft_vestiaire_tenue_rel", "partner_id",
                                           "cosmetique_id", string="Outfit",
                                           domain=[("genre", "=", "cosmetique")])
    vestiaire_case_ids = fields.One2many("besacraft.vestiaire.case", "partner_id",
                                         string="Emote wheel")
    # Colour and settings of each worn cosmetic, as the game writes them after the code
    # ("noir||d|2"). Purely visual: stored as received, never interpreted here.
    vestiaire_reglages = fields.Text(string="Outfit settings")

    @api.depends("vestiaire_mouvement_ids.points")
    def _compute_vestiaire_points(self):
        for partner in self:
            partner.vestiaire_points = sum(partner.vestiaire_mouvement_ids.mapped("points"))

    # -- what a player owns ---------------------------------------------------------

    def _vestiaire_possede(self):
        """Published items this player owns: bought, given, or owned by everyone."""
        self.ensure_one()
        Cosmetique = self.env["besacraft.vestiaire.cosmetique"].sudo()
        de_base = Cosmetique.search([("publie", "=", True), ("de_base", "=", True)])
        possedes = self.sudo().vestiaire_possession_ids.cosmetique_id.filtered("publie")
        return de_base | possedes

    def _vestiaire_tenue(self):
        """The worn cosmetics, without what the player no longer owns."""
        self.ensure_one()
        return self.sudo().vestiaire_tenue_ids & self._vestiaire_possede()

    def _vestiaire_tenue_codes(self):
        """The worn codes, each followed by its settings when it has some ("code|noir")."""
        self.ensure_one()
        reglages = self._vestiaire_lire_reglages()
        return [code + ("|" + reglages[code] if reglages.get(code) else "")
                for code in self._vestiaire_tenue().mapped("code")]

    def _vestiaire_lire_reglages(self):
        try:
            reglages = json.loads(self.sudo().vestiaire_reglages or "{}")
        except ValueError:
            return {}
        return reglages if isinstance(reglages, dict) else {}

    def _vestiaire_roue(self):
        """The eight wheel slots as codes, None for an empty slot."""
        self.ensure_one()
        possede = self._vestiaire_possede()
        roue = [None] * 8
        for case in self.sudo().vestiaire_case_ids:
            if 0 <= case.index < 8 and case.emote_id in possede:
                roue[case.index] = case.emote_id.code
        return roue

    def _vestiaire_ranger(self):
        """Drop from the outfit and the wheel what is no longer owned."""
        for partner in self.sudo():
            possede = partner._vestiaire_possede()
            perdus = partner.vestiaire_tenue_ids - possede
            if perdus:
                partner.vestiaire_tenue_ids = [(3, c.id) for c in perdus]
            partner.vestiaire_case_ids.filtered(lambda c: c.emote_id not in possede).unlink()

    def _vestiaire_equiper(self, codes_tenue, codes_roue):
        """Save what the game shows. Unowned codes, a second item on a slot and an
        incompatible slot are dropped without error. Returns what was kept."""
        self.ensure_one()
        partner = self.sudo()
        possede = self._vestiaire_possede()
        par_code = {c.code: c for c in possede}

        tenue = self.env["besacraft.vestiaire.cosmetique"]
        pris = set()
        reglages = {}
        for entree in (codes_tenue or [])[:24]:
            code, _sep, suffixe = entree.partition("|") if isinstance(entree, str) else (None, "", "")
            cosmetique = par_code.get(code) if code else None
            if not cosmetique or cosmetique.genre != "cosmetique" or cosmetique in tenue:
                continue
            slot = cosmetique.emplacement or cosmetique.code
            if slot in pris or INCOMPATIBLES.get(slot, set()) & pris:
                continue
            pris.add(slot)
            tenue |= cosmetique
            if suffixe and len(suffixe) <= REGLAGE_MAX:
                reglages[code] = suffixe
        partner.vestiaire_tenue_ids = [(6, 0, tenue.ids)]
        partner.vestiaire_reglages = json.dumps(reglages) if reglages else False

        partner.vestiaire_case_ids.unlink()
        roue = [None] * 8
        vues = set()
        for index, code in enumerate((codes_roue or [])[:8]):
            emote = par_code.get(code) if isinstance(code, str) else None
            if not emote or emote.genre != "emote" or emote in vues:
                continue
            vues.add(emote)
            roue[index] = emote.code
            self.env["besacraft.vestiaire.case"].sudo().create(
                {"partner_id": partner.id, "index": index, "emote_id": emote.id})
        return {"tenue": [c + ("|" + reglages[c] if c in reglages else "") for c in tenue.mapped("code")],
                "roue": roue}

    # -- points ---------------------------------------------------------------------

    def _vestiaire_verrouiller(self):
        """Serialize the spending of one player: two clicks or two computers never
        spend the same points twice."""
        self.ensure_one()
        self.env.cr.execute("SELECT id FROM res_partner WHERE id = %s FOR UPDATE", [self.id])
        self.env["besacraft.vestiaire.mouvement"].flush_model()
        self.env.cr.execute(
            "SELECT COALESCE(SUM(points), 0) FROM besacraft_vestiaire_mouvement"
            " WHERE partner_id = %s", [self.id])
        return self.env.cr.fetchone()[0]

    def _vestiaire_crediter(self, points, motif, libelle=False, reference=False):
        """Add a movement; with a reference, a second identical call credits nothing.
        Returns the movement, or an empty recordset if it was already credited."""
        self.ensure_one()
        Mouvement = self.env["besacraft.vestiaire.mouvement"].sudo()
        self._vestiaire_verrouiller()
        if reference and Mouvement.search_count([("partner_id", "=", self.id),
                                                 ("motif", "=", motif),
                                                 ("reference", "=", reference)]):
            return Mouvement
        mouvement = Mouvement.create({"partner_id": self.id, "points": points, "motif": motif,
                                      "libelle": libelle, "reference": reference})
        self.message_post(body=_("%(points)s wardrobe points: %(libelle)s",
                                 points=points, libelle=libelle or motif))
        return mouvement

    def _vestiaire_gagner(self, motif, reference, code=None):
        """A reward reported by one of our servers, worth what the scale says.
        Returns (points credited, already credited); raises KeyError without scale."""
        self.ensure_one()
        ligne = self.env["besacraft.vestiaire.bareme"].sudo()._trouver(motif, code)
        if not ligne:
            raise KeyError(motif)
        libelle = ligne.name or dict(self.env["besacraft.vestiaire.bareme"]._fields["motif"]
                                     ._description_selection(self.env)).get(motif)
        mouvement = self._vestiaire_crediter(ligne.points, motif, libelle, reference)
        return ligne.points, not mouvement

    def _vestiaire_acheter(self, code, prix_affiche):
        """Buy an item with points, at the price the player saw. Raises AchatRefuse."""
        self.ensure_one()
        cosmetique = self.env["besacraft.vestiaire.cosmetique"].sudo().search(
            [("code", "=", code)], limit=1)._en_vente()
        if not cosmetique:
            raise AchatRefuse("inconnu")
        solde = self._vestiaire_verrouiller()
        if cosmetique in self._vestiaire_possede():
            raise AchatRefuse("deja_possede", points=solde)
        if prix_affiche != cosmetique.prix:
            raise AchatRefuse("prix_change", points=solde, prix=cosmetique.prix)
        if solde < cosmetique.prix:
            raise AchatRefuse("solde_insuffisant", points=solde, prix=cosmetique.prix)
        self.env["besacraft.vestiaire.mouvement"].sudo().create({
            "partner_id": self.id, "points": -cosmetique.prix, "motif": "achat",
            "libelle": cosmetique.name, "cosmetique_id": cosmetique.id})
        self.env["besacraft.vestiaire.possession"].sudo().create({
            "partner_id": self.id, "cosmetique_id": cosmetique.id, "origine": "achat",
            "annonce": True})
        self.message_post(body=_("Bought %(nom)s for %(prix)s points in the wardrobe.",
                                 nom=cosmetique.name, prix=cosmetique.prix))
        return solde - cosmetique.prix

    def _vestiaire_offrir_cosmetique(self, cosmetique, origine="offert"):
        for partner in self:
            if not partner.sudo().vestiaire_possession_ids.filtered(
                    lambda p: p.cosmetique_id == cosmetique):
                self.env["besacraft.vestiaire.possession"].sudo().create(
                    {"partner_id": partner.id, "cosmetique_id": cosmetique.id,
                     "origine": origine})

    def _vestiaire_nouvelles(self):
        """Gains not yet told in game, marked as told."""
        self.ensure_one()
        mouvements = self.sudo().vestiaire_mouvement_ids.filtered(
            lambda m: not m.annonce and m.points > 0).sorted("id")
        nouvelles = [{"points": m.points, "libelle": m.libelle or ""} for m in mouvements]
        mouvements.write({"annonce": True})
        cadeaux = self.sudo().vestiaire_possession_ids.filtered(
            lambda p: not p.annonce and p.cosmetique_id.publie).sorted("id")
        nouvelles += [{"points": 0, "libelle": p.cosmetique_id.name,
                       "code": p.cosmetique_id.code} for p in cadeaux]
        cadeaux.write({"annonce": True})
        return nouvelles

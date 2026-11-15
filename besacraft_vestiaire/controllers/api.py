import base64
import json
import re

import werkzeug

from odoo import fields, http
from odoo.http import request

from odoo.addons.besacraft_minecraft_api.controllers.base import limiter, partenaire_ou_401, reponse

from ..models.res_partner import AchatRefuse

APPELS_SERVEUR_PAR_MINUTE = 120
EMPREINTE = re.compile(r"^[0-9a-f]{64}$")


def corps_json():
    """The JSON object sent by the game, or 400."""
    try:
        donnees = json.loads(request.httprequest.get_data(as_text=True) or "{}")
    except ValueError:
        donnees = None
    if not isinstance(donnees, dict):
        raise werkzeug.exceptions.BadRequest()
    return donnees


class VestiaireApi(http.Controller):

    def _compte(self):
        """The valid account behind the token, or a 403 answer telling where to ask."""
        partner = partenaire_ou_401()
        if partner._vestiaire_valide():
            return partner, None
        Code = request.env["besacraft.vestiaire.code"].sudo()
        code = Code._emettre(partner.minecraft_uuid, partner.minecraft_login or "")
        return partner, reponse({"erreur": "compte_non_valide", "code": code.code,
                                 "url": Code._url(code.code)}, code=403)

    def _cle_serveur(self):
        """The active server key behind the Bearer header, or an empty recordset."""
        entete = request.httprequest.headers.get("Authorization") or ""
        Cle = request.env["besacraft.vestiaire.cle.serveur"].sudo()
        return Cle._par_cle(entete[7:] if entete.startswith("Bearer ") else "")

    def _joueur_ou_serveur(self):
        """Let in a signed-in player or one of our Minecraft servers; 401 otherwise. A wrong
        key falls through to the player check, whose per-address ceiling counts it."""
        cle = self._cle_serveur()
        if cle:
            limiter("serveur-ip:%s" % request.httprequest.remote_addr, APPELS_SERVEUR_PAR_MINUTE, 60)
            cle.derniere_utilisation = fields.Datetime.now()
            return
        partenaire_ou_401()

    @http.route("/mc/v1/vestiaire/distants", type="http", auth="public", methods=["GET"],
                csrf=False, save_session=False)
    def distants(self, **kw):
        """The manifest of the remote cosmetics: catalogue entries and files to download."""
        self._joueur_ou_serveur()
        Cosmetique = request.env["besacraft.vestiaire.cosmetique"].sudo()
        return reponse(Cosmetique._distants_servis()._manifeste())

    @http.route("/mc/v1/vestiaire/fichier/<string:empreinte>", type="http", auth="public",
                methods=["GET"], csrf=False, save_session=False)
    def fichier(self, empreinte, **kw):
        """One remote file, by its SHA-256. Only files of a served cosmetic go out."""
        self._joueur_ou_serveur()
        if not EMPREINTE.match(empreinte):
            raise werkzeug.exceptions.BadRequest()
        Cosmetique = request.env["besacraft.vestiaire.cosmetique"].sudo()
        fichier = request.env["besacraft.vestiaire.fichier"].sudo().search([
            ("sha256", "=", empreinte), ("cosmetique_id", "in", Cosmetique._distants_servis().ids)], limit=1)
        if not fichier:
            raise werkzeug.exceptions.NotFound()
        return request.make_response(base64.b64decode(fichier.contenu), headers=[
            ("Content-Type", "application/octet-stream"),
            ("Cache-Control", "private, max-age=31536000, immutable"),
        ])

    @http.route("/mc/v1/vestiaire/moi", type="http", auth="public", methods=["GET"],
                csrf=False, save_session=False)
    def moi(self, **kw):
        partner, refus = self._compte()
        if refus:
            return refus
        skin = partner._vestiaire_skin_actif()
        armures, derniere = partner._vestiaire_armures()
        return reponse({
            "pseudo": partner.minecraft_login,
            "skin": {"empreinte": skin.empreinte, "modele": skin.modele} if skin else None,
            "cape": partner.vestiaire_cape_id.empreinte or None,
            "points": partner.vestiaire_points,
            "possede": partner._vestiaire_possede().mapped("code"),
            "tenue": partner._vestiaire_tenue_codes(),
            "roue": partner._vestiaire_roue(),
            "armures": armures,
            "armure_derniere": derniere,
            "nouvelles": partner._vestiaire_nouvelles(),
        })

    @http.route("/mc/v1/vestiaire/catalogue", type="http", auth="public", methods=["GET"],
                csrf=False, save_session=False)
    def catalogue(self, **kw):
        partner, refus = self._compte()
        if refus:
            return refus
        possede = partner._vestiaire_possede()
        objets = possede | possede.search([("publie", "=", True), ("prix", ">", 0)])
        return reponse({"cosmetiques": [{
            "code": c.code, "genre": c.genre, "nom": c.name, "emplacement": c.emplacement or None,
            "prix": c.prix, "de_base": c.de_base, "possede": c in possede,
        } for c in objets.sorted(lambda c: (c.genre, c.sequence, c.name, c.id))]})

    @http.route("/mc/v1/vestiaire/equipement", type="http", auth="public", methods=["PUT"],
                csrf=False, save_session=False)
    def equipement(self, **kw):
        partner, refus = self._compte()
        if refus:
            return refus
        donnees = corps_json()
        tenue, roue = donnees.get("tenue"), donnees.get("roue")
        if not isinstance(tenue, list) or not isinstance(roue, list):
            raise werkzeug.exceptions.BadRequest()
        resultat = partner._vestiaire_equiper(tenue, roue)
        # Merged, not replaced: a game without armours (2.5.0) sends no "armures" and keeps the stand.
        if "armures" in donnees:
            if not isinstance(donnees["armures"], list):
                raise werkzeug.exceptions.BadRequest()
            armures, derniere = partner._vestiaire_equiper_armures(donnees["armures"],
                                                                    donnees.get("armure_derniere", -1))
        else:
            armures, derniere = partner._vestiaire_armures()
        return reponse(dict(resultat, armures=armures, armure_derniere=derniere))

    @http.route("/mc/v1/vestiaire/achat", type="http", auth="public", methods=["POST"],
                csrf=False, save_session=False)
    def achat(self, **kw):
        partner, refus = self._compte()
        if refus:
            return refus
        donnees = corps_json()
        code, prix = donnees.get("code"), donnees.get("prix")
        if not isinstance(code, str) or not isinstance(prix, int) or isinstance(prix, bool):
            raise werkzeug.exceptions.BadRequest()
        try:
            points = partner._vestiaire_acheter(code, prix)
        except AchatRefuse as refuse:
            if refuse.erreur == "inconnu":
                return reponse({"erreur": "inconnu"}, code=404)
            return reponse(dict(refuse.details, erreur=refuse.erreur), code=409)
        return reponse({"points": points, "possede": partner._vestiaire_possede().mapped("code")})

    @http.route("/mc/v1/serveur/gain", type="http", auth="public", methods=["POST"],
                csrf=False, save_session=False)
    def gain(self, **kw):
        """A reward reported by one of our Minecraft servers. Replayable: the same
        player, reason and reference is credited once."""
        limiter("serveur-ip:%s" % request.httprequest.remote_addr, APPELS_SERVEUR_PAR_MINUTE, 60)
        cle = self._cle_serveur()
        if not cle:
            raise werkzeug.exceptions.Unauthorized()
        cle.derniere_utilisation = fields.Datetime.now()
        donnees = corps_json()
        uuid, motif, reference = (donnees.get("uuid"), donnees.get("motif"),
                                  donnees.get("reference"))
        code = donnees.get("code")
        if not all(isinstance(v, str) and v for v in (uuid, motif, reference)) or (
                code is not None and not isinstance(code, str)):
            raise werkzeug.exceptions.BadRequest()
        if motif not in ("mission", "defi"):
            return reponse({"erreur": "motif_refuse"}, code=400)
        partner = request.env["res.partner"].sudo()._vestiaire_par_uuid(uuid)
        if not partner:
            return reponse({"erreur": "joueur_inconnu"}, code=404)
        try:
            points, deja = partner._vestiaire_gagner(motif, reference, code)
        except KeyError:
            return reponse({"erreur": "bareme_absent"}, code=422)
        return reponse({"points": points, "deja_credite": deja})

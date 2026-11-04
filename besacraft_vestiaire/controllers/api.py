import json

import werkzeug

from odoo import fields, http
from odoo.http import request

from odoo.addons.besacraft_minecraft_api.controllers.base import limiter, partenaire_ou_401, reponse

from ..models.res_partner import AchatRefuse

APPELS_SERVEUR_PAR_MINUTE = 120


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

    @http.route("/mc/v1/vestiaire/moi", type="http", auth="public", methods=["GET"],
                csrf=False, save_session=False)
    def moi(self, **kw):
        partner, refus = self._compte()
        if refus:
            return refus
        skin = partner._vestiaire_skin_actif()
        return reponse({
            "pseudo": partner.minecraft_login,
            "skin": {"empreinte": skin.empreinte, "modele": skin.modele} if skin else None,
            "cape": partner.vestiaire_cape_id.empreinte or None,
            "points": partner.vestiaire_points,
            "possede": partner._vestiaire_possede().mapped("code"),
            "tenue": partner._vestiaire_tenue().mapped("code"),
            "roue": partner._vestiaire_roue(),
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
        return reponse(partner._vestiaire_equiper(tenue, roue))

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
        entete = request.httprequest.headers.get("Authorization") or ""
        Cle = request.env["besacraft.vestiaire.cle.serveur"].sudo()
        cle = Cle._par_cle(entete[7:] if entete.startswith("Bearer ") else "")
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

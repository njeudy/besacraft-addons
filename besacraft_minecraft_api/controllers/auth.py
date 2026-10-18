import werkzeug

from odoo import http
from odoo.http import request

from .base import DEFIS_PAR_MINUTE, limiter, reponse

OU_LIER = "https://nicolas.alusage.fr/my/account"


class BesacraftMcAuth(http.Controller):
    """The handshake: a one-shot challenge, then a session token."""

    @http.route("/mc/v1/defi", type="http", auth="public", methods=["POST"],
                csrf=False, save_session=False)
    def defi(self, **kw):
        limiter("defi:%s" % request.httprequest.remote_addr, DEFIS_PAR_MINUTE, 60)
        defi = request.env["besacraft.mc.challenge"].sudo()._nouveau()
        return reponse({"server_id": defi.server_id})

    @http.route("/mc/v1/session", type="http", auth="public", methods=["POST"],
                csrf=False, save_session=False)
    def session(self, **kw):
        # `get_json_data` is a bare `json.loads`, and anything that is not an
        # HTTPException leaves as a 500 with a traceback -- on an open endpoint.
        try:
            corps = request.get_json_data()
            pseudo, server_id = corps.get("pseudo"), corps.get("server_id")
        except (ValueError, AttributeError):
            raise werkzeug.exceptions.BadRequest()
        if not pseudo or not server_id:
            raise werkzeug.exceptions.BadRequest()
        Defi = request.env["besacraft.mc.challenge"].sudo()
        if not Defi._consommer(server_id):
            raise werkzeug.exceptions.Forbidden()
        Session = request.env["besacraft.mc.session"].sudo()
        uuid = Session._uuid_certifie(pseudo, server_id)
        if not uuid:
            raise werkzeug.exceptions.Forbidden()
        partenaire = request.env["res.partner"].sudo().search(
            [("minecraft_uuid", "=", uuid)], limit=2)
        if len(partenaire) > 1:
            # Unreachable while the uniqueness constraint holds, which is the point:
            # on a base where it could not be installed, picking one of the two would
            # hand this player a session on somebody else's account.
            return reponse({"erreur": "compte_ambigu", "ou": OU_LIER}, code=409)
        if not partenaire:
            # Known player, unknown customer: say where to link the account rather than
            # refusing flatly -- this is the most common first contact.
            return reponse({"erreur": "compte_non_lie", "ou": OU_LIER}, code=404)
        session = Session._ouvrir(partenaire)
        return reponse({"token": session.token,
                        "expire_le": session.expire_le.isoformat(),
                        "nom": partenaire.name})

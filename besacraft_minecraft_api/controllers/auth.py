import werkzeug

from odoo import http
from odoo.http import request

from .base import reponse

OU_LIER = "https://nicolas.alusage.fr/my/account"


class BesacraftMcAuth(http.Controller):
    """The handshake: a one-shot challenge, then a session token."""

    @http.route("/mc/v1/defi", type="http", auth="public", methods=["POST"],
                csrf=False, save_session=False)
    def defi(self, **kw):
        defi = request.env["besacraft.mc.challenge"].sudo()._nouveau()
        return reponse({"server_id": defi.server_id})

    @http.route("/mc/v1/session", type="http", auth="public", methods=["POST"],
                csrf=False, save_session=False)
    def session(self, **kw):
        corps = request.get_json_data()
        pseudo, server_id = corps.get("pseudo"), corps.get("server_id")
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
            [("minecraft_uuid", "=", uuid)], limit=1)
        if not partenaire:
            # Known player, unknown customer: say where to link the account rather than
            # refusing flatly -- this is the most common first contact.
            return reponse({"erreur": "compte_non_lie", "ou": OU_LIER}, code=404)
        session = Session._ouvrir(partenaire)
        return reponse({"token": session.token,
                        "expire_le": session.expire_le.isoformat(),
                        "nom": partenaire.name})

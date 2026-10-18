import json

import werkzeug

from odoo.http import request


def reponse(donnees, code=200):
    """A plain JSON body, because the mod is an HTTP client, not a JSON-RPC one."""
    return request.make_response(
        json.dumps(donnees, separators=(",", ":")),
        headers=[("Content-Type", "application/json")], status=code)


def partenaire_ou_401():
    """The partner behind the Bearer token, or 401. Never falls back to a public user."""
    entete = request.httprequest.headers.get("Authorization") or ""
    jeton = entete[7:] if entete.startswith("Bearer ") else ""
    partenaire = request.env["besacraft.mc.session"].sudo()._partenaire_du_jeton(jeton)
    if not partenaire:
        raise werkzeug.exceptions.Unauthorized()
    return partenaire

import json
import time
from collections import defaultdict, deque

import werkzeug

from odoo.http import request

# Per-worker and in memory on purpose: this is a ceiling against a runaway client or a
# clumsy script, not a defence against a distributed attack -- that belongs at the
# reverse proxy. Keeping it here costs nothing and needs no shared store.
_passages = defaultdict(deque)

DEFIS_PAR_MINUTE = 20
APPELS_PAR_MINUTE = 300


def limiter(cle, maximum, fenetre):
    """Raise 429 past `maximum` calls in the last `fenetre` seconds."""
    maintenant = time.monotonic()
    passages = _passages[cle]
    while passages and maintenant - passages[0] > fenetre:
        passages.popleft()
    if len(passages) >= maximum:
        raise werkzeug.exceptions.TooManyRequests()
    passages.append(maintenant)


def reponse(donnees, code=200):
    """A plain JSON body, because the mod is an HTTP client, not a JSON-RPC one."""
    return request.make_response(
        json.dumps(donnees, separators=(",", ":")),
        headers=[("Content-Type", "application/json")], status=code)


def partenaire_ou_401():
    """The partner behind the Bearer token, or 401. Never falls back to a public user."""
    # The ceiling comes before the refusal, not after it: four of the six routes are
    # `auth="public"` and are rejected right here, and a refusal that costs nothing to
    # repeat is a refusal that can be repeated forever. Behind a reverse proxy this
    # key is only per-player if `proxy_mode = True` -- see the module's README.
    limiter("ip:%s" % request.httprequest.remote_addr, APPELS_PAR_MINUTE, 60)
    entete = request.httprequest.headers.get("Authorization") or ""
    jeton = entete[7:] if entete.startswith("Bearer ") else ""
    partenaire = request.env["besacraft.mc.session"].sudo()._partenaire_du_jeton(jeton)
    if not partenaire:
        raise werkzeug.exceptions.Unauthorized()
    limiter("api:%s" % partenaire.id, APPELS_PAR_MINUTE, 60)
    return partenaire

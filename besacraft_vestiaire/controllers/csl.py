import base64
import json
import re

from odoo import http
from odoo.http import request

PSEUDO = re.compile(r"^[A-Za-z0-9_]{1,16}$")
HASH = re.compile(r"^[0-9a-f]{64}$")
CACHE = [("Cache-Control", "public, max-age=31536000, immutable")]


class VestiaireCsl(http.Controller):
    """The CustomSkinAPI format read by CustomSkinLoader: profile, then textures by hash."""

    def _joueur(self, pseudo):
        # Escape the SQL wildcards: the pseudo is matched whole, case-insensitively.
        motif = re.sub(r"([\\%_])", r"\\\1", pseudo)
        candidats = request.env["res.partner"].sudo().search(
            [("minecraft_login", "=ilike", motif)])
        # minecraft_login is not unique: the first valid account wins.
        return next((p for p in candidats if p._vestiaire_valide()), None)

    @http.route("/csl/<string:pseudo>.json", type="http", auth="public",
                methods=["GET"], csrf=False, save_session=False)
    def profil(self, pseudo, **kw):
        partner = self._joueur(pseudo) if PSEUDO.match(pseudo) else None
        if not partner:
            raise request.not_found()
        corps = {"username": partner.minecraft_login}
        skin = partner._vestiaire_skin_actif()
        if skin:
            corps["skins"] = {"slim" if skin.modele == "slim" else "default": skin.empreinte}
        cape = partner.vestiaire_cape_id
        if cape.publiee:
            corps["cape"] = cape.empreinte
            if cape.empreinte_elytre:
                corps["elytra"] = cape.empreinte_elytre
        return request.make_response(json.dumps(corps),
                                     headers=[("Content-Type", "application/json"),
                                              ("Cache-Control", "no-cache")])

    @http.route("/csl/textures/<string:empreinte>", type="http", auth="public",
                methods=["GET"], csrf=False, save_session=False)
    def texture(self, empreinte, **kw):
        if not HASH.match(empreinte):
            raise request.not_found()
        env = request.env
        skins = env["besacraft.vestiaire.skin"].sudo().search(
            [("empreinte", "=", empreinte), ("actif", "=", True)])
        skin = next((s for s in skins if s.partner_id._vestiaire_valide()), None)
        if skin:
            return self._png(skin.image)
        portee = env["res.partner"].sudo().search(
            ["|", ("vestiaire_cape_id.empreinte", "=", empreinte),
             ("vestiaire_cape_id.empreinte_elytre", "=", empreinte)])
        porteur = portee.filtered(
            lambda p: p._vestiaire_valide() and p.vestiaire_cape_id.publiee)[:1]
        if not porteur:
            raise request.not_found()
        cape = porteur.vestiaire_cape_id
        return self._png(cape.image if cape.empreinte == empreinte else cape.image_elytre)

    def _png(self, image):
        return request.make_response(base64.b64decode(image),
                                     headers=[("Content-Type", "image/png"),
                                              ("X-Content-Type-Options", "nosniff")] + CACHE)

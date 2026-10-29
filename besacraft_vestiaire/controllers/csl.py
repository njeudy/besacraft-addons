import base64
import json
import re

from odoo import http
from odoo.http import request

HASH = re.compile(r"^[0-9a-f]{64}$")
CACHE = [("Cache-Control", "public, max-age=31536000, immutable")]


class VestiaireCsl(http.Controller):
    """The CustomSkinAPI format read by CustomSkinLoader: profile, then textures by hash."""

    def _joueur(self, pseudo):
        partner = request.env["res.partner"].sudo().search(
            [("minecraft_login", "=ilike", pseudo)], limit=1)
        return partner if partner and partner._vestiaire_valide() else None

    @http.route("/csl/<string:pseudo>.json", type="http", auth="public",
                methods=["GET"], csrf=False, save_session=False)
    def profil(self, pseudo, **kw):
        partner = self._joueur(pseudo)
        if not partner:
            return request.not_found()
        corps = {"username": partner.minecraft_login}
        skin = partner._vestiaire_skin_actif()
        if skin:
            corps["skins"] = {"slim" if skin.modele == "slim" else "default": skin.empreinte}
        cape = partner.vestiaire_cape_id
        if cape:
            corps["cape"] = cape.empreinte
            if cape.empreinte_elytre:
                corps["elytra"] = cape.empreinte_elytre
        return request.make_response(json.dumps(corps),
                                     headers=[("Content-Type", "application/json")])

    @http.route("/csl/textures/<string:empreinte>", type="http", auth="public",
                methods=["GET"], csrf=False, save_session=False)
    def texture(self, empreinte, **kw):
        if not HASH.match(empreinte):
            return request.not_found()
        env = request.env
        skin = env["besacraft.vestiaire.skin"].sudo().search(
            [("empreinte", "=", empreinte)], limit=1)
        if skin and skin.partner_id._vestiaire_valide():
            return self._png(skin.image)
        portee = env["res.partner"].sudo().search(
            ["|", ("vestiaire_cape_id.empreinte", "=", empreinte),
             ("vestiaire_cape_id.empreinte_elytre", "=", empreinte)])
        porteur = portee.filtered(lambda p: p._vestiaire_valide())[:1]
        if not porteur:
            return request.not_found()
        cape = porteur.vestiaire_cape_id
        return self._png(cape.image if cape.empreinte == empreinte else cape.image_elytre)

    def _png(self, image):
        return request.make_response(base64.b64decode(image),
                                     headers=[("Content-Type", "image/png")] + CACHE)

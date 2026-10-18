import base64
import json

import werkzeug

from odoo import http
from odoo.http import request

from .base import partenaire_ou_401, reponse
from .catalogue import BesacraftMcCatalogue


class BesacraftMcGeometrie(BesacraftMcCatalogue):
    """The one route that lets block types out, and the one place the lock lives."""

    @http.route("/mc/v1/build/<string:code>/couche/<int:n>", type="http", auth="public",
                methods=["GET"], csrf=False, save_session=False)
    def couche(self, code, n, **kw):
        """One layer's blocks, with their types.

        A layer already laid stays readable -- the player re-reads their notice. Only
        the ones ahead of the work are withheld.
        """
        partenaire = partenaire_ou_401()
        build, membre = self._membre_ou_403(partenaire, code)
        if n < 1 or n > build.layer_count:
            raise werkzeug.exceptions.NotFound()
        if n > membre.layer_reached + 1:
            raise werkzeug.exceptions.Forbidden()
        if not build.build_json_attachment_id:
            return reponse({"erreur": "plan_absent", "code": build.code}, code=409)
        plan = json.loads(base64.b64decode(build.build_json_attachment_id.datas))
        couches = plan.get("layers") or []
        # The tutorial skips the sunk foundations; layer 1 of the notice is layer
        # `layer_offset` of the file. Without this the mod would lay the wrong level.
        index = build.layer_offset + n - 1
        if index < 0 or index >= len(couches):
            raise werkzeug.exceptions.NotFound()
        brute = couches[index]
        palette = plan.get("palette") or []
        blocs = [[x, z, palette[i].get("key") or palette[i].get("id")]
                 for x, z, i in (brute.get("blocks") or [])
                 if i < len(palette) and not str(palette[i].get("id", "")).endswith(":air")]
        return reponse({"n": n, "y": brute.get("y", 0), "blocs": blocs})

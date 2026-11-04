import werkzeug

from odoo import http
from odoo.http import request

from .base import partenaire_ou_401, reponse

FICHE = "https://nicolas.alusage.fr/builds/%d"


class BesacraftMcCatalogue(http.Controller):
    """What the mod needs to draw the shelf and the index page of one book."""

    def _membre_ou_403(self, partenaire, code):
        """The build and this partner's membership line, or 404 / 403.

        A build that exists but was never added to this player's books answers 403,
        never a sheet: membership is the only key, and a paid build's geometry must
        not come out just because its code was guessed.
        """
        build = request.env["besacraft.build"].sudo().search([("code", "=", code)], limit=1)
        if not build:
            raise werkzeug.exceptions.NotFound()
        membre = request.env["besacraft.build.member"].sudo().search(
            [("build_id", "=", build.id), ("partner_id", "=", partenaire.id)], limit=1)
        if not membre:
            raise werkzeug.exceptions.Forbidden()
        return build, membre

    @http.route("/mc/v1/builds", type="http", auth="public", methods=["GET"],
                csrf=False, save_session=False)
    def builds(self, **kw):
        partenaire = partenaire_ou_401()
        membres = request.env["besacraft.build.member"].sudo().search(
            [("partner_id", "=", partenaire.id)])
        return reponse({"builds": [{
            "code": m.build_id.code,
            "nom": m.build_id.name,
            "serie": m.build_id.serie_id.name,
            "couches": m.build_id.layer_count,
            "blocs": m.build_id.block_count,
            "layer_reached": m.layer_reached,
        } for m in membres]})

    # `<string:code>` and not `<int:code>`: a junk code must reach the method and get a
    # plain 404 from the search, instead of an opaque routing 404 the mod cannot read.
    @http.route("/mc/v1/build/<string:code>", type="http", auth="public", methods=["GET"],
                csrf=False, save_session=False)
    def build(self, code, **kw):
        partenaire = partenaire_ou_401()
        build, membre = self._membre_ou_403(partenaire, code)
        a_farmer = {}
        for couche in build.layer_ids:
            for ligne in couche.line_ids:
                a_farmer[ligne.item_key] = a_farmer.get(ligne.item_key, 0) + ligne.qty
        return reponse({
            "code": build.code, "nom": build.name, "serie": build.serie_id.name,
            "blocs": build.block_count, "couches_total": build.layer_count,
            "taille": [build.size_x, build.size_y, build.size_z],
            "layer_reached": membre.layer_reached,
            "a_farmer": a_farmer,
            "fiche": FICHE % int(build.code),
            "short": build.short_youtube_url or "",
            "couches": [{
                "n": couche.sequence,
                "titre": couche.title or "",
                "consigne": couche.instruction or "",
                "blocs": {l.item_key: l.qty for l in couche.line_ids},
            } for couche in build.layer_ids.sorted("sequence")],
        })

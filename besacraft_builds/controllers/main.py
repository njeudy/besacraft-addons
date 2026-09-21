import base64
import json

from odoo import http
from odoo.http import request


class BesacraftBuilds(http.Controller):
    """Public pages of the build catalogue."""

    @http.route("/builds", type="http", auth="public", website=True, sitemap=True)
    def catalogue(self, serie=None, **kw):
        """The catalogue, laid out as a shelf of construction boxes."""
        domaine = [("is_published", "=", True)]
        Build = request.env["besacraft.build"].sudo()
        series = request.env["besacraft.serie"].sudo().search([])
        if serie:
            domaine.append(("serie_id.code", "=", serie))
        builds = Build.search(domaine)
        # Le compteur de chaque filtre se lit sur la totalité, pas sur la sélection
        # courante : un filtre qui afficherait « 0 » une fois cliqué serait absurde.
        tous = Build.search_count([("is_published", "=", True)])
        par_serie = {
            s.id: Build.search_count([("is_published", "=", True), ("serie_id", "=", s.id)])
            for s in series
        }
        return request.render("besacraft_builds.catalogue", {
            "builds": builds, "series": series, "serie_active": serie,
            "total": tous, "par_serie": par_serie,
        })

    @http.route("/t/<int:code>", type="http", auth="public", website=True, sitemap=True)
    def tuto(self, code, **kw):
        """A build's tutorial sheet. The URL carries the number without padding zeros."""
        build = request.env["besacraft.build"].sudo().search(
            [("code", "=", "%03d" % code), ("is_published", "=", True)], limit=1)
        if not build:
            return request.not_found()
        # Les couches partent en JSON : la page change de couche sans aller-retour serveur,
        # et la liste se coche pendant qu'on pose, hors ligne si besoin.
        couches = [{
            "sequence": c.sequence,
            "title": c.title or "",
            "block_count": c.block_count,
            "lines": [{"id": l.id, "name": l.name_fr or l.item_key,
                       "mod": l.mod or "", "qty": l.qty} for l in c.line_ids],
        } for c in build.layer_ids]
        return request.render("besacraft_builds.tuto", {
            "build": build,
            "accessible": build.is_accessible_by(request.env.user.partner_id),
            "couches_json": json.dumps(couches),
        })

    @http.route("/besacraft/viewer/<int:build_id>", type="http", auth="public", sitemap=False)
    def viewer(self, build_id, **kw):
        """Serve the build's standalone viewer.html from OUR origin.

        Same origin is not a detail: the page injects a stylesheet into the iframe and
        reads the build data out of it, and neither is possible across origins.
        """
        build = request.env["besacraft.build"].sudo().browse(build_id).exists()
        if not build or not build.viewer_attachment_id:
            return request.not_found()
        if not build.is_accessible_by(request.env.user.partner_id):
            return request.not_found()
        piece = build.viewer_attachment_id
        contenu = base64.b64decode(piece.datas)
        # The viewer is regenerated per build version: a long cache plus an ETag on the
        # attachment id avoids shipping several megabytes on every layer change.
        etag = '"%s-%s"' % (build.id, piece.id)
        if request.httprequest.headers.get("If-None-Match") == etag:
            return request.make_response("", status=304, headers=[("ETag", etag)])
        return request.make_response(contenu, headers=[
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(contenu))),
            ("Cache-Control", "private, max-age=86400"),
            ("ETag", etag),
        ])

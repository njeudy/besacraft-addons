import base64
import json

from odoo import http
from odoo.http import request


def _site_besacraft(env):
    """Sitemap hook: the catalogue is only crawled on the site that serves it."""
    return env["website"].get_current_website().besacraft_enabled


class BesacraftBuilds(http.Controller):
    """Public pages of the build catalogue."""

    def _garde_site(self):
        """404 hors du site Besacraft.

        Borner les ENREGISTREMENTS par `website_id` ne suffisait pas : les autres sites
        servaient /builds en rayon vide, habillage compris. Un catalogue qui existe et
        ne contient rien a l'air cassé — mieux vaut que la page n'existe pas du tout.
        """
        return not request.website.besacraft_enabled

    def _filtre_publie(self):
        """`[]` pour un éditeur du site, le filtre de publication pour tout le monde.

        Un tuto se relit en ligne avant d'être ouvert au public : sans cette exception,
        « non publié » voudrait dire « invisible même pour son auteur », et la seule
        façon de se relire serait de publier d'abord. C'est le comportement du blog.
        """
        if request.env.user.has_group("website.group_website_designer"):
            return []
        return [("is_published", "=", True)]

    @http.route("/builds", type="http", auth="public", website=True,
                sitemap=_site_besacraft)
    def catalogue(self, serie=None, **kw):
        """The catalogue, laid out as a shelf of construction boxes."""
        if self._garde_site():
            return request.not_found()
        # website_domain() borne au site courant : le même Odoo sert aussi la boutique
        # freelance, et /builds y afficherait les tutos de Besacraft.
        domaine = self._filtre_publie() + request.website.website_domain()
        Build = request.env["besacraft.build"].sudo()
        series = request.env["besacraft.serie"].sudo().search([])
        if serie:
            domaine.append(("serie_id.code", "=", serie))
        builds = Build.search(domaine)
        # Le compteur de chaque filtre se lit sur la totalité, pas sur la sélection
        # courante : un filtre qui afficherait « 0 » une fois cliqué serait absurde.
        publies = self._filtre_publie() + request.website.website_domain()
        tous = Build.search_count(publies)
        par_serie = {
            s.id: Build.search_count(publies + [("serie_id", "=", s.id)]) for s in series
        }
        return request.render("besacraft_builds.catalogue", {
            "builds": builds, "series": series, "serie_active": serie,
            "total": tous, "par_serie": par_serie,
        })

    @http.route("/t/<int:code>", type="http", auth="public", website=True,
                sitemap=_site_besacraft)
    def tuto(self, code, **kw):
        """A build's tutorial sheet. The URL carries the number without padding zeros."""
        if self._garde_site():
            return request.not_found()
        build = request.env["besacraft.build"].sudo().search(
            [("code", "=", "%03d" % code)] + self._filtre_publie()
            + request.website.website_domain(), limit=1)
        if not build:
            return request.not_found()
        # Les couches partent en JSON : la page change de couche sans aller-retour serveur,
        # et la liste se coche pendant qu'on pose, hors ligne si besoin.
        accessible = build.is_accessible_by(request.env.user.partner_id)
        # Sans accès, la notice ne part pas dans la page : le voile serait une serrure en
        # carton si la liste des blocs restait lisible dans le code source.
        couches = [] if not accessible else [{
            "sequence": c.sequence,
            "title": c.title or "",
            "block_count": c.block_count,
            "lines": [{"id": l.id, "name": l.name_fr or l.item_key, "key": l.item_key,
                       "mod": l.mod or "", "qty": l.qty} for l in c.line_ids],
        } for c in build.layer_ids]
        return request.render("besacraft_builds.tuto", {
            "build": build,
            # `main_object` est la clé sur laquelle la barre d'édition du site se branche :
            # c'est elle qui fait apparaître l'interrupteur « Publié / Non publié » et le
            # panneau « Optimiser le référencement ». Sans elle, la page est éditable mais
            # ne se publie que depuis le backend.
            "main_object": build,
            "accessible": accessible,
            "couches_json": json.dumps(couches),
            "decalage": build.layer_offset,
        })

    def _vers_le_produit(self, build):
        """Redirection vers le produit quand l'accès manque, sinon None.

        `sudo` sur le produit : un visiteur n'a pas le droit de lire product.product, mais
        il a le droit de savoir ce qu'il doit acheter et combien ça coûte.
        """
        if build.is_accessible_by(request.env.user.partner_id):
            return None
        produit = build.sudo().product_id
        if build.enroll == "payment" and produit:
            return request.redirect(produit.product_tmpl_id.website_url, code=303)
        return None     # enroll=invite : la fiche s'affiche, verrouillée et sans achat

    @http.route("/besacraft/viewer/<int:build_id>", type="http", auth="public", sitemap=False)
    def viewer(self, build_id, **kw):
        """Serve the build's standalone viewer.html from OUR origin.

        Same origin is not a detail: the page injects a stylesheet into the iframe and
        reads the build data out of it, and neither is possible across origins.
        """
        if self._garde_site():
            return request.not_found()
        build = request.env["besacraft.build"].sudo().browse(build_id).exists()
        if not build or not build.viewer_attachment_id:
            return request.not_found()
        redirection = self._vers_le_produit(build)
        if redirection:
            return redirection
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

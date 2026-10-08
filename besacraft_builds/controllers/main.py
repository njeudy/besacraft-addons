import base64
import json
import random

from odoo import http
from odoo.http import request


def _site_besacraft(env, rule=None, qs=None):
    """Sitemap hook: the catalogue is only crawled on the sites that serve it.

    One callable stands for every route that names it (the sitemap runs it once), so it
    lists all the pages itself: the shelf, each published build with its tutorial, and the
    series with their episodes. Nothing is listed on a site that publishes no series.
    """
    site = env["website"].get_current_website()
    series = site._besacraft_series()
    if not series:
        return
    Build = env["besacraft.build"].sudo()
    yield {"loc": "/builds"}
    for build in Build.search(Build._domaine_site(site) + [("is_published", "=", True)]):
        yield {"loc": "/builds/%d" % int(build.code)}
        yield {"loc": "/t/%d" % int(build.code)}
    for serie in series:
        yield {"loc": "/builds/serie/%s" % serie.code}
        yield {"loc": "/builds/serie/%s/episodes" % serie.code}


class BesacraftBuilds(http.Controller):
    """Public pages of the build catalogue."""

    def _site(self):
        return request.env["website"].get_current_website()

    def _garde_site(self):
        """404 sur un site qui ne publie aucune série.

        Borner les ENREGISTREMENTS par `website_id` ne suffisait pas : les autres sites
        servaient /builds en rayon vide, habillage compris. Un catalogue qui existe et
        ne contient rien a l'air cassé — mieux vaut que la page n'existe pas du tout.

        `get_current_website()` et non `request.website` : la route du viewer n'est pas
        déclarée `website=True` (elle sert un fichier, pas une page), et `request.website`
        n'y existe donc pas — la garde y répondait 500 au lieu de 404.
        """
        return not self._site()._besacraft_series()

    def _filtre_publie(self):
        """`[]` pour un éditeur du site, le filtre de publication pour tout le monde.

        Un tuto se relit en ligne avant d'être ouvert au public : sans cette exception,
        « non publié » voudrait dire « invisible même pour son auteur », et la seule
        façon de se relire serait de publier d'abord. C'est le comportement du blog.
        """
        if request.env.user.has_group("website.group_website_designer"):
            return []
        return [("is_published", "=", True)]

    def _domaine_builds(self):
        """Builds a visitor may see here: published (editors: all) and in this site's series."""
        return self._filtre_publie() + request.env["besacraft.build"]._domaine_site(
            request.website)

    @staticmethod
    def _code(code):
        return "%03d" % code

    def _build(self, code):
        """The build behind /builds/<n> or /t/<n>, or an empty recordset."""
        return request.env["besacraft.build"].sudo().search(
            [("code", "=", self._code(code))] + self._domaine_builds(), limit=1)

    @staticmethod
    def _avec_piece(records, champ):
        """Ids of the records whose binary field holds something.

        Asked of ir.attachment rather than by reading the field: testing `build.short_video`
        would load the whole video just to learn whether it exists.
        """
        pieces = request.env["ir.attachment"].sudo().search_fetch(
            [("res_model", "=", records._name), ("res_field", "=", champ),
             ("res_id", "in", records.ids)], ["res_id"])
        return set(pieces.mapped("res_id"))

    def _contexte_cartes(self, builds):
        """What the shared card needs beyond the build: who already owns what, who has a box.

        One query for the whole shelf: `is_accessible_by` per card would search the members
        table once for every build.
        """
        partner = request.env.user.partner_id
        membres = request.env["besacraft.build.member"].sudo().search(
            [("build_id", "in", builds.ids), ("partner_id", "=", partner.id)])
        return {
            "acquis": set(membres.build_id.ids),
            "avec_boite": self._avec_piece(builds, "box_image"),
        }

    def _couche_apercu(self, couche, role):
        """One layer as the build page previews it: number, count, a few real blocks."""
        return {"sequence": couche.sequence, "block_count": couche.block_count, "role": role,
                "types": len(couche.line_ids), "lines": couche.line_ids[:8]}

    @http.route("/builds", type="http", auth="public", website=True,
                sitemap=_site_besacraft)
    def catalogue(self, serie=None, **kw):
        """The catalogue: every build of the site on one shelf, filtered in the browser."""
        if self._garde_site():
            return request.not_found()
        Build = request.env["besacraft.build"].sudo()
        publies = self._domaine_builds()
        builds = Build.search(publies)
        series = request.website._besacraft_series()
        # Le compteur de chaque filtre se lit sur la totalité, pas sur la sélection
        # courante : un filtre qui afficherait « 0 » une fois cliqué serait absurde.
        par_serie = {s.id: len(builds.filtered(lambda b, s=s: b.serie_id == s)) for s in series}
        valeurs = {
            "builds": builds, "series": series,
            "serie_active": serie if serie in series.mapped("code") else None,
            "total": len(builds), "par_serie": par_serie,
            "n_gratuits": len(builds.filtered(lambda b: b.enroll == "public")),
            "n_payants": len(builds.filtered(lambda b: b.enroll == "payment")),
            "barre_active": "catalogue",
        }
        valeurs.update(self._contexte_cartes(builds))
        return request.render("besacraft_builds.catalogue", valeurs)

    @http.route("/builds/<int:code>", type="http", auth="public", website=True,
                sitemap=_site_besacraft)
    def build(self, code, **kw):
        """A build's own page: the box, the short, what the tutorial holds, how to get it."""
        if self._garde_site():
            return request.not_found()
        build = self._build(code)
        if not build:
            return request.not_found()
        partner = request.env.user.partner_id
        couches = build.layer_ids
        apercu = []
        if couches:
            # Première, milieu, dernière : trois vraies couches de la notice, pas la notice.
            milieu = couches[(len(couches) + 1) // 2 - 1]
            roles = [(couches[0], "Première couche"), (milieu, "Couche du milieu"),
                     (couches[-1], "Dernière couche")]
            vus = []
            for couche, role in roles:
                if couche not in vus:
                    vus.append(couche)
                    apercu.append(self._couche_apercu(couche, role))
        voisins = request.env["besacraft.build"].sudo().search(
            [("serie_id", "=", build.serie_id.id), ("id", "!=", build.id)]
            + self._domaine_builds())
        voisins = sorted(voisins, key=lambda b: abs(int(b.code) - int(build.code)))[:4]
        voisins = request.env["besacraft.build"].sudo().browse(
            [b.id for b in sorted(voisins, key=lambda b: b.code)])
        valeurs = {
            "build": build, "main_object": build,
            "accessible": build.is_accessible_by(partner),
            "apercu": apercu, "voisins": voisins,
            "a_un_court": build.id in self._avec_piece(build, "short_video"),
            "barre_active": "catalogue",
            "produit": build.product_id,
        }
        valeurs.update(self._contexte_cartes(build | voisins))
        return request.render("besacraft_builds.build", valeurs)

    @http.route("/builds/<int:code>/court", type="http", auth="public", website=True,
                sitemap=False)
    def court(self, code, **kw):
        """The build's vertical short. Streamed by the core, which answers Range requests."""
        if self._garde_site():
            return request.not_found()
        build = self._build(code)
        if not build or build.id not in self._avec_piece(build, "short_video"):
            return request.not_found()
        return request.env["ir.binary"]._get_stream_from(
            build, "short_video", mimetype="video/mp4").get_response()

    @http.route("/t/<int:code>", type="http", auth="public", website=True,
                sitemap=_site_besacraft)
    def tuto(self, code, **kw):
        """A build's tutorial sheet. The URL carries the number without padding zeros."""
        if self._garde_site():
            return request.not_found()
        build = self._build(code)
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
        # L'aperçu d'un tuto payant : la couche 1 en clair, rien des suivantes que leur
        # numéro. Elle suffit à juger de la notice sans en livrer la suite.
        apercu = None
        masquees = []
        if not accessible and build.enroll == "payment" and build.layer_ids:
            apercu = self._couche_apercu(build.layer_ids[0], "Première couche")
            masquees = list(range(2, min(build.layer_count, 4) + 1))
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
            "apercu": apercu, "masquees": masquees,
            "produit": build.product_id,
        })

    def _serie_du_site(self, code):
        """The series behind /builds/serie/<code>, only if this site publishes it."""
        return request.website._besacraft_series().filtered(lambda s: s.code == code)[:1]

    @http.route("/builds/serie/<string:code>", type="http", auth="public", website=True,
                sitemap=_site_besacraft)
    def serie(self, code, **kw):
        """A series' page: who it is, its first builds, its latest episodes."""
        if self._garde_site():
            return request.not_found()
        serie = self._serie_du_site(code)
        if not serie:
            return request.not_found()
        Build = request.env["besacraft.build"].sudo()
        domaine = self._domaine_builds() + [("serie_id", "=", serie.id)]
        builds = Build.search(domaine, limit=8)
        episodes = request.env["besacraft.episode"].sudo().search(
            self._filtre_publie() + [("serie_id", "=", serie.id)])
        valeurs = {
            "serie": serie.sudo(), "builds": builds,
            "n_builds": Build.search_count(domaine),
            "episodes": episodes[:3], "n_episodes": len(episodes),
            "barre_active": serie.code,
        }
        valeurs.update(self._contexte_cartes(builds))
        return request.render("besacraft_builds.serie", valeurs)

    @http.route("/builds/serie/<string:code>/episodes", type="http", auth="public",
                website=True, sitemap=_site_besacraft)
    def episodes(self, code, **kw):
        """The series' episodes, laid out like a blog."""
        if self._garde_site():
            return request.not_found()
        serie = self._serie_du_site(code)
        if not serie:
            return request.not_found()
        episodes = request.env["besacraft.episode"].sudo().search(
            self._filtre_publie() + [("serie_id", "=", serie.id)])
        autorises = request.env["besacraft.build"].sudo().search(self._domaine_builds())
        vus = {e.id: e.build_ids & autorises for e in episodes}
        tous = autorises.browse()
        for v in vus.values():
            tous |= v
        valeurs = {
            "serie": serie.sudo(), "episodes": episodes, "vus": vus,
            "avec_boite": self._avec_piece(tous, "box_image"),
            "barre_active": serie.code,
        }
        return request.render("besacraft_builds.episodes", valeurs)

    @http.route("/besacraft/holo", type="http", auth="public", methods=["GET"],
                website=True, sitemap=False)
    def holo(self, code=None, **kw):
        """One build to draw as a hologram, and the site's figures.

        No 404 guard: the theme calls this from pages of any site, and a site with no series
        simply gets `build: null`. A fresh draw per load, hence no cache.
        """
        Build = request.env["besacraft.build"].sudo()
        site = self._site()
        series = site._besacraft_series()
        publies = (self._filtre_publie() + Build._domaine_site(site)) if series else None
        resultat = {"build": None, "stats": {"builds": 0, "blocs": 0, "series": len(series)}}
        if series:
            resultat["stats"]["builds"] = Build.search_count(publies)
            resultat["stats"]["blocs"] = sum(
                Build.search(publies).mapped("block_count"))
            domaine = publies + [("holo_data", "!=", False)]
            if code and str(code).isdigit():
                domaine.append(("code", "=", self._code(int(code))))
            ids = Build.search(domaine).ids
            if ids:
                build = Build.browse(random.choice(ids))
                donnees = json.loads(build.holo_data)
                resultat["build"] = {
                    "code": build.code, "nom": build.name,
                    "taille": donnees.get("taille"), "couches": donnees.get("couches"),
                    "url": "/builds/%d" % int(build.code),
                    "blocs": build.block_count, "couches_n": build.layer_count,
                    "serie": build.serie_id.name, "couleur": build.serie_id.color,
                }
        return request.make_json_response(
            resultat, headers=[("Cache-Control", "no-store")])

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
        if not build or not build.viewer_attachment_id or not build.is_shown_on(self._site()):
            return request.not_found()
        redirection = self._vers_le_produit(build)
        if redirection:
            return redirection
        piece = build.viewer_attachment_id
        contenu = base64.b64decode(piece.datas)
        # A long cache plus an ETag avoids shipping several megabytes on every layer change.
        # The ETag follows the CONTENT: the import refreshes the viewer by rewriting the same
        # attachment, and an ETag on its id kept browsers on the old viewer for a day.
        etag = '"%s-%s"' % (build.id, piece.checksum or piece.id)
        if request.httprequest.headers.get("If-None-Match") == etag:
            return request.make_response("", status=304, headers=[("ETag", etag)])
        return request.make_response(contenu, headers=[
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(contenu))),
            ("Cache-Control", "private, max-age=86400"),
            ("ETag", etag),
        ])

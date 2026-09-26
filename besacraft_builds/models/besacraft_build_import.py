from odoo import api, models
from odoo.exceptions import ValidationError


class BesacraftBuildImport(models.Model):
    _inherit = "besacraft.build"

    @api.model
    def import_depuis_buildplan(self, build_json, plan_json, code, serie_code):
        """JSON-RPC entry point: the same import, addressed by codes.

        `import_build_json` takes a besacraft.serie recordset and reads `.id` on it.
        Over JSON-RPC there are no recordsets -- a caller can only send an integer, and
        the first import of a build died on that. Resolving the series here also keeps
        the caller honest: it names the series the tutorial belongs to, and a name that
        matches nothing is refused instead of being filed under the wrong one.

        Returns the build's id and its series, so the caller can log what it did without
        a second round trip.
        """
        serie = self.env["besacraft.serie"].search([("code", "=", serie_code)], limit=1)
        if not serie:
            connues = self.env["besacraft.serie"].search([]).mapped("code")
            raise ValidationError(
                "Unknown series %r. Known series: %s."
                % (serie_code, ", ".join(sorted(connues)) or "none")
            )
        build = self.import_build_json(build_json, plan_json, code, serie)
        return {"id": build.id, "code": build.code, "name": build.name,
                "serie": serie.name, "layer_count": build.layer_count,
                "block_count": build.block_count,
                "website_id": build.website_id.id or False}

    @api.model
    def import_build_json(self, build_json, plan_json, code, serie):
        """Create or refresh a build from a decoded build.json. Returns the build.

        Quantities are copied as they are read. The editorial fields -- layer titles,
        instructions, notes -- are typed by hand afterwards and must survive a refresh,
        so layers are matched on their sequence rather than dropped and recreated.

        The counts shown to a reader are the ones the video announces, which are NOT
        build.json's: that file also counts the decor and the foundation layers sunk
        below ground level, which the build animation skips. plan.json carries the
        editorial truth; without it we import the whole file.
        """
        build = self.search([("code", "=", code)], limit=1)
        taille = build_json.get("size") or [0, 0, 0]
        depuis = (plan_json or {}).get("depuis", 0)
        couches = (build_json.get("layers") or [])[depuis:]
        total = (plan_json or {}).get(
            "total", sum(sum((c.get("counts") or {}).values()) for c in couches))
        # Le crédit voyage avec la structure : buildplan le pose dans build.json, l'import
        # le reprend tel quel. Une licence libre se respecte en citant, et citer à la main
        # une fois sur deux revient à ne pas citer.
        credits = build_json.get("credits") or {}
        valeurs = {
            # Le viewer, lui, garde TOUTES les couches : sans ce décalage sa couche 1 est
            # une fondation enterrée et la page montre des blocs que la 3D ne pose pas.
            "layer_offset": depuis,
            "block_count": total,
            "layer_count": len(couches),
            "size_x": taille[0], "size_y": taille[1], "size_z": taille[2],
            "source_author": credits.get("author") or "",
            "source_license": credits.get("license") or "",
            "source_url": credits.get("website") or "",
        }
        if build:
            build.write(valeurs)
        else:
            build = self.create(dict(valeurs, code=code, serie_id=serie.id,
                                     name=build_json.get("name") or code))

        items = build_json.get("items") or {}
        Layer = self.env["besacraft.build.layer"]
        for index, couche in enumerate(couches, start=1):
            counts = couche.get("counts") or {}
            existante = build.layer_ids.filtered(lambda l, i=index: l.sequence == i)
            lignes = [(5, 0, 0)] + [
                (0, 0, {"item_key": cle, "qty": qte,
                        "name_fr": (items.get(cle) or {}).get("name") or cle,
                        "mod": (items.get(cle) or {}).get("mod") or ""})
                for cle, qte in counts.items()
            ]
            couche_valeurs = {"block_count": sum(counts.values()), "line_ids": lignes}
            if existante:
                existante.write(couche_valeurs)
            else:
                Layer.create(dict(couche_valeurs, build_id=build.id, sequence=index))
        build.layer_ids.filtered(lambda l, n=len(couches): l.sequence > n).unlink()
        return build

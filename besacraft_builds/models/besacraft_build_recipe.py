from collections import Counter

from odoo import fields, models


class BesacraftBuildRecipe(models.Model):
    """The build's crafting recipes, as buildplan computed them in recipes.json.

    Stored as the file itself rather than as records: the trees are computed for the
    whole build by buildplan and only ever read back, and splitting them into models
    would mean a second source of truth to keep in step with the viewer's copy.
    """

    _inherit = "besacraft.build"

    recipe_data = fields.Json(
        "Recipes", copy=False,
        help="recipes.json as produced by buildplan: trees, raw_totals and items.")

    def _tuto_item(self, item_id):
        """Display name and icon of any item the recipes mention.

        Only inline data URIs are kept: `icon` is a path relative to the viewer's own
        folder and would 404 once served from the site.
        """
        self.ensure_one()
        item = ((self.recipe_data or {}).get("items") or {}).get(item_id) or {}
        icon = item.get("icon_data") or ""
        return {
            "id": item_id,
            "name": item.get("name") or item_id,
            "icon": icon if icon.startswith("data:image/") else False,
        }

    def _tuto_recipe_for(self, item_key):
        """One craft of this block, ready for the tutorial page, or None.

        The tree in recipes.json is sized for the whole build. A layer only needs to
        know how the block is made, so this returns the unit recipe: the station, what
        goes into one craft, and how many come out of it.
        """
        self.ensure_one()
        noeud = ((self.recipe_data or {}).get("trees") or {}).get(item_key)
        if not noeud:
            return None
        recette = noeud.get("recipe")
        if noeud.get("raw") or not recette:
            return {"raw": True, "hint": noeud.get("hint") or "",
                    "station": "", "station_icon": False, "yield": 0,
                    "inputs": [], "alternatives": []}

        if recette.get("grid"):
            # Counter keeps first-seen order, so ingredients read in grid order.
            comptes = Counter(cle for rangee in recette["grid"] for cle in rangee if cle)
            entrees = [dict(self._tuto_item(cle), count=n, fluid_mb=0)
                       for cle, n in comptes.items()]
        else:
            par_cle = {}
            for entree in recette.get("inputs") or []:
                cle = entree.get("id")
                if not cle:
                    continue
                ligne = par_cle.setdefault(
                    cle, dict(self._tuto_item(cle), count=0, fluid_mb=0))
                ligne["count"] += entree.get("count") or 0
                ligne["fluid_mb"] += entree.get("fluid_mb") or 0
            entrees = list(par_cle.values())

        station = recette.get("station_item")
        return {
            "raw": False,
            "hint": noeud.get("hint") or "",
            "station": recette.get("station") or "",
            "station_icon": self._tuto_item(station)["icon"] if station else False,
            "yield": recette.get("yield") or 1,
            "inputs": entrees,
            "alternatives": [a for a in noeud.get("alternatives") or [] if a],
        }

    def _tuto_layer_recipes(self, layer):
        """The layer's blocks that have an entry in the recipes, in the layer's order."""
        self.ensure_one()
        resultat = []
        for ligne in layer.line_ids:
            recette = self._tuto_recipe_for(ligne.item_key)
            if recette:
                resultat.append({"line": ligne, "recipe": recette})
        return resultat

    def _tuto_raw_materials(self):
        """What to gather for the whole build, largest quantity first."""
        self.ensure_one()
        totaux = (self.recipe_data or {}).get("raw_totals") or {}
        matieres = [dict(self._tuto_item(cle), count=n) for cle, n in totaux.items() if n]
        return sorted(matieres, key=lambda m: (-m["count"], m["name"]))

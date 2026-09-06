#!/usr/bin/env python3
"""Charge les vignettes du catalogue depuis les jars, par JSON-RPC.

Les textures ne sont pas livrees avec le module : Conquest Reforged est sous
« tous droits reserves » et les textures de Mojang ne sont pas plus libres, si
bien que les versionner serait fautif. Elles s'importent depuis les jars que
l'instance possede — ce qui est un usage, pas une redistribution.

Un bloc n'a pas « une » texture : un escalier en a trois faces. On suit son
modele, parents compris, et on retient la face qui le represente le mieux dans
une liste.

    import_images.py --instance alusage \\
        --jar ~/.../ConquestReforged-neoforge-1.21.1-1.7.0.jar \\
        --jar ~/.../minecraft-resources.jar --espace conquest,minecraft
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import pathlib
import sys
import zipfile

ORDRE_FACES = ("side", "all", "texture", "top", "front", "0", "particle", "end", "bottom")


def resoudre_textures(z, espace, chemin, vus=None):
    vus = vus or set()
    if chemin in vus or len(vus) > 8:
        return {}
    vus.add(chemin)
    ns, _, rel = chemin.partition(":")
    if not rel:
        ns, rel = espace, chemin
    try:
        m = json.loads(z.read(f"assets/{ns}/models/{rel}.json"))
    except (KeyError, json.JSONDecodeError):
        return {}
    t = {}
    if m.get("parent"):
        t.update(resoudre_textures(z, espace, m["parent"], vus))
    t.update(m.get("textures", {}))
    return t


def vignette(donnees: bytes, taille: int = 16) -> bytes:
    from PIL import Image
    im = Image.open(io.BytesIO(donnees)).convert("RGBA")
    if im.height > im.width:          # texture animee : les trames sont empilees
        im = im.crop((0, 0, im.width, im.width))
    if im.size != (taille, taille):
        im = im.resize((taille, taille), Image.NEAREST)
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", default="alusage")
    ap.add_argument("--jar", action="append", required=True)
    ap.add_argument("--espace", default="conquest,minecraft",
                    help="espaces de noms, dans l'ordre des jars")
    ap.add_argument("--taille", type=int, default=16)
    ap.add_argument("--lot", type=int, default=200, help="ecritures par appel")
    ap.add_argument("--simuler", action="store_true")
    args = ap.parse_args()

    sys.path.insert(0, str(pathlib.Path.home()
                           / "dev/PAO/plugins/pao-core/skills/odoo-jsonrpc/scripts"))
    from credentials import load_odoo_env
    from odoo_client import OdooClient

    c = OdooClient.from_env(load_odoo_env(args.instance))
    items = c.search_read("besacraft.item", [], ["id", "identifiant"], limit=0)
    par_ident = {i["identifiant"]: i["id"] for i in items}
    print(f"{len(par_ident)} blocs au catalogue")

    espaces = args.espace.split(",")
    trouvees: dict[int, str] = {}
    for chemin, espace in zip(args.jar, espaces):
        z = zipfile.ZipFile(chemin)
        prefixe = f"assets/{espace}/models/item/"
        modeles = [n for n in z.namelist() if n.startswith(prefixe) and n.endswith(".json")]
        print(f"{pathlib.Path(chemin).name} ({espace}) : {len(modeles)} objets")
        for n, nom in enumerate(modeles, 1):
            cle = nom.rsplit("/", 1)[1][:-5]
            oid = par_ident.get(f"{espace}:{cle}")
            if not oid:
                continue
            textures = resoudre_textures(z, espace, f"{espace}:item/{cle}")
            ref = next((textures[k] for k in ORDRE_FACES
                        if textures.get(k) and not textures[k].startswith("#")), None)
            if ref is None:
                ref = next((v for v in textures.values() if v and not v.startswith("#")), None)
            if ref is None:
                continue
            ns, _, rel = ref.partition(":")
            if not rel:
                ns, rel = espace, ref
            try:
                brut = z.read(f"assets/{ns}/textures/{rel}.png")
            except KeyError:
                continue
            trouvees[oid] = base64.b64encode(vignette(brut, args.taille)).decode()
            if n % 2000 == 0:
                print(f"  … {n}", flush=True)

    print(f"\n{len(trouvees)} vignettes prêtes")
    if args.simuler:
        print("simulation : rien n'est écrit")
        return

    # Une écriture par bloc serait vingt mille appels ; on regroupe les blocs qui
    # partagent la même vignette, ce qui est fréquent — un escalier, une dalle et un
    # mur du même matériau montrent la même face.
    par_image: dict[str, list[int]] = {}
    for oid, img in trouvees.items():
        par_image.setdefault(img, []).append(oid)
    print(f"{len(par_image)} vignettes distinctes pour {len(trouvees)} blocs")

    ecrits = 0
    for img, ids in par_image.items():
        for i in range(0, len(ids), args.lot):
            lot = ids[i:i + args.lot]
            c.write("besacraft.item", lot, {"image_1920": img})
            ecrits += len(lot)
            print(f"  {ecrits}/{len(trouvees)}", end="\r", flush=True)
    print(f"\n{ecrits} blocs mis à jour")


if __name__ == "__main__":
    main()

====================
Besacraft — Wardrobe
====================

Accounts, skins and capes for the Besacraft players. A player asks for an account
from inside the game, an administrator validates the request, and the player then
manages a wardrobe of skins and capes from the portal. The game reads the result
through CustomSkinLoader.

Depends on ``besacraft_minecraft_api``, whose Mojang sign-in (``/mc/v1/defi`` and
``/mc/v1/session``) is reused as is: the UUID of a player is never trusted unless
Mojang vouched for it.

Routes
======

``GET /mc/v1/vestiaire/moi``
    The signed-in player's pseudo, active skin and worn cape. For an account that is
    not validated yet it answers ``403 compte_non_valide`` with a request ``code``
    and the ``url`` of the request form.

``GET|POST /vestiaire/demande?code=...``
    The public account request form. The code is twelve characters, valid for 24
    hours and tied to the UUID Mojang vouched for. Players under 15 must give a
    parent's email address.

``GET /csl/<pseudo>.json`` and ``GET /csl/textures/<hash>``
    The CustomSkinAPI format read by CustomSkinLoader. Only validated accounts are
    served, and only their active skin and worn cape; anything else is a plain 404.

``GET /my/vestiaire``
    The portal page (a "Wardrobe" card appears in ``/my`` for validated players):
    upload, use and delete skins, wear one of the capes they own, or none. Every
    action only touches the logged-in player's own records.

Image rules
===========

PNG only, 1 MB at most. A skin is 64×64 or 64×32 pixels. A cape or an elytra is
64×32 pixels or a multiple of it (width a multiple of 64, width twice the height).

Capes are gifts: an administrator offers them from the contacts list. A player can
only wear a cape they own.

CustomSkinLoader
================

Add this entry to the ``loadlist`` of ``CustomSkinLoader/CustomSkinLoader.json`` in
the modpack, before the other sources:

.. code-block:: json

    {
        "name": "Besacraft",
        "type": "CustomSkinAPI",
        "root": "https://<your-odoo-domain>/csl/"
    }

Deployment
==========

``proxy_mode = True`` **is required** when Odoo sits behind a reverse proxy, as for
``besacraft_minecraft_api``. The open endpoints are rate-limited per client IP, and
without it every player shares the proxy's address: the ceiling then becomes global.
Make sure the proxy sets ``X-Forwarded-For`` itself rather than passing on whatever
the client sent.

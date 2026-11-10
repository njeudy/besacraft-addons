====================
Besacraft — Wardrobe
====================

Accounts, skins, capes, cosmetics, emotes and points for the Besacraft players. A player asks for an account
from inside the game, an administrator validates the request, and the player then
manages a wardrobe of skins and capes from the portal. The game reads the result
through CustomSkinLoader.

Depends on ``besacraft_minecraft_api``, whose Mojang sign-in (``/mc/v1/defi`` and
``/mc/v1/session``) is reused as is: the UUID of a player is never trusted unless
Mojang vouched for it.

Routes
======

``GET /mc/v1/vestiaire/moi``
    The signed-in player's pseudo, active skin, worn cape, ``points``, the codes they
    own (``possede``), their ``tenue`` and the eight slots of their emote ``roue``,
    and the ``nouvelles`` (gains and gifts) not yet told in game, which this call
    marks as told. For an account that is not validated yet it answers
    ``403 compte_non_valide`` with a request ``code`` and the ``url`` of the request
    form; the other wardrobe routes do the same.

``GET /mc/v1/vestiaire/catalogue``
    What the player owns plus what is for sale: ``code``, ``genre``, ``nom``,
    ``emplacement``, ``prix``, ``de_base``, ``possede``.

``PUT /mc/v1/vestiaire/equipement`` ``{tenue: [codes], roue: [8 codes or null]}``
    Saves the outfit and the wheel. Unowned codes, a second item on a slot and a
    head under a hat are dropped silently; the answer is what was kept.
    An outfit entry may carry the game's settings after the code
    (``chapeau_sorcier|noir||d|2``: colour, side, back, height). Only the code is
    checked; the suffix (60 characters at most, otherwise ignored) is kept as is and
    given back by ``moi``. A code sent bare forgets its settings. Colours are free:
    nothing about them is sold.

``POST /mc/v1/vestiaire/achat`` ``{code, prix}``
    Buys an item at the price the player saw. ``409`` with ``deja_possede``,
    ``solde_insuffisant`` or ``prix_change`` (and the current ``points`` and
    ``prix``), ``404`` when the item is not for sale. The balance is read under a
    row lock on the player, so two clicks never spend twice.

``POST /mc/v1/serveur/gain`` ``{uuid, motif, reference, code?}``
    For our Minecraft servers only, with a server key (menu Wardrobe > Server
    keys, only the hash is kept). ``motif`` is ``mission`` or ``defi``; the amount
    comes from the points scale, never from the caller. Replayable: the same player,
    reason and reference is credited once (``deja_credite``).

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

Cosmetics, emotes and points
============================

The 3D models and animations ship in the mod's jar; Odoo holds the rights, keyed
by the code of the jar's ``catalogue.json``. Everything the v50 pack shipped is
seeded as *owned by everyone*, so nobody loses what they had. An item is owned
when it is published and either owned by everyone, bought, or given.

Points live in a ledger (``besacraft.vestiaire.mouvement``) that is never edited
nor deleted: a mistake is fixed with a correction line. Administrators give
points, cosmetics, emotes and capes with the *Give* action on a contact.

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

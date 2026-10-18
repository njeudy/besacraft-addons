=========================
Besacraft — Minecraft API
=========================

The read API the in-game notice mod talks to. Six routes under ``/mc/v1``, plain
HTTP and plain JSON, no JSON-RPC: the client is a Minecraft mod, not a browser.

How a player signs in
=====================

#. ``POST /mc/v1/defi`` hands out a one-shot ``server_id``.
#. The mod makes the game client join that server id, which makes Mojang vouch for
   the session.
#. ``POST /mc/v1/session`` asks Mojang whether this player really answered that
   challenge. Mojang has the last word: the UUID the mod announces is never trusted.
#. The certified UUID is matched against ``res.partner.minecraft_uuid``, and a token
   valid for thirty days comes back.

No password ever reaches Odoo, and a stolen UUID is worthless: only the player who
holds the Mojang session can answer the challenge.

What the lock protects
======================

``/mc/v1/build/<code>/couche/<n>`` is the only route that lets block types out, and
it only serves a layer the player has already reached, or the next one. Membership
is the key, and membership comes from a confirmed sale order or from joining a free
build on the website.

The hologram served publicly by ``/besacraft/holo`` carries positions without block
types; the full plan lives in an attachment that no public route serves.

Deployment
==========

``proxy_mode = True`` **is required** when Odoo sits behind a reverse proxy. The
open endpoints are rate-limited per client IP, and without it every player shares
the proxy's address: the ceiling then becomes global, and the twenty-first player of
the minute cannot sign in. Make sure the proxy sets ``X-Forwarded-For`` itself
rather than passing on whatever the client sent.

The ceiling is per worker and held in memory, on purpose: it stops a runaway client
or a clumsy script, not a distributed attack. That belongs at the reverse proxy.

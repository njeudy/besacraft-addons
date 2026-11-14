"""Make `minecraft_uuid` a key that names exactly one contact.

Two things had to be true before the uniqueness constraint could be added, and
neither was. The UUID was stored in playerdb.co's dashed form while the game
authenticates on Mojang's undashed one, so the two halves of the identity never
matched. And `set_minecraft_player_info` resolved on the whole recordset instead of
each contact, so every contact of a multi-record call was written the first one's
UUID -- fourteen different players shared one identity on the development base.

A duplicated UUID is cleared on *every* contact of its group, not on all but one:
we have no way to tell which of them really owns it, and keeping an arbitrary one
would leave exactly the impersonation this constraint exists to prevent. Those
players re-link from their portal account, which costs them one form and is loud.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("UPDATE res_partner SET minecraft_uuid = NULL WHERE minecraft_uuid = ''")
    cr.execute("""
        UPDATE res_partner
           SET minecraft_uuid = lower(replace(minecraft_uuid, '-', ''))
         WHERE minecraft_uuid IS NOT NULL
           AND minecraft_uuid <> lower(replace(minecraft_uuid, '-', ''))
    """)
    _logger.info("Minecraft UUIDs normalised: %s rows", cr.rowcount)
    cr.execute("""
        SELECT minecraft_uuid, array_agg(id ORDER BY id), array_agg(minecraft_login)
          FROM res_partner
         WHERE minecraft_uuid IS NOT NULL
      GROUP BY minecraft_uuid
        HAVING count(*) > 1
    """)
    doublons = cr.fetchall()
    for uuid, ids, logins in doublons:
        _logger.warning(
            "Minecraft UUID %s was shared by %s contacts (%s): cleared on all of them, "
            "they have to link their account again.", uuid, len(ids), ", ".join(
                filter(None, logins)) or "no login")
        cr.execute("UPDATE res_partner SET minecraft_uuid = NULL WHERE id IN %s",
                   (tuple(ids),))

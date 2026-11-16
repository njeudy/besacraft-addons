"""What a deployed armour lets its wearer do, decided in Odoo.

Two levels: the armour piece says what it can do at most, the player's ownership says what
this player has unlocked. In game, the piece gives the intersection. An empty list on either
side means "everything", so pieces and ownerships created before this feature keep it all.
"""

# The order is the one shown to the player and sent to the game.
FONCTIONS = ("vol", "phares", "hud", "scanner", "lunettes_create", "chantier")


def effectives(sait, debloque):
    """The functions a piece gives this player, in the reference order.

    :param sait: codes the piece can do, empty for all
    :param debloque: codes the player unlocked on it, empty for all
    """
    sait = set(sait) or set(FONCTIONS)
    debloque = set(debloque) or set(FONCTIONS)
    return [f for f in FONCTIONS if f in sait and f in debloque]

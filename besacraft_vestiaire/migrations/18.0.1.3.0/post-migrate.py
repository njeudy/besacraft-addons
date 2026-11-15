"""Mark the armours of PAO and Zoé as deployable armour pieces.

Their records come from catalogue data loaded with noupdate: the new field would stay empty on
an existing database. The game reads the same codes from its catalogue.
"""
import logging

_logger = logging.getLogger(__name__)

PIECES = {
    "pao_armure": "plastron", "pao_casque_armure": "casque",
    "pao_armure_neon": "plastron", "pao_casque_neon": "casque",
    "zoe_armure": "plastron", "zoe_casque_armure": "casque",
    "zoe_armure_neon": "plastron", "zoe_casque_neon": "casque",
}


def migrate(cr, version):
    if not version:
        return
    for code, piece in PIECES.items():
        cr.execute("UPDATE besacraft_vestiaire_cosmetique SET piece_armure = %s"
                   " WHERE code = %s AND piece_armure IS NULL", [piece, code])
    _logger.info("besacraft_vestiaire: armour pieces marked on %s codes", len(PIECES))

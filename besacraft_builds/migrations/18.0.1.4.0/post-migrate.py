"""Hand each build's site over to its series.

A build used to be filed under one site (`website_id`); the series now says where its
builds show. Each series inherits the sites its builds were on, so nothing a reader could
see before disappears with the upgrade. Builds filed under no site were shown on the site
flagged as Besacraft, so they bring that one.

The column is read in SQL: the field is gone from the model, and Odoo only drops the
column once every module is loaded, after this script has run.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not column_exists(cr, "besacraft_build", "website_id"):
        return
    cr.execute("""
        SELECT serie_id, array_agg(DISTINCT website_id)
          FROM besacraft_build GROUP BY serie_id
    """)
    par_serie = dict(cr.fetchall())
    besacraft = []
    if column_exists(cr, "website", "besacraft_enabled"):
        cr.execute("SELECT id FROM website WHERE besacraft_enabled")
        besacraft = [r[0] for r in cr.fetchall()]

    env = api.Environment(cr, SUPERUSER_ID, {})
    for serie in env["besacraft.serie"].browse(list(par_serie)).exists():
        ids = set(par_serie[serie.id])
        if None in ids:
            ids.discard(None)
            ids.update(besacraft)
        serie.website_ids = [(4, i) for i in ids]
        _logger.info("besacraft.serie %s: published on websites %s",
                     serie.code, sorted(ids))

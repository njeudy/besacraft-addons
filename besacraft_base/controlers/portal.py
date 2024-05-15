import logging
from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request

_logger = logging.getLogger(__name__)


CustomerPortal.OPTIONAL_BILLING_FIELDS.append('minecraft_login')
CustomerPortal.OPTIONAL_BILLING_FIELDS.append('minecraft_uuid')

class CustomerPortal(CustomerPortal):

    @http.route(['/my/account'], type='http', auth="user", website=True)
    def account(self, **kw):
        partner = request.env.user.partner_id

        _logger.debug('I AM IN: %s' % kw)
        if partner.minecraft_uuid or kw['minecraft_login']:
            na_fields = ['street', 'phone', 'zipcode', 'city']
            for field in na_fields:
                if not kw.get(field, False):
                    kw[field] = 'NA'
        res = super(CustomerPortal, self).account(**kw)
        # Récupérer les informations du joueur Minecraft
        partner.set_minecraft_player_info()
        return res
import logging
from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request

_logger = logging.getLogger(__name__)


class CustomerPortal(CustomerPortal):

    def _get_optional_fields(self):
        """This method is there so that we can override the optional fields"""
        res = super(CustomerPortal, self)._get_optional_fields()
        # Add minecraft fields
        res.extend(
            ["minecraft_login", "minecraft_uuid", "minecraft_skin", "minecraft_head"]
        )
        return res

    @http.route(["/my/account"], type="http", auth="user", website=True)
    def account(self, **kw):
        partner = request.env.user.partner_id

        _logger.debug("I AM IN: %s" % kw)
        if partner.minecraft_uuid or kw.get("minecraft_login", False):
            na_fields = ["street", "phone", "zipcode", "city"]
            for field in na_fields:
                if not kw.get(field, False):
                    kw[field] = "NA"
        res = super(CustomerPortal, self).account(**kw)
        # Récupérer les informations du joueur Minecraft
        partner.set_minecraft_player_info()
        return res

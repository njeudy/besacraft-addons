import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    minecraft_login = fields.Char(string="Minecraft Login")
    minecraft_uuid = fields.Char(string="Minecraft UUID")
    minecraft_skin = fields.Binary(string="Minecraft Skin")

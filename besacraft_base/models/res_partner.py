import base64
import logging
import requests

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    minecraft_login = fields.Char(string="Minecraft Login")
    minecraft_uuid = fields.Char(string="Minecraft UUID")
    minecraft_skin = fields.Binary(string="Minecraft Skin")
    minecraft_head = fields.Binary(string="Minecraft Head")

    def get_minecraft_player_info(self):
        for partner in self:
            username = partner.minecraft_login
            if username:
                url = f"https://playerdb.co/api/player/minecraft/{username}"
                try:
                    response = requests.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        if data['code'] == 'player.found':
                            player_info = data['data']['player']
                            _logger.debug(player_info)
                            return player_info
                        else:
                            return {'error': 'Player not found'}
                    else:
                        return {'error': f"Failed to connect to API, status code: {response.status_code}"}
                except Exception as e:
                    return {'error': str(e)}
    
    def set_minecraft_player_info(self):
        for partner in self:
            minecraft_info = self.get_minecraft_player_info()
            if minecraft_info and minecraft_info.get('username', False):
                _logger.debug("SET MINECRAFT INFOS %s" % minecraft_info)
                partner.write({
                    'minecraft_uuid': minecraft_info.get('id', False),
                    'minecraft_skin': partner.set_image_from_url("https://crafthead.net/armor/body/%s" % minecraft_info.get('id', False)),
                    'minecraft_head': partner.set_image_from_url(minecraft_info.get('avatar', False)),
                })

    def set_image_from_url(self, image_url):
        try:
            # Télécharger l'image
            response = requests.get(image_url)
            if response.status_code == 200:
                # Encoder l'image en base64
                image_base64 = base64.b64encode(response.content)
                # Enregistrer l'image dans le champ image_1920
                return image_base64
            else:
                raise Exception(f"Failed to download image. Status code: {response.status_code}")
        except Exception as e:
            raise Exception(f"Error in set_image_from_url: {str(e)}")
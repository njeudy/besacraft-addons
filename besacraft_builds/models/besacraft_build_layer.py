from odoo import fields, models


class BesacraftBuildLayer(models.Model):
    """One layer of a build. Its title and instruction are written by hand afterwards;
    everything else comes from build.json."""

    _name = "besacraft.build.layer"
    _description = "Build Layer"
    _order = "build_id, sequence"

    build_id = fields.Many2one("besacraft.build", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(required=True)
    title = fields.Char(translate=True, help='Editorial title, e.g. "Gallery and lintels".')
    instruction = fields.Text(translate=True)
    note = fields.Text(translate=True, help="Warning shown next to the layer.")
    block_count = fields.Integer(help="From build.json. Never recomputed.")
    iso_image = fields.Image("Isometric View")
    plan_image = fields.Image("Top View")
    line_ids = fields.One2many("besacraft.build.layer.line", "layer_id")


class BesacraftBuildLayerLine(models.Model):
    """One block type to place in a layer, with the quantity read from build.json."""

    _name = "besacraft.build.layer.line"
    _description = "Build Layer Block"
    _order = "layer_id, qty desc, name_fr"

    layer_id = fields.Many2one("besacraft.build.layer", required=True, ondelete="cascade", index=True)
    item_key = fields.Char(required=True, index=True, help='Game key, e.g. "minecraft:oak_log".')
    name_fr = fields.Char("Name", translate=True)
    mod = fields.Char()
    qty = fields.Integer(required=True)
    icon = fields.Image(max_width=64, max_height=64)

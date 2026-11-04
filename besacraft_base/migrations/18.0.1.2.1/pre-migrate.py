"""Delete the website form view that showed besacraft_enabled.

The field and its view left the module together, but Odoo only removes an
obsolete view once every module is loaded. Until then the view is still
inherited, so validating any other extension of the website form fails on a
field that no longer exists.
"""


def migrate(cr, version):
    cr.execute("""
        DELETE FROM ir_ui_view
         WHERE id IN (SELECT res_id FROM ir_model_data
                       WHERE module = 'besacraft_base'
                         AND name = 'view_website_form_besacraft'
                         AND model = 'ir.ui.view')
    """)
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'besacraft_base'
           AND name = 'view_website_form_besacraft'
    """)

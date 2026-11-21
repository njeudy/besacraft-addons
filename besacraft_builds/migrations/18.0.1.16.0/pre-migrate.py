"""The builds project page setting is gone.

Its settings view is dropped before the module loads: left in place until the end of the
update, it would still name the removed field while the settings form is rebuilt.
"""


def migrate(cr, version):
    cr.execute("""
        DELETE FROM ir_ui_view
         WHERE id IN (SELECT res_id FROM ir_model_data
                       WHERE module = 'besacraft_builds'
                         AND name = 'res_config_settings_view_form_besacraft'
                         AND model = 'ir.ui.view')
    """)
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'besacraft_builds'
           AND name = 'res_config_settings_view_form_besacraft'
    """)

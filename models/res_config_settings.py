import os

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Local backup
    abackup_local_backup = fields.Boolean(string="Backup to local machine",
                                             config_parameter='abackup_local_backup')
    abackup_local_path = fields.Char(string="Backup path",
                                        config_parameter='abackup_local_path')
    abackup_local_cleanup = fields.Boolean(string="Delete old local backups",
                                              config_parameter='abackup_local_cleanup')
    abackup_local_cleanup_itv_number = fields.Integer(string='Clean up limit',
                                                         required=True,
                                                         default=1,
                                                         config_parameter='abackup_local_cleanup_itv_number')
    abackup_local_cleanup_itv_type = fields.Selection(string='Clean up limit Unit',
                                                         default='weeks',
                                                         config_parameter='abackup_local_cleanup_itv_type',
                                                         selection=[('weeks', 'Weeks'),
                                                                    ('months', 'Months')], )

    # Google Drive backup
    abackup_gdrive_backup = fields.Boolean(string='Back up to Google Drive',
                                              config_parameter='abackup_gdrive_backup')
    abackup_gdrive_auth_code = fields.Char(string='Authorization Code',
                                              config_parameter='abackup_gdrive_auth_code')
    abackup_gdrive_client_id = fields.Char(string='Client ID',
                                              config_parameter='abackup_gdrive_client_id')
    abackup_gdrive_client_secret = fields.Char(string='Client secret',
                                                  config_parameter='abackup_gdrive_client_secret')
    abackup_gdrive_location = fields.Char(string="Folder ID",
                                             config_parameter='abackup_gdrive_location')

    abackup_gdrive_cleanup = fields.Boolean(string="Delete old backups on Google Drive",
                                               config_parameter='abackup_gdrive_cleanup')

    abackup_gdrive_cleanup_itv_number = fields.Integer(string='Clean up limit',
                                                          required=True,
                                                          default=1,
                                                          config_parameter='abackup_gdrive_cleanup_itv_number')
    abackup_gdrive_cleanup_itv_type = fields.Selection(string='Clean up limit unit',
                                                          default='weeks',
                                                          config_parameter='abackup_gdrive_cleanup_itv_type',
                                                          selection=[('weeks', 'Weeks'),
                                                                     ('months', 'Months')], )

    def _compute_gdrive_uri(self):
        return self.env['odoo_addon_auto_backup.google_drive'].get_user_redirect_url()

    abackup_gdrive_uri = fields.Char(string='URI',
                                        help="The URL to generate the authorization code from Google",
                                        default=_compute_gdrive_uri)

    # Cronjob
    abackup_interval_number = fields.Integer(string='Back up interval',
                                                required=True,
                                                default=1,
                                                config_parameter='abackup_interval_number')
    abackup_interval_type = fields.Selection(string='Interval Unit',
                                                default='days',
                                                config_parameter='abackup_interval_type',
                                                selection=[('hours', 'Hours'),
                                                           ('days', 'Days'),
                                                           ('weeks', 'Weeks'),
                                                           ('months', 'Months')], )

    def set_values(self):
        # Validate local path
        if self.abackup_local_backup and (
                not self.abackup_local_path or not os.access(self.abackup_local_path, os.W_OK)):
            raise ValidationError(_("The specified local path is not writable."))

        # Validate Google Drive info
        if self.abackup_gdrive_backup and (
                not self.abackup_gdrive_client_id or not self.abackup_gdrive_client_secret):
            raise ValidationError(_("You must set up Client ID and Client Secret to use Google Drive backup."))

        # Validate interval
        if not self.abackup_interval_number or self.abackup_interval_number <= 0 or not self.abackup_interval_type:
            raise ValidationError(_("Please set a correct backup interval."))

        # Super
        super(ResConfigSettings, self).set_values()

        # Set up cronjob
        cronjob = self.env.ref('odoo_addon_auto_backup.ir_cron_database_backup', raise_if_not_found=False)
        if self.abackup_local_backup or self.abackup_gdrive_backup:
            cronjob.update({
                'active': True,
                'interval_number': self.abackup_interval_number,
                'interval_type': self.abackup_interval_type
            })
        else:
            cronjob.active = False

    def action_setup_abackup_auth_code(self):
        self.ensure_one()
        template = self.env.ref('odoo_addon_auto_backup.gdrive_auth_code_wizard')
        return {
            'name': _('Set up refresh token'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.config.settings',
            'views': [(template.id, 'form')],
            'target': 'new',
        }

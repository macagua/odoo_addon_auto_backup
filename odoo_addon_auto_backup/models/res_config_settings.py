import os

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Local backup
    abackup_local_backup = fields.Boolean(string="Backup to local machine",
                                          config_parameter='abackup_local_backup',
                                          help='Automatically generated backup files will be saved to your local'
                                               'machine (server). You will need to set a local path to save the'
                                               'file in the field below.')
    abackup_local_path = fields.Char(string="Backup path",
                                     config_parameter='abackup_local_path',
                                     help='Backup files will be saved to this location on your local machine.')
    abackup_local_cleanup = fields.Boolean(string="Delete old local backups",
                                           config_parameter='abackup_local_cleanup',
                                           help='Automatically remove old backup files saved on your local machine.'
                                                'The limit can be set using the interval field below.')
    abackup_local_cleanup_itv_number = fields.Integer(string='Clean up limit',
                                                      required=True,
                                                      default=1,
                                                      config_parameter='abackup_local_cleanup_itv_number',
                                                      help='The limit for which old backups will be kept.')
    abackup_local_cleanup_itv_type = fields.Selection(string='Clean up limit Unit',
                                                      default='week(s)',
                                                      config_parameter='abackup_local_cleanup_itv_type',
                                                      selection=[('week(s)', 'Week(s)'),
                                                                 ('month(s)', 'Month(s)')], )

    # Google Drive backup
    abackup_gdrive_backup = fields.Boolean(string='Back up to Google Drive',
                                           config_parameter='abackup_gdrive_backup',
                                           help='Automatically generated backup files will be saved to a Google'
                                                'Drive folder that you specify. You will need to set up your own Google'
                                                'client ID and client secret to use this feature.')
    abackup_gdrive_auth_code = fields.Char(string='Authorization Code',
                                           config_parameter='abackup_gdrive_auth_code',
                                           help='You should use the automatically generated URL to get an authorization '
                                                'code. You can also manually fill the code in this field if you already'
                                                'obtained it.')
    abackup_gdrive_client_id = fields.Char(string='Client ID',
                                           config_parameter='abackup_gdrive_client_id')
    abackup_gdrive_client_secret = fields.Char(string='Client secret',
                                               config_parameter='abackup_gdrive_client_secret')
    abackup_gdrive_location = fields.Char(string="Folder ID",
                                          config_parameter='abackup_gdrive_location',
                                          help='Backup files will be saved to the folder with this ID on'
                                               'your Google Drive.')

    abackup_gdrive_cleanup = fields.Boolean(string="Delete old backups on Google Drive",
                                            config_parameter='abackup_gdrive_cleanup',
                                            help='Automatically remove old backup files saved in the specified folder '
                                                 'on your Google Drive. The limit can be set using the interval field'
                                                 'below.')

    abackup_gdrive_cleanup_itv_number = fields.Integer(string='Clean up limit',
                                                       required=True,
                                                       default=1,
                                                       config_parameter='abackup_gdrive_cleanup_itv_number',
                                                       help='The limit for which old backups will be kept.')
    abackup_gdrive_cleanup_itv_type = fields.Selection(string='Clean up limit unit',
                                                       default='week(s)',
                                                       config_parameter='abackup_gdrive_cleanup_itv_type',
                                                       selection=[('week(s)', 'Week(s)'),
                                                                  ('month(s)', 'Month(s)')], )

    abackup_gdrive_fail = fields.Boolean(config_parameter='abackup_gdrive_fail', default=False)

    def _compute_gdrive_uri(self):
        return self.env['odoo_addon_auto_backup.google_drive'].get_user_redirect_url(self.abackup_gdrive_client_id)

    abackup_gdrive_uri = fields.Char(string='URI',
                                     help="The URL to generate the authorization code from Google",
                                     default=_compute_gdrive_uri)

    # Cronjob
    abackup_interval_number = fields.Integer(string='Back up interval',
                                             required=True,
                                             default=1,
                                             config_parameter='abackup_interval_number',
                                             help='The frequency that the backup job will run.')
    abackup_interval_type = fields.Selection(string='Interval Unit',
                                             default='days',
                                             config_parameter='abackup_interval_type',
                                             selection=[('hours', 'Hour(s)'),
                                                        ('days', 'Day(s)'),
                                                        ('weeks', 'Week(s)'),
                                                        ('months', 'Month(s)')], )

    @api.onchange('abackup_gdrive_client_id')
    def _onchange_gdrive_uri(self):
        self.abackup_gdrive_uri = self._compute_gdrive_uri()

    @api.onchange('abackup_gdrive_backup')
    def _onchange_gdrive_backup(self):
        if not self.abackup_gdrive_backup:
            self.abackup_gdrive_cleanup = False

    @api.onchange('abackup_local_backup')
    def _onchange_local_backup(self):
        if not self.abackup_local_backup:
            self.abackup_local_cleanup = False

    def set_values(self):
        # Validate local path
        if self.abackup_local_backup:
            if not self.abackup_local_path or not os.access(self.abackup_local_path, os.W_OK):
                raise ValidationError(_("The specified local path does not exist, or is not writable."))
            # Standardize local path
            if self.abackup_local_path[-1] != '/':
                self.abackup_local_path += '/'

        # Validate Google Drive info
        if self.abackup_gdrive_backup and (
                not self.abackup_gdrive_client_id or not self.abackup_gdrive_client_secret):
            raise ValidationError(_("You must set up Client ID and Client Secret to use Google Drive backup."))

        # Validate back up interval
        if not self.abackup_interval_number or self.abackup_interval_number <= 0 or not self.abackup_interval_type:
            raise ValidationError(_("Please set a correct backup interval."))

        # Validate local clean up interval
        if self.abackup_local_cleanup and (
                not self.abackup_local_cleanup_itv_number
                or self.abackup_local_cleanup_itv_number <= 0
                or not self.abackup_local_cleanup_itv_type):
            raise ValidationError(_("Please set a correct GDrive cleanup interval."))

        # Validate GDrive clean up interval
        if self.abackup_gdrive_cleanup and (
                not self.abackup_gdrive_cleanup_itv_number
                or self.abackup_gdrive_cleanup_itv_number <= 0
                or not self.abackup_gdrive_cleanup_itv_type):
            raise ValidationError(_("Please set a correct Google Drive cleanup interval."))

        # Super
        Config = self.env['ir.config_parameter'].sudo()
        temp_auth_code = Config.get_param('abackup_gdrive_auth_code')

        super(ResConfigSettings, self).set_values()

        if temp_auth_code != self.abackup_gdrive_auth_code:
            Config.set_param('abackup_gdrive_token', False)
            Config.set_param('abackup_gdrive_refresh_code', False)
            Config.set_param('abackup_gdrive_expires_at', False)

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

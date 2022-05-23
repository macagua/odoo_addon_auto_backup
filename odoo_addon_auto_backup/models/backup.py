from datetime import datetime, timedelta
import logging
import os
import pytz

import odoo
from odoo import fields, http, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class Backup(models.Model):
    _name = 'odoo_addon_auto_backup.backup'
    _description = 'Backup'

    PREFIX = 'ABK'
    TIME_FORMAT = '%Y-%m-%d-%H-%M-%S'

    created_time = fields.Datetime(string='Created Time')
    file_name = fields.Char(string='File name')
    local_path = fields.Char(string='Local path')
    gdrive_id = fields.Char(string='Google Drive file ID')
    is_local_removed = fields.Boolean(string='Removed locally', default=False)
    is_gdrive_removed = fields.Boolean(string='Removed on Google Drive', default=False)
    gdrive_url = fields.Char(string='Google Drive URL', compute='_compute_gdrive_url', store=False)

    def _compute_gdrive_url(self):
        for backup in self:
            if backup.gdrive_id:
                backup.gdrive_url = 'https://drive.google.com/file/d/' + backup.gdrive_id
            else:
                backup.gdrive_url = False

    def backup(self):
        db_name = http.db_monodb()

        Config = self.env['ir.config_parameter'].sudo()
        local_backup = Config.get_param('abackup_local_backup')
        backup_path = Config.get_param('abackup_local_path')
        gdrive_backup = Config.get_param('abackup_gdrive_backup')
        backup = None

        try:
            ts = datetime.utcnow().strftime(self.TIME_FORMAT)
            filename = "%s_%s_%s.%s" % (self.PREFIX, db_name, ts, 'dump')
            file_path = None
            drive_id = None
            dump_stream = odoo.service.db.dump_db(db_name, None, 'dump').read()

            if local_backup:
                file_path = backup_path + filename
                with open(file_path, 'wb') as f:
                    f.write(dump_stream)

            if gdrive_backup:
                Drive = self.env['odoo_addon_auto_backup.google_drive']
                drive_id = Drive.upload_resumable(dump_stream, filename)
                # drive_id = Drive.upload(dump_stream, filename)

            # Create a new backup record
            backup = self.env['odoo_addon_auto_backup.backup'].create({
                'created_time': datetime.now(),
                'file_name': filename,
                'local_path': file_path,
                'gdrive_id': drive_id,
            })

        except Exception as e:
            _logger.exception('Database.backup')

        return backup

    def get_delta(self, backup_type):
        Config = self.env['ir.config_parameter'].sudo()
        itv_number = int(Config.get_param('abackup_%s_cleanup_itv_number' % backup_type))
        itv_type = Config.get_param('abackup_%s_cleanup_itv_type' % backup_type)

        if itv_type == 'week(s)':
            itv_number *= 7
        elif itv_type == 'month(s)':
            itv_number *= 30
        return timedelta(days=itv_number)

    def clean_local(self):
        clean_limit = datetime.now() - self.get_delta('local')
        old_backups = self.env['odoo_addon_auto_backup.backup'].search([('created_time', '<', clean_limit),
                                                                        ('is_local_removed', '=', False),
                                                                        ('local_path', '!=', False)])
        for backup in old_backups:
            try:
                os.remove(backup.local_path)
                backup.is_local_removed = True
            except OSError:
                _logger.exception('Database.local.cleanup')

    def clean_gdrive(self):
        Drive = self.env['odoo_addon_auto_backup.google_drive']

        clean_limit = datetime.now() - self.get_delta('gdrive')
        old_backups = self.env['odoo_addon_auto_backup.backup'].search([('created_time', '<', clean_limit),
                                                                        ('is_gdrive_removed', '=', False),
                                                                        ('gdrive_id', '!=', False)])
        for backup in old_backups:
            try:
                Drive.delete(backup.gdrive_id)
                backup.is_gdrive_removed = True
            except Exception as e:
                _logger.exception('Database.gdrive.cleanup')

    def run(self):
        Config = self.env['ir.config_parameter'].sudo()
        local_cleanup = Config.get_param('abackup_local_cleanup')
        gdrive_cleanup = Config.get_param('abackup_gdrive_cleanup')

        # Backup and send mail
        backup_obj = self.backup()
        if backup_obj:
            template = self.env.ref('odoo_addon_auto_backup.email_template_auto_backup')
            recipients = self.env['res.users'].search([('receive_backup_email', '=', True)])
            for recipient in recipients:
                if recipient.tz:
                    tz = pytz.timezone(recipient.tz)
                    localized_time = pytz.utc.localize(backup_obj.created_time).astimezone(tz).strftime('%m-%d-%Y %H:%M:%S')
                else:
                    localized_time = backup_obj.created_time.strftime('%m-%d-%Y %H:%M:%S')
                email_values = {
                    'name': recipient.name,
                    'email': recipient.email,
                    'time': localized_time,
                }
                template.with_context(email_values).send_mail(backup_obj.id,
                                                              email_values=None,
                                                              force_send=True)

        if local_cleanup:
            self.clean_local()
        if gdrive_cleanup:
            self.clean_gdrive()

    def run_manually(self):
        Config = self.env['ir.config_parameter'].sudo()
        local_backup = Config.get_param('abackup_local_backup')
        gdrive_backup = Config.get_param('abackup_gdrive_backup')

        if not local_backup and not gdrive_backup:
            raise UserError(_('Please configure your backup preferences in Settings first.'))
        self.run()

    def get_cleanup_warning_str(self):
        Config = self.env['ir.config_parameter'].sudo()

        local_cleanup = Config.get_param('abackup_local_cleanup')
        gdrive_cleanup = Config.get_param('abackup_gdrive_cleanup')
        local_itv_number = Config.get_param('abackup_local_cleanup_itv_number')
        local_itv_type = Config.get_param('abackup_local_cleanup_itv_type')
        gdrive_itv_number = Config.get_param('abackup_local_cleanup_itv_number')
        gdrive_itv_type = Config.get_param('abackup_local_cleanup_itv_type')

        if local_cleanup and gdrive_cleanup:
            return 'local backups will be automatically removed after %s %s of creation, and backup files on ' \
                   'Google Drive will be removed after %s %s' % (local_itv_number, local_itv_type,
                                                                 gdrive_itv_number, gdrive_itv_type)
        if local_cleanup:
            return 'local backups will be automatically removed after %s %s of creation' % (local_itv_number,
                                                                                            local_itv_type)
        return 'backup files on Google Drive will be automatically removed after %s %s of creation' % (
            gdrive_itv_number, gdrive_itv_type)

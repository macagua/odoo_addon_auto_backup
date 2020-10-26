from datetime import datetime, timedelta
import logging
import os

import odoo
from odoo import fields, models, api, http

_logger = logging.getLogger(__name__)


class Backup(models.TransientModel):
    _name = 'odoo_addon_auto_backup.backup'

    PREFIX = 'ABK'
    TIME_FORMAT = '%Y-%m-%d-%H-%M-%S'

    def backup(self):
        db_name = http.db_monodb()

        Config = self.env['ir.config_parameter'].sudo()
        local_backup = Config.get_param('abackup_local_backup')
        backup_path = Config.get_param('abackup_local_path')
        gdrive_backup = Config.get_param('abackup_gdrive_backup')

        if local_backup or gdrive_backup:
            try:
                ts = datetime.utcnow().strftime(self.TIME_FORMAT)
                filename = "%s_%s_%s.%s" % (self.PREFIX, db_name, ts, 'dump')
                dump_stream = odoo.service.db.dump_db(db_name, None, 'dump').read()

                if local_backup:
                    with open(backup_path + filename, 'wb') as f:
                        f.write(dump_stream)

                if gdrive_backup:
                    Drive = self.env['odoo_addon_auto_backup.google_drive']
                    Drive.upload(dump_stream, filename)

            except Exception as e:
                _logger.exception('Database.backup')

    def get_delta(self, backup_type):
        Config = self.env['ir.config_parameter'].sudo()
        itv_number = int(Config.get_param('abackup_%s_cleanup_itv_number' % backup_type))
        itv_type = Config.get_param('abackup_%s_cleanup_itv_type' % backup_type)

        if itv_type == 'days':
            itv_number *= 7
        elif itv_type == 'months':
            itv_number *= 30
        return timedelta(days=itv_number)

    def clean_local(self):
        Config = self.env['ir.config_parameter'].sudo()
        backup_path = Config.get_param('abackup_local_path')

        delta = self.get_delta('local')
        now = datetime.now()

        files = os.listdir(backup_path)
        for file_name in files:
            if file_name.startswith(self.PREFIX):
                try:
                    created = datetime.strptime(file_name.split('_')[-1][:-5], self.TIME_FORMAT)
                    if now - created > delta:
                        os.remove(backup_path + file_name)
                except ValueError:
                    _logger.exception('Database.local.cleanup')

    def clean_gdrive(self):
        Drive = self.env['odoo_addon_auto_backup.google_drive']
        delta = self.get_delta('gdrive')
        now = datetime.now()

        files = Drive.list(self.PREFIX)
        delete_ids = []
        for file in files:
            try:
                created = datetime.strptime(file['name'].split('_')[-1][:-5], self.TIME_FORMAT)
                if now - created > delta:
                    delete_ids.append(file['id'])
            except ValueError:
                _logger.exception('Database.local.cleanup')

        Drive.delete(delete_ids)

    def run(self):
        Config = self.env['ir.config_parameter'].sudo()
        local_cleanup = Config.get_param('abackup_local_cleanup')
        gdrive_cleanup = Config.get_param('abackup_gdrive_cleanup')

        self.backup()
        if local_cleanup:
            self.clean_local()
        if gdrive_cleanup:
            self.clean_gdrive()

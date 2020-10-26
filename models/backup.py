import datetime
import logging
import os

import odoo
from odoo import fields, models, api, http

_logger = logging.getLogger(__name__)


class Backup(models.TransientModel):
    _name = 'odoo_addon_auto_backup.backup'

    def backup(self):
        db_name = http.db_monodb()

        Config = self.env['ir.config_parameter'].sudo()
        local_backup = Config.get_param('abackup_local_backup')
        backup_path = Config.get_param('abackup_local_path')
        gdrive_backup = Config.get_param('abackup_gdrive_backup')

        if local_backup or gdrive_backup:
            try:
                ts = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
                filename = "ABK_%s_%s.%s" % (db_name, ts, 'dump')
                dump_stream = odoo.service.db.dump_db(db_name, None, 'dump').read()

                if local_backup:
                    if backup_path[-1] != '/':
                        backup_path += '/'
                    with open(backup_path + filename, 'wb') as f:
                        f.write(dump_stream)

                if gdrive_backup:
                    Drive = self.env['odoo_addon_auto_backup.google_drive']
                    Drive.upload(dump_stream, filename)

            except Exception as e:
                _logger.exception('Database.backup')

    def clean_local(self):
        Config = self.env['ir.config_parameter'].sudo()
        backup_path = Config.get_param('abackup_local_path')

        files = os.listdir(backup_path)
        log_time = datetime.now().__str__() + ': '
        hasMoved = False

    def run_backup(self):
        Config = self.env['ir.config_parameter'].sudo()
        local_cleanup = Config.get_param('abackup_local_cleanup')
        gdrive_cleanup = Config.get_param('abackup_gdrive_cleanup')

        self.backup()
        if local_cleanup:
            self.clean_local()
        if gdrive_cleanup:
            self.clean_gdrive()

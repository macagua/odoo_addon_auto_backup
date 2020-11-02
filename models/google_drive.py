import json
import urllib
import requests
import random
import string
from datetime import datetime, timedelta

from odoo import fields, models, api, _
from odoo.exceptions import UserError

GOOGLE_OAUTH_ENDPOINT = 'https://oauth2.googleapis.com/token'
GOOGLE_USER_PROMPT_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_DRIVE_UPLOAD_API = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable'
GOOGLE_DRIVE_API = 'https://www.googleapis.com/drive/v3/files/'
MAX_ATTEMPT = 5


class GoogleDrive(models.Model):
    _name = 'odoo_addon_auto_backup.google_drive'

    def gen_local_token(self):
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for i in range(64))

    @api.model
    def get_user_redirect_url(self, client_id=None):
        Config = self.env['ir.config_parameter'].sudo()
        base_url = Config.get_param('web.base.url')
        client_id = client_id or Config.get_param('abackup_gdrive_client_id')

        local_token = self.gen_local_token()
        Config.set_param('abackup_oauth_local_token', local_token)
        state = {
            't': local_token
        }

        params = {
            'client_id': client_id,
            'redirect_uri': base_url + '/autobackup/authentication',
            'access_type': 'offline',
            'response_type': 'code',
            'scope': 'https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/drive.file',
            'state': json.dumps(state),
        }
        try:
            params_text = '&'.join(['%s=%s' % (key, urllib.parse.quote(value, safe=''))
                                for (key, value) in params.items()])
            return GOOGLE_USER_PROMPT_URL + '?' + params_text
        except TypeError:
            return False

    @api.model
    def get_access_token(self):
        Config = self.env['ir.config_parameter'].sudo()
        TIME_FORMAT = '%Y-%m-%d %X'
        EXPIRATION_OFFSET = 5

        base_url = Config.get_param('web.base.url')
        auth_code = Config.get_param('abackup_gdrive_auth_code')

        if not auth_code:
            Config.set_param('abackup_gdrive_fail', True)
            raise UserError(_("Authorization code is not available."))

        token = Config.get_param('abackup_gdrive_token', False)
        refresh_token = Config.get_param('abackup_gdrive_refresh_code', False)
        expires_at = Config.get_param('abackup_gdrive_expires_at', False)
        client_id = Config.get_param('abackup_gdrive_client_id')
        client_secret = Config.get_param('abackup_gdrive_client_secret')

        if token and expires_at and datetime.now() < datetime.strptime(expires_at, TIME_FORMAT):
            return token

        headers = {"Content-type": "application/x-www-form-urlencoded"}
        if refresh_token:
            # Request refresh token
            body = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
            }
        else:
            # Request new token
            body = {
                'client_id': client_id,
                'client_secret': client_secret,
                'code': auth_code,
                'grant_type': 'authorization_code',
                'redirect_uri': base_url + '/autobackup/authentication',
            }
        res = requests.post(GOOGLE_OAUTH_ENDPOINT, data=body, headers=headers)
        try:
            res.raise_for_status()
        except Exception as e:
            Config.set_param('abackup_gdrive_fail', True)
            raise e

        res_json = res.json()

        delta = timedelta(seconds=(res_json.get('expires_in') - EXPIRATION_OFFSET))
        expires_at_str = (datetime.now() + delta).strftime(TIME_FORMAT)

        Config.set_param('abackup_gdrive_expires_at', expires_at_str)
        Config.set_param('abackup_gdrive_refresh_code', res_json.get('refresh_token'))
        Config.set_param('abackup_gdrive_token', res_json.get('access_token'))
        Config.set_param('abackup_gdrive_fail', False)

        return res_json.get('access_token')

    def resume_upload(self, binary_stream, upload_location):
        try_count = 0
        token = self.get_access_token()

        headers = {
            "Authorization": "Bearer %s" % token,
            "Content-Range": "*/*"
        }
        res = requests.put(upload_location, headers=headers)
        if res.status_code == 200 or res.status_code == 201:
            return res.json().get('id')
        elif res.status_code == 308:
            while try_count < MAX_ATTEMPT:
                try_count += 1
                uploaded_range = res.headers['Range']
                if not uploaded_range:
                    range_start, range_end = -1, -1
                else:
                    uploaded_range = uploaded_range[6:].split('-')
                    range_start, range_end = int(uploaded_range[0]), int(uploaded_range[1])

                headers['Content-Range'] = 'bytes %s-%s/%s' % (range_end + 1, len(binary_stream) - 1, len(binary_stream))
                res = requests.put(upload_location, headers=headers, data=binary_stream[range_end + 1:])

                if res.status_code == 200 or res.status_code == 201:
                    return res.json().get('id')

    def upload_resumable(self, binary_stream, file_name):
        folder_id = self.env['ir.config_parameter'].sudo().get_param('abackup_gdrive_location')
        token = self.get_access_token()

        # Send init request
        headers = {"Authorization": "Bearer %s" % token}
        params = {
            'enforceSingleParent': True
        }
        body = {
            'name': file_name,
            'parents': [folder_id],
        }
        res = requests.post(GOOGLE_DRIVE_UPLOAD_API, headers=headers, json=body, params=params)
        res.raise_for_status()
        upload_location = res.headers['Location']

        # Upload file
        res = requests.put(upload_location, headers=headers, data=binary_stream)
        if res.status_code == 200:
            return res.json().get('id')
        elif res.status_code // 100 == 5:  # Status code 5xx
            return self.resume_upload(binary_stream, file_name)
        res.raise_for_status()

    def delete(self, file_id):
        if not file_id:
            return
        token = self.get_access_token()
        headers = {"Authorization": "Bearer %s" % token}
        res = requests.delete(GOOGLE_DRIVE_API + file_id, headers=headers)
        res.raise_for_status()

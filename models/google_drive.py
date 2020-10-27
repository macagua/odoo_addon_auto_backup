import json
import urllib
import requests
import random
import string

from odoo import fields, models, api, _
from odoo.exceptions import UserError

GOOGLE_OAUTH_ENDPOINT = 'https://oauth2.googleapis.com/token'
GOOGLE_USER_PROMPT_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_DRIVE_UPLOAD_API = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart'
GOOGLE_DRIVE_API = 'https://www.googleapis.com/drive/v3/files/'


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

        params_text = '&'.join(['%s=%s' % (key, urllib.parse.quote(value, safe=''))
                                for (key, value) in params.items()])
        return GOOGLE_USER_PROMPT_URL + '?' + params_text


    @api.model
    def get_access_token(self):
        Config = self.env['ir.config_parameter'].sudo()

        base_url = Config.get_param('web.base.url')
        auth_code = Config.get_param('abackup_gdrive_auth_code')
        refresh_token = Config.get_param('abackup_gdrive_refresh_code', False)
        client_id = Config.get_param('abackup_gdrive_client_id')
        client_secret = Config.get_param('abackup_gdrive_client_secret')

        if auth_code:
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

            headers = {"Content-type": "application/x-www-form-urlencoded"}

            req = requests.post(GOOGLE_OAUTH_ENDPOINT, data=body, headers=headers)
            try:
                req.raise_for_status()
            except Exception as e:
                Config.set_param('abackup_gdrive_fail', True)
                raise e

            req_json = req.json()
            if req_json.get('refresh_token') is not None:
                self.env['ir.config_parameter'].sudo().set_param('abackup_gdrive_refresh_code', req_json.get('refresh_token'))

            Config.set_param('abackup_gdrive_fail', False)
            return req_json.get('access_token')

        Config.set_param('abackup_gdrive_fail', True)
        raise UserError(_("Authorization code is not available."))

    def upload(self, binary_stream, file_name):
        folder_id = self.env['ir.config_parameter'].sudo().get_param('abackup_gdrive_location')

        token = self.get_access_token()
        # Upload file
        para = json.dumps({
            'name': file_name,
        })
        headers = {"Authorization": "Bearer %s" % token}
        files = {
            'data': ('metadata', json.dumps(para), 'application/json; charset=UTF-8'),
            'file': ('mimeType', binary_stream)
        }

        req = requests.post(GOOGLE_DRIVE_UPLOAD_API, headers=headers, files=files)
        req.raise_for_status()

        # Update file name
        file_id = req.json().get('id')
        if folder_id:
            params = {
                'addParents': [folder_id],
                'enforceSingleParent': True
            }
        else:
            params = None
        body = {
            'name': file_name,
        }
        req = requests.patch(GOOGLE_DRIVE_API + file_id, headers=headers, json=body, params=params)
        req.raise_for_status()

    def list(self, prefix):
        folder_id = self.env['ir.config_parameter'].sudo().get_param('abackup_gdrive_location')

        token = self.get_access_token()
        if folder_id:
            query = "name contains '%s' and '%s' in parents" % (prefix, folder_id)
        else:
            query = "name contains '%s'" % prefix
        params = {
            'q': query,
            'pageSize': 1000
        }
        headers = {"Authorization": "Bearer %s" % token}

        req = requests.get(GOOGLE_DRIVE_API, headers=headers, params=params)
        req.raise_for_status()
        return req.json().get('files')

    def delete(self, file_ids):
        if len(file_ids) == 0:
            return
        token = self.get_access_token()
        for id in file_ids:
            headers = {"Authorization": "Bearer %s" % token}
            req = requests.delete(GOOGLE_DRIVE_API + id, headers=headers)

# -*- coding: utf-8 -*-
from odoo import http
from werkzeug.utils import redirect
import json


class GoogleAuthEndpoint(http.Controller):

    @http.route('/autobackup/authentication', type='http', auth="none")
    def oauth2callback(self, **kw):

        Config = http.request.env['ir.config_parameter'].sudo()
        state = kw.get('state')
        if state:
            local_token = Config.get_param('abackup_oauth_local_token')
            state = json.loads(state)
            if local_token == state.get('t'):
                Config.set_param('abackup_gdrive_auth_code', kw.get('code'))
                Config.set_param('abackup_gdrive_token', False)
                Config.set_param('abackup_gdrive_refresh_code', False)
                Config.set_param('abackup_gdrive_expires_at', False)

        return redirect(http.request.env['ir.config_parameter'].sudo().get_param('web.base.url'))

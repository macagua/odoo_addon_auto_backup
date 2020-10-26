# -*- coding: utf-8 -*-
from odoo import http
from werkzeug.utils import redirect


class GoogleAuthEndpoint(http.Controller):

    @http.route('/screwproof/authentication', type='http', auth="none")
    def oauth2callback(self, **kw):
        """ This route/function is called by Google when user Accept/Refuse the consent of Google """

        if kw.get('code'):
            http.request.env['ir.config_parameter'].sudo().set_param('abackup_gdrive_auth_code', kw.get('code'))

        return redirect(http.request.env['ir.config_parameter'].sudo().get_param('web.base.url'))

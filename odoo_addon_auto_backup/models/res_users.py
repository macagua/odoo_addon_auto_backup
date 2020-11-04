from odoo import fields, models, api


class Users(models.Model):
    _inherit = 'res.users'

    def _default_receive_email(self):
        group_system_id = self.env.ref('base.group_system')
        return group_system_id in self.groups_id

    receive_backup_email = fields.Boolean(default=_default_receive_email,
                                          string="Send backup information email to this user")

# -*- coding: utf-8 -*-
{
    'name': "Odoo Addon Auto Backup",

    'summary': """Automatically back up your database on a predetermined basis""",

    'description': """
Odoo Addon Auto Backup
==================================
Data is always an important aspect of any operational system. With
this module, your Odoo database is safe. The module helps back up
your database on a schedule that you set, so you always have
a fallback should anything unexpected occurs.


Main Features
-------------
* Automatically generate database backups.
* Save backup file to local machine or Google Drive
* Automatically clean up old backups.
    """,

    'author': "Magenest",
    'website': "https://magenest.com/en/",
    'category': 'Extra Tools',
    'version': '0.1',
    'depends': ['base', 'base_setup'],
    'data': [
        'data/backup_cronjob.xml',
        'views/res_config_settings_view.xml',
        'views/abackup_views.xml',
        'views/user_form_views.xml',
        'mails/backup_information_mail.xml',
        'security/ir.model.access.csv'
    ],
}

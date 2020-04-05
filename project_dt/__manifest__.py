# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Mini Project',
    'version': '1.1',
    'website': '',
    'category': 'Project',
    'sequence': 1,
    'summary': 'Organize and schedule your mini projects by Tb',
    'author': 'Tb25',
    'depends': [
        'base',
        'base_setup',
        'project',
        'crm_project',
        'mail',
        'portal',
        'rating',
        'resource',
        'web',
        'web_tour',
        'digest',
        #'ir_attachment',
        'hr',
    ],
    'description': "If you need same module of Project Management as same when installed module of Project Management base, you can use this module",
    'data': [
        'security/ir.model.access.csv',
        'views/project_views.xml',
    ],
    #'qweb': ['static/src/xml/project.xml'],
    #'demo': ['data/project_demo.xml'],
    #'test': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}

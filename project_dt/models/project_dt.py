# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.tools.safe_eval import safe_eval



class ProjectTaskTypeDt(models.Model):
    _name = 'project.task.type.dt'
    _description = 'Task Stage Design team'
    _order = 'sequence, id'

    def _get_default_project_ids(self):
        default_project_id = self.env.context.get('default_project_id')
        return [default_project_id] if default_project_id else None

    name = fields.Char(string='Stage Name', required=True, translate=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=1)
    project_ids = fields.Many2many('project.dt', 'project_task_type_rel_dt', 'type_id', 'project_id', string='Projects',
        default=_get_default_project_ids)
    legend_priority = fields.Char(
        string='Starred Explanation', translate=True,
        help='Explanation text to help users using the star on tasks or issues in this stage.')
    legend_blocked = fields.Char(
        'Red Kanban Label', default=lambda s: _('Blocked'), translate=True, required=True,
        help='Override the default value displayed for the blocked state for kanban selection, when the task or issue is in that stage.')
    legend_done = fields.Char(
        'Green Kanban Label', default=lambda s: _('Ready for Next Stage'), translate=True, required=True,
        help='Override the default value displayed for the done state for kanban selection, when the task or issue is in that stage.')
    legend_normal = fields.Char(
        'Grey Kanban Label', default=lambda s: _('In Progress'), translate=True, required=True,
        help='Override the default value displayed for the normal state for kanban selection, when the task or issue is in that stage.')
    fold = fields.Boolean(string='Folded in Kanban',
        help='This stage is folded in the kanban view when there are no records in that stage to display.')
    mail_template_id = fields.Many2one(
        'mail.template',
        string='Email Template',
        domain=[('model', '=', 'task.dt')],
        help="If set an email will be sent to the customer when the task or issue reaches this step.")
    rating_template_id = fields.Many2one(
        'mail.template',
        string='Rating Email Template',
        domain=[('model', '=', 'task.dt')],
        help="If set and if the project's rating configuration is 'Rating when changing stage', then an email will be sent to the customer when the task reaches this step.")
    auto_validation_kanban_state = fields.Boolean('Automatic kanban status', default=False,
        help="Automatically modify the kanban state when the customer replies to the feedback for this stage.\n"
            " * A good feedback from the customer will update the kanban state to 'ready for the new stage' (green bullet).\n"
            " * A medium or a bad feedback will set the kanban state to 'blocked' (red bullet).\n")
    projects = fields.One2many('project.dt', 'stage_id', string='Task Activities')
    is_project = fields.Boolean(string="Is project")
    is_sub_task = fields.Boolean(string="Sub task")
    is_last_stage = fields.Boolean(string="Is Last stage")
    

class ProjectDt(models.Model):
    _name = "project.dt"
    _description = "Project Design team"
    _inherit = ['portal.mixin', 'mail.thread']
    _order = "sequence, name, id"
    #_period_number = 5
    
    def _compute_task_count(self):
        #task_data = self.env['task.dt'].read_group([('project_id', 'in', self.ids), '|', ('stage_id.fold', '=', False), ('stage_id', '=', False), ('parent_id', '=', False)], ['project_id'], ['project_id'])
        #result = dict((data['project_id'][0], data['project_id_count']) for data in task_data)
        for project in self:
            task_ids = self.env['task.dt'].search([('project_id', '=', project.id)]).ids
            project.task_count = len(task_ids)
                
    def _compute_is_favorite(self):
        for project in self:
            project.is_favorite = self.env.user in project.favorite_user_ids
            
    def _inverse_is_favorite(self):
        favorite_projects = not_fav_projects = self.env['project.dt'].sudo()
        for project in self:
            if self.env.user in project.favorite_user_ids:
                favorite_projects |= project
            else:
                not_fav_projects |= project
        
        # Project User has no write access for project.
        not_fav_projects.write({'favorite_user_ids': [(4, self.env.uid)]})
        favorite_projects.write({'favorite_user_ids': [(3, self.env.uid)]})
        
    def _get_default_favorite_user_ids(self):
        return [(6, 0, [self.env.uid])]
                
    
    @api.depends('task_ids.planned_hours')
    def _compute_task_planned(self):
        for project in self:
            project.planned = sum(project.task_ids.mapped('planned_hours'))
    
    @api.depends('task_ids.planned_hours','task_ids.progress')
    def _compute_task_effective(self):
        for project in self:
            i = 0.0
            for line in project.task_ids:
                #===============================================================
                # if line.progress == 100.0:
                #     i = i + 1
                #===============================================================
                if line.progress == 100.0:
                    i = i + sum(line.mapped('planned_hours'))
            project.effective = i

    def _compute_task_progress(self):
        for project in self:
            if project.planned != 0:
                project.progress = project.effective * 100.0 / project.planned
            else:
                project.progress = 0.0
    
    
    def _compute_cs_planned(self):
        for project in self:
            #project.planned = sum(project.task_ids.mapped('planned_hours'))
            task_ids25 = self.env['task.dt'].search([('project_id', '=', project.id),('project_stage_id', '=', project.stage_id.id)])
            #===================================================================
            # for line in task_ids25:
            #     cs_sum = cs_sum + line.
            #===================================================================
            project.cs_planned = sum(task_ids25.mapped('planned_hours'))
            
    def _compute_cs_effective(self):
        for project in self:
            i = 0.0
            task_ids25 = self.env['task.dt'].search([('project_id', '=', project.id),('project_stage_id', '=', project.stage_id.id)])
            for line in task_ids25:
                #===============================================================
                # if line.progress == 100.0:
                #     i = i + 1
                #===============================================================
                if line.progress == 100.0:
                    i = i + sum(line.mapped('planned_hours'))
            project.cs_effective = i

    def _compute_cs_progress(self):
        for project in self:
            if project.cs_planned != 0:
                project.cs_progress = project.cs_effective * 100.0 / project.cs_planned
            else:
                project.cs_progress = 0.0

    def tb_doc_view(self):
        self.ensure_one()
        domain = [
            ('res_id', '=', self.id)]
        return {
            'name': _('Project Attachments'),
            'domain': domain,
            'res_model': 'ir.attachment',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'kanban,tree,form',
            'view_type': 'form',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        Documents are attached to the tasks and issues of your project.</p><p>
                        Send messages or log internal notes with attachments to link
                        documents to your project.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d}" % (self._name, self.id)
        }
     
    #===========================================================================
    # def _compute_doc_count(self):
    #     for project in self:
    #         #doc_ids25 = self.env['project.project'].search([('members', 'in', project.user_id),('members', '!=', False)]).ids
    #         project.doc_count = len(self.message_attachment_count)
    #===========================================================================
    
    
    @api.multi
    def tb_task_view(self):
        self.ensure_one()
        domain = [
            ('project_id', '=', self.id),('project_stage_id', '=', self.stage_id.id)]
        return {
            'name': self.stage_id.name,
            'domain': domain,
            'res_model': 'task.dt',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'view_type': 'form',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        Documents are attached to the tasks and issues of your project.</p><p>
                        Send messages or log internal notes with attachments to link
                        documents to your project.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d,'default_project_id': %d,'default_project_stage_id': %d}" % (self._name, self.id, self.id, self.stage_id.id)
        }
    
    def _compute_task_count2(self):
        for project in self:
            task_ids25 = self.env['task.dt'].search([('project_id', '=', project.id),('project_stage_id', '=', project.stage_id.id)]).ids
            project.task_count2 = len(task_ids25)
            
    is_template_project = fields.Boolean(string='Is template', track_visibility='onchange', default=False, copy=False)
    partner_id = fields.Many2one('res.partner', string='Project family name', track_visibility='onchange')
    name = fields.Char("Project name")
    approved_number = fields.Char("Project code")
    date_deadline = fields.Date("Project deadline")
    active = fields.Boolean(default=True,
        help="If the active field is set to False, it will allow you to hide the project without removing it.")
    #team_id = fields.Many2one('crm.team', string='Project team', track_visibility='onchange')

    members = fields.Many2many('res.users', 'project_user_rel_dt', 'project_dt_id',
                               'uid', 'Project Members DT', help="""Project's
                               members are users who can have an access to
                               the tasks related to this project."""
                               )
    #===========================================================================
    # team_members = fields.Many2many('res.users', 'project_team_user_rel_dt',
    #                                 'team_dt_id', 'uid', 'Project Members DT')
    #===========================================================================
    team_id = fields.Many2one('crm.team', "Project Team DT",
                              domain=[('type_team', '=', 'project')])
    
    description = fields.Text("Description")
    is_design_team_project = fields.Boolean("Is design team project")
    
    label_tasks = fields.Char(string='Use Tasks as', default=lambda s: _('Tasks'), translate=True,
        help="Gives label to tasks on project's kanban view.")
    tasks = fields.One2many('task.dt', 'project_id', string='Tasks', copy=True)
    type_ids = fields.Many2many('project.task.type.dt', 'project_task_type_rel_dt', 'project_id', 'type_id', string='Tasks Stages')
    task_count = fields.Integer(compute='_compute_task_count', string="Task Count")
    task_count2 = fields.Integer(compute='_compute_task_count2', string="Task Count 2")
    task_ids = fields.One2many('task.dt', 'project_id', string='Tasks', copy=True, domain=['|', ('stage_id.fold', '=', False), ('stage_id', '=', False)])
    color = fields.Integer(string='Color Index')
    user_id = fields.Many2one('res.users', string='Project Manager', default=lambda self: self.env.user, track_visibility="onchange")
    
    #doc_count = fields.Integer(compute='_compute_doc_count', string="DOC Count")
            
    stage_id = fields.Many2one('project.task.type.dt', string="Stage")

    planned = fields.Float("Planned", compute='_compute_task_planned')
    effective = fields.Float("Effective", compute='_compute_task_effective')
    progress = fields.Float(compute='_compute_task_progress', string="Progress")
    #doc_count = fields.Integer(compute='_compute_attached_docs_count', string="Number of documents attached")

    cs_planned = fields.Float("Current stage Planned", compute='_compute_cs_planned')
    cs_effective = fields.Float("Current stage Effective", compute='_compute_cs_effective')
    cs_progress = fields.Float(string="Current stage Progress", compute='_compute_cs_progress')
    
    subtask_project_id = fields.Many2one('project.dt', string='Sub-task Project', ondelete="restrict",
        help="Choosing a sub-tasks project will both enable sub-tasks and set their default project (possibly the project itself)")
    
    sequence = fields.Char("Sequence")
    #===========================================================================
    # alias_id = fields.Many2one('mail.alias', string='Alias', ondelete="restrict", required=True,
    #     help="Internal email associated with this project. Incoming emails are automatically synchronized "
    #          "with Tasks (or optionally Issues if the Issue Tracker module is installed).")
    #===========================================================================
    favorite_user_ids = fields.Many2many(
        'res.users', 'project_favorite_user_rel_dt', 'project_id', 'user_id',
        default=_get_default_favorite_user_ids,
        string='Members')
    is_favorite = fields.Boolean(compute='_compute_is_favorite', inverse='_inverse_is_favorite', string='Show Project on dashboard',
        help="Whether this project should be displayed on the dashboard or not")
    privacy_visibility = fields.Selection([
            ('followers', 'On invitation only'),
            ('employees', 'Visible by all employees'),
            ('portal', 'Visible by following customers'),
        ],
        string='Privacy',
        default='portal',
        help="Holds visibility of the tasks or issues that belong to the current project:\n"
                "- On invitation only: Employees may only see the followed project, tasks or issues\n"
                "- Visible by all employees: Employees may see all project, tasks or issues\n"
                "- Visible by following customers: employees see everything;\n"
                "   if website is activated, portal users may see project, tasks or issues followed by\n"
                "   them or by someone of their company\n")
    rating_status = fields.Selection([('stage', 'Rating when changing stage'), ('periodic', 'Periodical Rating'), ('no','No rating')], 'Customer(s) Ratings', help="How to get the customer's feedbacks?\n"
                    "- Rating when changing stage: Email will be sent when a task/issue is pulled in another stage\n"
                    "- Periodical Rating: Email will be sent periodically\n\n"
                    "Don't forget to set up the mail templates on the stages for which you want to get the customer's feedbacks.", default="no", required=True)
    rating_status_period = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'), ('bimonthly', 'Twice a Month'),
        ('monthly', 'Once a Month'), ('quarterly', 'Quarterly'), ('yearly', 'Yearly')
    ], 'Rating Frequency')
    portal_show_rating = fields.Boolean('Rating visible publicly', copy=False, oldname='website_published')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
#===============================================================================
#     percentage_satisfaction_task = fields.Integer(
#         compute='_compute_percentage_satisfaction_task', string="Happy % on Task", store=True, default=-1)
#     percentage_satisfaction_project = fields.Integer(
#         compute="_compute_percentage_satisfaction_project", string="Happy % on Project", store=True, default=-1)
#     rating_request_deadline = fields.Datetime(compute='_compute_rating_request_deadline', store=True)
#     rating_status = fields.Selection([('stage', 'Rating when changing stage'), ('periodic', 'Periodical Rating'), ('no','No rating')], 'Customer(s) Ratings', help="How to get the customer's feedbacks?\n"
#                     "- Rating when changing stage: Email will be sent when a task/issue is pulled in another stage\n"
#                     "- Periodical Rating: Email will be sent periodically\n\n"
#                     "Don't forget to set up the mail templates on the stages for which you want to get the customer's feedbacks.", default="no", required=True)
#     rating_status_period = fields.Selection([
#         ('daily', 'Daily'), ('weekly', 'Weekly'), ('bimonthly', 'Twice a Month'),
#         ('monthly', 'Once a Month'), ('quarterly', 'Quarterly'), ('yearly', 'Yearly')
#     ], 'Rating Frequency')
# 
#     portal_show_rating = fields.Boolean('Rating visible publicly', copy=False, oldname='website_published')
#===============================================================================



    @api.onchange('team_id')
    def get_team_members(self):
        self.members = False
        if self.team_id:
            self.members = \
                [(6, 0, [member.id for member in self.team_id.team_members])]

    @api.model
    def activate_sample_project(self):
        
        action = self.env.ref('project_dt.open_view_project_dt_all', False)
        action_data = None
        if action:
            action.sudo().write({
                "help": _('''<p class="o_view_nocontent_smiling_face">
                    Create a new project</p>''')
            })
            action_data = action.read()[0]
        # Reload the dashboard
        return action_data

    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        if default is None:
            default = {}
        if not default.get('name'):
            default['name'] = _("%s (copy)") % self.name
        return super(ProjectDt, self).copy(default)

    #@api.multi
    #@api.returns('self', lambda value: value.id)
    def new_project_from_template(self, default=None):
        project_obj = self.env['project.dt'].search([('is_template_project', '=', True)])
        if default is None:
            default = {}
        if not default.get('name'):
            default['name'] = _("%s (copy)") % project_obj.name
        return super(ProjectDt, self).copy(default)
    
    def copy_tasks_from_template(self, default=None):
        writed_ids = []
        if not self.tasks:
            template_proj = self.env['project.dt'].search([('is_template_project', '=', True)])
            if template_proj and len(template_proj) == 1:
                template_proj_tasks = self.env['task.dt'].search([('project_id', '=', template_proj.id),('parent_id', '=', False)])
                if template_proj_tasks:
                    for copied_task_one_by_one_parent in template_proj_tasks:
                        if copied_task_one_by_one_parent:
                            for parent_task_copied in copied_task_one_by_one_parent:
                                par_task = parent_task_copied.copy()
                                par_task.write({'project_id': self.id})
                                if par_task.child_ids:
                                    for child_task in par_task.child_ids:
                                        child_task.write({'parent_id': par_task.id})
                        writed_ids.append(par_task)
        else:
            raise ValidationError("Энэ Төсөлд даалгавар бүртгэгдсэн байгаа тул загвар төслийн даалгаврыг хуулбарлахгүй!")
        
        return True
    
    def change_to_template(self):
        project_obj = self.env['project.dt']
        task_obj = self.env['task.dt']
        template_proj = project_obj.search([('is_template_project','=',True)])
        if template_proj:
            raise ValidationError("Энэ төрөлд загвар төсөл байна! Загвар төсөл цор ганц байх ёстой! Та өмнөх загвар төслийг цуцласны дараагаар энэхүү төслийг загвар болгож болно")
        else:
            template_tasks= task_obj.search([('project_id','=',self.id)])
            if template_tasks:
                for line in template_tasks:
                    if line.child_ids:
                        for line2 in line.child_ids:
                            line2.write({'is_template_task': True})
                    line.write({'is_template_task': True})
            self.is_template_project = True
        return True
    
    def change_to_untemplate(self):
        task_obj = self.env['task.dt']
        template_tasks= task_obj.search([('project_id','=',self.id)])
        if template_tasks:
            for line in template_tasks:
                if line.child_ids:
                    for line2 in line.child_ids:
                        line2.write({'is_template_task': False})
                line.write({'is_template_task': False})
        self.is_template_project = False
        return True

    #===========================================================================
    # @api.multi
    # def open_tasks(self):
    #     ctx = dict(self._context)
    #     ctx.update({'search_default_project_id': self.id})
    #     action = self.env['ir.actions.act_window'].for_xml_id('project.dt', 'act_project_project_2_project_task_dt_all')
    #     return dict(action, context=ctx)
    #===========================================================================
    
    
    #===========================================================================
    # def action_open_members_emp(self):
    #     return {
    #         'name': _('Employee of Members'),
    #         'view_type': 'kanban,form',
    #         'view_mode': 'kanban,form',
    #         'res_model': 'h',
    #         'res_id': self.parent_id.id,
    #         'type': 'ir.actions.act_window'
    #     }
    #===========================================================================
 
    def action_open_members_emp(self):
        action = self.env.ref('project_dt.act_project_2_employee_by_members2').read()[0]
        ctx = self.env.context.copy()
        ctx.update({
            'default_user_id': self.members,
            
        })
        action['context'] = ctx
        action['domain'] = [('user_id.id', 'in', self.members.ids)]
        return action
    
    
class TaskDt(models.Model):
    _name = "task.dt"
    _description = "Task Design team"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'rating.mixin']
    #_mail_post_access = 'read'
    _order = "priority desc, sequence, id desc"
    
    @api.depends('stage_id', 'kanban_state')
    
    def stage_find(self, section_id, domain=[], order='sequence'):
        # collect all section_ids
        section_ids = []
        if section_id:
            section_ids.append(section_id)
        section_ids.extend(self.mapped('project_id').ids)
        search_domain = []
        if section_ids:
            search_domain = [('|')] * (len(section_ids) - 1)
            for section_id in section_ids:
                search_domain.append(('project_ids', '=', section_id))
        search_domain += list(domain)
        # perform search, return the first found
        return self.env['project.task.type.dt'].search(search_domain, order=order, limit=1).id
    
    def _compute_kanban_state_label(self):
        for task in self:
            if task.kanban_state == 'normal':
                task.kanban_state_label = task.legend_normal
            elif task.kanban_state == 'blocked':
                task.kanban_state_label = task.legend_blocked
            else:
                task.kanban_state_label = task.legend_done

    def _get_default_stage_id(self):
        project_id = self.env.context.get('default_project_id')
        if not project_id:
            return False
        return self.stage_find(project_id, [('fold', '=', False)])
    
    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        search_domain = [('id', 'in', stages.ids)]
        if 'default_project_id' in self.env.context:
            search_domain = ['|', ('project_ids', '=', self.env.context['default_project_id'])] + search_domain
 
        stage_ids = stages._search(search_domain, order=order, access_rights_uid=SUPERUSER_ID)
        return stages.browse(stage_ids)
    
    @api.depends('child_ids')
    def _compute_subtask_count(self):
        task_data = self.env['task.dt'].read_group([('parent_id', 'in', self.ids)], ['parent_id'], ['parent_id'])
        mapping = dict((data['parent_id'][0], data['parent_id_count']) for data in task_data)
        for task in self:
            task.subtask_count = mapping.get(task.id, 0)
    
    @api.model
    def _get_default_partner(self):
        if 'default_project_id' in self.env.context:
            default_project_id = self.env['project.dt'].browse(self.env.context['default_project_id'])
            return default_project_id.exists().partner_id
    
    @api.depends('child_ids.planned_hours')
    def _compute_subtask_planned_hours(self):
        for task in self:
            task.subtask_planned_hours = sum(task.child_ids.mapped('planned_hours'))
    
    def tb_doc_view_task(self):
        self.ensure_one()
        domain = [
            ('res_id', '=', self.id)]
        return {
            'name': _('Task Attachments'),
            'domain': domain,
            'res_model': 'ir.attachment',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'view_type': 'form',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        Documents are attached to the tasks and issues of your project.</p><p>
                        Send messages or log internal notes with attachments to link
                        documents to your project.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d}" % (self._name, self.id)
        }
    #===========================================================================
    # @api.model
    # @api.depends('parent_id')
    # def _compute_is_subtask(self):
    #     for task in self:
    #         if task.parent_id:
    #             task.is_sub_task = True
    #         else:
    #             task.is_sub_task = False
    #===========================================================================

    #===========================================================================
    # def _compute_progress(self):
    #     for project in self:
    #         if project.is_sub_task == False:
    #             if project.subtask_planned_hours != 0:
    #                 sum_sub_planned = 0.0
    #                 for line in project.child_ids:
    #                     if line.progress == 100.0:
    #                         sum_sub_planned = sum_sub_planned + line.planned
    #                 project.progress = sum_sub_planned * 100.0 / project.subtask_planned_hours
    #             else:
    #                 project.progress = 0.0
    #         else:
    #             project.progress = project.progress
    #===========================================================================
    
    
    
    #===========================================================================
    # @api.depends('child_ids.planned_hours','child_ids.progress')
    # def _compute_subtask_effective(self):
    #     for project in self:
    #         if project.is_sub_task == False:
    #             i = 0.0
    #             for line in project.child_ids:
    #                 if line.progress == 100.0:
    #                     i = i + sum(line.mapped('planned_hours'))
    #             project.effective = i
    #===========================================================================
    @api.depends('is_sub_task')
    def _compute_task_progress(self):
        for project in self:
            if project.is_sub_task == False:
                if project.stage_id.is_last_stage == True:
                    project.progress = 100.0
                else:
                    i = 0.0
                    for line in project.child_ids:
                        if line.progress2 == 100.0:
                            i = i + sum(line.mapped('planned_hours'))
                    #project.effective = i
                    if i != 0.0:
                        project.progress = i * 100.0 / project.subtask_planned_hours
            else:
                project.progress = 0.0
            #===================================================================
            # else:
            #     print ('PPPPPPPPP')
            #     project.progress = 0.0
            #===================================================================
            #===================================================================
            # if project.planned_hours != 0:
            #     project.progress = i * 100.0 / project.planned_hours
            # else:
            #     project.progress = 0.0
            #===================================================================
    
    active = fields.Boolean(default=True)
    is_template_task = fields.Boolean(string='Is template task', track_visibility='onchange', default=False, copy=False)
    
    name = fields.Char(string='Title', required=True)
    project_id = fields.Many2one('project.dt', string='Parent project', track_visibility='onchange', copy=False)
    date_deadline = fields.Date("Deadline")
    reviewer_id = fields.Many2one('res.users', string='Reviewer', track_visibility='onchange', copy=True)
    user_id = fields.Many2one('res.users', string='Assigned to', track_visibility='onchange', copy=True)
    swap_id = fields.Many2one('res.users', string='Swap user', track_visibility='onchange', copy=True)
    description = fields.Text("Description")
    #progress = fields.Float(compute='_compute_progress', string="Progress")
    #progress = fields.Float("Progress")
    approved_number = fields.Char("Project code")
    
    planned_hours = fields.Float("Planned", track_visibility='onchange', copy=True)
    #effective = fields.Float("Effective", compute='_compute_subtask_effective')
    progress = fields.Float(compute='_compute_task_progress', string="Progress")
    progress2 = fields.Float(string="Progress2")
    subtask_planned_hours = fields.Float("Subtasks", compute='_compute_subtask_planned_hours', copy=True)
    
    partner_id = fields.Many2one('res.partner',
        string='Customer',
        default=lambda self: self._get_default_partner())
    company_id = fields.Many2one('res.company',
        string='Company',
        default=lambda self: self.env['res.company']._company_default_get())
    color = fields.Integer(string='Color Index', copy=True)
    
    stage_id = fields.Many2one('project.task.type.dt', string='Stage', ondelete='restrict', track_visibility='onchange', 
        default=_get_default_stage_id, group_expand='_read_group_stage_ids', copy=True)
    stage_id_sub = fields.Many2one('project.task.type.dt', string='Stage ')
    #is_sub_task = fields.Boolean(string="Sub Task", compute='_compute_is_subtask', store=True)
    project_stage_id = fields.Many2one('project.task.type.dt',string='Type of project to which the task belongs', track_visibility='onchange', copy=True)#Даалгаварт хамаарах төслийн төлөв
    is_sub_task = fields.Boolean(string="Sub Task", default=False)
    
    parent_id = fields.Many2one('task.dt', string='Parent Task')
    child_ids = fields.One2many('task.dt', 'parent_id', string='Subtasks', copy=True)
    #types_ids = fields.One2many('project.task.type.dt', 'parent_id', string="Sub-tasks", context={'active_test': False})
    subtask_project_id = fields.Many2one('project.dt', related="project_id.subtask_project_id", string='Sub-task Project', readonly=True)
    subtask_count = fields.Integer("Sub-task count", compute='_compute_subtask_count')
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ], default='0', index=True, string="Priority", copy=True)
    sequence = fields.Integer(string='Sequence', default=10,
        help="Gives the sequence order when displaying a list of tasks.")
    user_email = fields.Char(related='user_id.email', string='User Email', readonly=True, related_sudo=False)
    
    #tag_ids = fields.Many2many('tags.dt', string='Tags')
    tag_ids = fields.Many2many('tags.dt', 'task_tags_rel_dt', 'tags_dt_id', 'task_dt_id', string='Tags DT', copy=False)
    kanban_state = fields.Selection([
        ('normal', 'Grey'),
        ('done', 'Green'),
        ('blocked', 'Red')], string='Kanban State',
        copy=False, default='normal', required=True)
    kanban_state_label = fields.Char(compute='_compute_kanban_state_label', string='Kanban State Label', track_visibility='onchange')
    legend_blocked = fields.Char(related='stage_id.legend_blocked', string='Kanban Blocked Explanation', readonly=True, related_sudo=False)
    legend_done = fields.Char(related='stage_id.legend_done', string='Kanban Valid Explanation', readonly=True, related_sudo=False)
    legend_normal = fields.Char(related='stage_id.legend_normal', string='Kanban Ongoing Explanation', readonly=True, related_sudo=False)
    
    
    def action_close_task(self):
        for task in self:
            if task.is_sub_task == False:
                last_stage = self.env['project.task.type.dt'].search([('is_sub_task','=',False),('project_ids','=',False),('is_last_stage','=',True)])
                if task.child_ids:
                    for line2 in task.child_ids:
                        last_stage2 = self.env['project.task.type.dt'].search([('is_sub_task','=',True),('is_project','=',False),('is_last_stage','=',True)])
                        line2.write({'stage_id_sub': last_stage2.id,
                                     'progress2': 100.0})
                    self.write({'stage_id': last_stage.id})
                else:
                    self.write({'stage_id': last_stage.id})
            else:
                last_stage = self.env['project.task.type.dt'].search([('is_sub_task','=',True),('is_project','=',False),('is_last_stage','=',True)])
                self.write({'stage_id_sub': last_stage.id,
                            'progress2': 100.0})
    
    def action_open_task(self):
        for task in self:
            if task.is_sub_task == False:
                last_stage = self.env['project.task.type.dt'].search([('is_sub_task','=',False),('is_project','=',False)], order='id asc',limit=1)
                for line2 in task.child_ids:
                    last_stage2 = self.env['project.task.type.dt'].search([('is_sub_task','=',True),('is_project','=',False)], order='id asc',limit=1)
                    line2.write({'stage_id_sub': last_stage2.id,
                                 'progress2': 0.0})
                self.write({'stage_id': last_stage.id})
            else:
                last_stage = self.env['project.task.type.dt'].search([('is_sub_task','=',True),('is_project','=',False)], order='id asc',limit=1)
                self.write({'stage_id_sub': last_stage.id,
                            'progress2': 0.0})
                for line22 in task.parent_id:
                    last_stage22 = self.env['project.task.type.dt'].search([('is_sub_task','=',False),('is_project','=',False)], order='id asc',limit=1)
                    line22.write({'stage_id': last_stage22.id})
    
    def action_open_parent_task(self):
        return {
            'name': _('Parent Task DT'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'task.dt',
            'res_id': self.parent_id.id,
            'type': 'ir.actions.act_window'
        }
 
    def action_subtask(self):
        action = self.env.ref('project_dt.project_task_action_sub_task_dt').read()[0]
        ctx = self.env.context.copy()
        ctx.update({
            'default_parent_id': self.id,
            'default_project_id': self.env.context.get('project_id', self.project_id.id),
            'default_name': self.env.context.get('name', self.name) + ':',
            'default_partner_id': self.env.context.get('partner_id', self.partner_id.id),
            'search_default_project_id': self.env.context.get('project_id', self.project_id.id),
        })
        action['context'] = ctx
        action['domain'] = [('id', 'child_of', self.id), ('id', '!=', self.id)]
        return action

    @api.model
    def create(self, vals):
        # context: no_log, because subtype already handle this
        context = dict(self.env.context, mail_create_nolog=True)
        # force some parent values, if needed
        if 'parent_id' in vals and vals['parent_id']:
            vals['is_sub_task'] = True
            #vals.update(self._subtask_values_from_parent(vals['parent_id']))
            context.pop('default_parent_id', None)
        if 'parent_id' in vals and vals['parent_id'] == False:
            vals['is_sub_task'] = False
        # for default stage
        if vals.get('project_id') and not context.get('default_project_id'):
            context['default_project_id'] = vals.get('project_id')
        # user_id change: update date_assign
        if vals.get('user_id'):
            vals['date_assign'] = fields.Datetime.now()
        # Stage change: Update date_end if folded stage and date_last_stage_update
        if vals.get('stage_id'):
            #vals.update(self.update_date_end(vals['stage_id']))
            vals['date_last_stage_update'] = fields.Datetime.now()
        task = super(TaskDt, self.with_context(context)).create(vals)
        return task

    @api.multi
    def write(self, vals):
        now = fields.Datetime.now()
        # subtask: force some parent values, if needed
        if 'parent_id' in vals and vals['parent_id']:
            #vals.update(self._subtask_values_from_parent(vals['parent_id']))
            vals['is_sub_task'] = True
        if 'parent_id' in vals and vals['parent_id'] == False:
            #vals.update(self._subtask_values_from_parent(vals['parent_id']))
            vals['is_sub_task'] = False
        # stage change: update date_last_stage_update
        if 'stage_id' in vals:
            last_stage = self.env['project.task.type.dt'].search([('id','=',vals['stage_id'])])
            if last_stage.is_last_stage == True:
                vals['progress'] = 100.0
            else:
                vals['progress'] = 0.0
            #vals.update(self.update_date_end(vals['stage_id']))
            vals['date_last_stage_update'] = now
            # reset kanban state when changing stage
            if 'kanban_state' not in vals:
                vals['kanban_state'] = 'normal'
        if 'stage_id_sub' in vals:
            last_stage_sub = self.env['project.task.type.dt'].search([('id','=',vals['stage_id_sub'])])
            if last_stage_sub.is_last_stage == True:
                vals['progress2'] = 100.0
            else:
                vals['progress2'] = 0.0
        # user_id change: update date_assign
        if vals.get('user_id') and 'date_assign' not in vals:
            vals['date_assign'] = now

        result = super(TaskDt, self).write(vals)
        # rating on stage
        #=======================================================================
        # if 'stage_id' in vals and vals.get('stage_id'):
        #     self.filtered(lambda x: x.project_id.rating_status == 'stage')._send_task_rating_mail(force_send=True)
        #=======================================================================
        # subtask: update subtask according to parent values
        subtask_values_to_write = self._subtask_write_values(vals)
        if subtask_values_to_write:
            subtasks = self.filtered(lambda task: not task.parent_id).mapped('child_ids')
            if subtasks:
                subtasks.write(subtask_values_to_write)
        return result

    @api.model
    def _subtask_implied_fields(self):
        """ Return the list of field name to apply on subtask when changing parent_id or when updating parent task. """
        return ['partner_id', 'email_from']

    @api.multi
    def _subtask_write_values(self, values):
        """ Return the values to write on subtask when `values` is written on parent tasks
            :param values: dict of values to write on parent
        """
        result = {}
        for field_name in self._subtask_implied_fields():
            if field_name in values:
                result[field_name] = values[field_name]
        return result

    def _subtask_values_from_parent(self, parent_id):
        """ Get values for substask implied field of the given"""
        result = {}
        parent_task = self.env['task.dt'].browse(parent_id)
        for field_name in self._subtask_implied_fields():
            result[field_name] = parent_task[field_name]
        return self._convert_to_write(result)
    

class TagsDt(models.Model):
    _name = "tags.dt"
    _description = "Mini Design team"

    name = fields.Char(required=True)
    color = fields.Integer(string='Color Index')
    task_dt_ids = fields.Many2many('task.dt', 'task_tags_rel_dt', 'task_dt_id', 'tags_dt_id', string='Tasks DT')
#===============================================================================
# 
#     _sql_constraints = [
#         ('name_uniq', 'unique (name)', "Tag name already exists!"),
#     ]
#===============================================================================

class DocDt(models.Model):
    _name = "doc.dt"
    _description = "Doc DT"

    name = fields.Char(string="Name", required=True)


class Attachment(models.Model):
    _inherit = 'ir.attachment'
      
    doc_type = fields.Many2one('doc.dt', string="DOC type", required=True)
    #project_dt = fields.Many2one('project.dt', string="Project DT")
    #task_dt = fields.Many2one('task.dt', string="Task DT")
     
    

class Employee(models.Model):
    _inherit = "hr.employee"

    def tb_project_view_dt(self):
        self.ensure_one()
        domain = [
            ('members', '=', self.user_id.id),('members', '!=', False)]
        return {
            'name': _('DT Projects'),
            'domain': domain,
            'res_model': 'project.dt',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'view_type': 'form',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        Documents are attached to the tasks and issues of your project.</p><p>
                        Send messages or log internal notes with attachments to link
                        documents to your project.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d,'default_project_id': %d}" % (self._name, self.id, self.id)
        }
    
    def _compute_project_count_dt(self):
        for emp in self:
            projects = self.env['project.dt'].search([('members', '=', emp.user_id.id),('members', '!=', False)]).ids
            emp.project_count_dt = len(projects)
        
    

    def tb_task_reviewer_view_dt(self):
        self.ensure_one()
        domain = [
            ('reviewer_id', '=', self.user_id.id),('reviewer_id', '!=', False)]
        return {
            'name': _('Task to Review'),
            'domain': domain,
            'res_model': 'task.dt',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'view_type': 'form',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        Documents are attached to the tasks and issues of your project.</p><p>
                        Send messages or log internal notes with attachments to link
                        documents to your project.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d,'default_task_id': %d}" % (self._name, self.id, self.id)
        }
    
    def _compute_task_count_reviewer_dt(self):
        for emp in self:
            tasks = self.env['task.dt'].search([('reviewer_id', '=', emp.user_id.id),('reviewer_id', '!=', False)]).ids
            emp.task_count_reviewer_dt = len(tasks)

    def tb_task_user_view_dt(self):
        self.ensure_one()
        domain = [
            ('user_id', '=', self.user_id.id),('user_id', '!=', False)]
        return {
            'name': _('Tasks to Assign'),
            'domain': domain,
            'res_model': 'task.dt',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'view_type': 'form',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        Documents are attached to the tasks and issues of your project.</p><p>
                        Send messages or log internal notes with attachments to link
                        documents to your project.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d,'default_task_id': %d}" % (self._name, self.id, self.id)
        }
    
    def _compute_task_count_user_dt(self):
        for emp in self:
            tasks = self.env['task.dt'].search([('user_id', '=', emp.user_id.id),('user_id', '!=', False)]).ids
            emp.task_count_user_dt = len(tasks)

    def tb_task_swap_view_dt(self):
        self.ensure_one()
        domain = [
            ('swap_id', '=', self.user_id.id),('swap_id', '!=', False)]
        return {
            'name': _('Tasks to Swap'),
            'domain': domain,
            'res_model': 'task.dt',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'view_type': 'form',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        Documents are attached to the tasks and issues of your project.</p><p>
                        Send messages or log internal notes with attachments to link
                        documents to your project.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d,'default_task_id': %d}" % (self._name, self.id, self.id)
        }
    
    def _compute_task_count_swap_dt(self):
        for emp in self:
            tasks = self.env['task.dt'].search([('swap_id', '=', emp.user_id.id),('swap_id', '!=', False)]).ids
            emp.task_count_swap_dt = len(tasks)
        


    #task_ids = fields.One2many('project.task', 'project_id', string='Tasks')
    #project_count = fields.Integer(compute='_compute_project_count', string="Project Count")
    project_count_dt = fields.Integer(compute='_compute_project_count_dt', string="Project Count")
    task_count_reviewer_dt = fields.Integer(compute='_compute_task_count_reviewer_dt', string="Task Count Reviewer")
    task_count_user_dt = fields.Integer(compute='_compute_task_count_user_dt', string="Task Count User")
    task_count_swap_dt = fields.Integer(compute='_compute_task_count_swap_dt', string="Task Count Swap")
    
    
    
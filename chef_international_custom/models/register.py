from odoo import api, fields, models, _


class DonorRegistration(models.Model):
    _inherit = 'account.payment'

    document_no = fields.Char('Document No')
    NTN_NIC = fields.Char('NTN/NIC')
    project_name = fields.Many2one('project.project')
    activity = fields.Char('Activity')


class CrossoveredBudget(models.Model):
    _inherit = 'crossovered.budget'

    donor_id = fields.Many2one('res.partner')
    project_id = fields.Many2one('project.project')


class CrossoveredBudgetLines(models.Model):
    _inherit = 'crossovered.budget.lines'

    balance = fields.Float(compute='get_balance')

    def get_balance(self):
        for rec in self:
            rec.balance = rec.planned_amount + rec.practical_amount


class ResPartner(models.Model):
    _inherit = 'res.partner'

    donor_code = fields.Char()
    is_organization = fields.Boolean()
    strn = fields.Char()
    company_type = fields.Selection(string='Company Type',
                                    selection=[('person', 'Individual'), ('company', 'Company'),
                                               ('organization', 'Organization')])

    @api.onchange('company_type')
    def on_change_company_type(self):
        for rec in self:
            if rec.company_type == 'organization':
                rec.is_organization = True
            else:
                rec.is_organization = False

    def _compute_company_type(self):
        for partner in self:
            if partner.is_organization:
                partner.company_type = 'organization'
            else:
                partner.company_type = 'company' if partner.is_company else 'person'

    def write(self, vals):
        partners = self.env['res.partner'].search_count([])
        if partners > 0:
            str_partner = str(partners)
            inc_partner = partners + 1
            if len(str_partner) == 1 and partners != 9:
                donor_code = '10000' + str(inc_partner)
            elif len(str_partner) == 2 and partners != 99 or partners == 9:
                donor_code = '1000' + str(inc_partner)
            elif len(str_partner) == 3 and partners != 999 or partners == 99:
                donor_code = '100' + str(inc_partner)
            elif len(str_partner) == 4 and partners != 9999 or partners == 999:
                donor_code = '10' + str(inc_partner)
            elif len(str_partner) == 5 or partners == 9999:
                donor_code = '1' + str(inc_partner)
        else:
            donor_code = '100001'
        vals.update({'donor_code': donor_code})
        res = super(ResPartner, self).write(vals)
        return res


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    expense_code = fields.Char(compute='get_code')
    budget_id = fields.Many2one('crossovered.budget')
    budget_position = fields.Many2one('account.budget.post', string='Budgetary Position')

    @api.onchange('budget_id')
    def on_budget_change(self):
        for rec in self:
            values = []
            for i in rec.budget_id.crossovered_budget_line:
                values.append(i.general_budget_id.id)
            return {'domain': {'budget_position': [('id', 'in', values)]}}

    def action_register_payment(self):
        res = super(HrExpense, self).action_register_payment()
        for order in self:
            res['context'] = {
                'default_budget_id': order.budget_id.id,
                'default_budget_position': order.budget_position.id,
            }
        return res

    def action_submit_expenses(self):
        res = super(HrExpense, self).action_submit_expenses()
        for order in self:
            res['context'] = {
                'default_budget_id': order.budget_id.id,
                'default_budget_position': order.budget_position.id,
            }
        return res

    def get_code(self):
        for rec in self:
            expences = self.env['hr.expense'].search_count([])
            if expences > 0:
                str_expence = str(expences)
                inc_expence = expences + 1
                if len(str_expence) == 1 and expences != 9:
                    rec.expense_code = '10000' + str(rec.id)
                elif len(str_expence) == 2 and expences != 99 or expences == 9:
                    rec.expense_code = '1000' + str(rec.id)
                elif len(str_expence) == 3 and expences != 999 or expences == 99:
                    rec.expense_code = '100' + str(rec.id)
                elif len(str_expence) == 4 and expences != 9999 or expences == 999:
                    rec.expense_code = '10' + str(rec.id)
                elif len(str_expence) == 5 or expences == 9999:
                    rec.expense_code = '1' + str(rec.id)
            else:
                rec.expense_code = '100001'


class Project(models.Model):
    _inherit = 'project.project'

    def write(self, vals):
        partners_value = vals.get('partner_id')
        if partners_value is not None:
            projects = self.env['project.project'].search_count([('partner_id', '=', vals['partner_id'])])
            partner = self.env['res.partner'].search([('id', '=', vals['partner_id'])])
        else:
            projects = self.env['project.project'].search_count([('partner_id', '=', self.partner_id.id)])
            partner = self.env['res.partner'].search([('id', '=', self.partner_id.id)])
        if projects >= 1:
            if projects == 1:
                inc_project = projects
            else:
                inc_project = projects + 1
            if len(str(projects)) == 1:
                str_c = '-0'
            else:
                str_c = '-'
            project_code = str(partner.donor_code) + str_c + str(inc_project)
        else:
            project_code = str(partner.donor_code) + '-01'
        vals.update({'project_code': project_code})
        res = super(Project, self).write(vals)
        return res

    project_code = fields.Char()


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_nature = fields.Char()


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    budget_id = fields.Many2one('crossovered.budget')
    budget_position = fields.Many2one('account.budget.post', string='Budgetary Position')

    @api.onchange('budget_id')
    def on_budget_change(self):
        for rec in self:
            values = []
            for i in rec.budget_id.crossovered_budget_line:
                values.append(i.general_budget_id.id)
            return {'domain': {'budget_position': [('id', 'in', values)]}}

    def action_create_invoice(self):
        res = super(PurchaseOrder, self).action_create_invoice()
        for order in self:
            move = res['res_id']
            if move:
                move_obj = self.env['account.move'].browse(move)
                try:
                    move_obj.write({
                        'budget_id': order.budget_id.id,
                        'budget_position': order.budget_position.id,

                    })
                except Exception as e:
                    pass
        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    budget_position = fields.Many2one('account.budget.post')

    @api.onchange('analytic_account_id')
    def onchange_analytic_account_id(self):
        account_analytic_obj = self.env['account.analytic.account'].search([('id', '=', self.analytic_account_id.id)])
        if account_analytic_obj:
            budgetry_position_list = []
            for i in account_analytic_obj.crossovered_budget_line:
                # if self.move_id.budget_id == i.crossovered_budget_id:
                budgetry_position_list.append(i.general_budget_id.id)
        domain = [('id', 'in', budgetry_position_list)]
        # Update the domain of the Many2one field
        return {'domain': {'budget_position': domain}}


class AccountMove(models.Model):
    _inherit = 'account.move'

    document_no = fields.Char('Document No')
    # ntn_nic = fields.Char('NTN/NIC')
    ntn_nic = fields.Char('NTN/NIC', related='partner_id.vat')
    budget_id = fields.Many2one('crossovered.budget')
    budget_position = fields.Many2one('account.budget.post', string='Budgetary Position')
    hide = fields.Boolean(compute='get_hide')
    hide_confirm = fields.Boolean(default=True)
    click_check = fields.Boolean(default=False)
    partner_id = fields.Many2one('res.partner')



    # @api.model_create_multi()
    def name_get(self):
        result = []
        for record in self:
            name = record.journal_id.name
            result.append((record.id, name))
        return result

    def action_post(self):
        res = super().action_post()
        budget = self.env['crossovered.budget'].browse(self.budget_id.id)
        if budget:
            for i in budget.crossovered_budget_line:
                for x in self.line_ids:
                    if x.debit > 0:
                        if x.analytic_account_id == i.analytic_account_id and x.budget_position == i.general_budget_id:
                            i.practical_amount = x.debit
                            i.balance = i.balance + x.debit

        return res

    def get_hide(self):
        for rec in self:
            if self.env.user.has_group('chef_international_custom.group_approval_right'):
                if not rec.click_check:
                    rec.hide = False
                    rec.hide_confirm = True
                else:
                    rec.hide_confirm = False
                    rec.hide = True
            else:
                rec.hide = True

    def action_approve(self):
        for rec in self:
            rec.hide_confirm = False
            rec.hide = True
            rec.click_check = True

    def action_register_payment(self):
        res = super(AccountMove, self).action_register_payment()
        for order in self:
            res['context'] = {
                'default_budget_id': order.budget_id.id,
                'default_budget_position': order.budget_position.id,
            }
        return res


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    budget_id = fields.Many2one('crossovered.budget')
    budget_position = fields.Many2one('account.budget.post', string='Budgetary Position')
    cheque_no = fields.Char('Cheque No')


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    budget_id = fields.Many2one('crossovered.budget')
    budget_position = fields.Many2one('account.budget.post', string='Budgetary Position')

    # def action_register_payment(self):
    #   res = super(HrExpenseSheet, self).action_register_payment()
    #  for order in self:
    #     res['context'] = {
    #        'default_budget_id': order.budget_id.id,
    #       'default_budget_position': order.budget_position.id,
    #  }
    # return res

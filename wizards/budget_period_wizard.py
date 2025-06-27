# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class BudgetPeriodWizard(models.TransientModel):
    """Мастер создания бюджетных периодов"""
    _name = 'budget.period.wizard'
    _description = 'Мастер создания бюджетных периодов'

    year = fields.Integer('Рік', required=True, default=lambda self: datetime.now().year)
    period_type = fields.Selection([
        ('month', 'Місячні періоди'),
        ('quarter', 'Квартальні періоди'),
        ('year', 'Річний період'),
        ('all', 'Всі типи періодів')
    ], 'Тип періодів', required=True, default='month')

    company_ids = fields.Many2many('res.company', string='Підприємства')
    create_for_all_companies = fields.Boolean('Створити для всіх компаній', default=True)

    start_month = fields.Selection([
        ('1', 'Січень'), ('2', 'Лютий'), ('3', 'Березень'), ('4', 'Квітень'),
        ('5', 'Травень'), ('6', 'Червень'), ('7', 'Липень'), ('8', 'Серпень'),
        ('9', 'Вересень'), ('10', 'Жовтень'), ('11', 'Листопад'), ('12', 'Грудень')
    ], 'Початковий місяць', default='1')

    end_month = fields.Selection([
        ('1', 'Січень'), ('2', 'Лютий'), ('3', 'Березень'), ('4', 'Квітень'),
        ('5', 'Травень'), ('6', 'Червень'), ('7', 'Липень'), ('8', 'Серпень'),
        ('9', 'Вересень'), ('10', 'Жовтень'), ('11', 'Листопад'), ('12', 'Грудень')
    ], 'Кінцевий місяць', default='12')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_company_ids'):
            res['company_ids'] = [(6, 0, self.env.context.get('default_company_ids'))]
            res['create_for_all_companies'] = False
        return res

    def action_create_periods(self):
        """Створення періодів"""
        if self.create_for_all_companies:
            companies = self.env['res.company'].search([])
        else:
            companies = self.company_ids

        if not companies:
            raise UserError('Оберіть принаймні одну компанію!')

        created_periods = []

        for company in companies:
            if self.period_type in ['month', 'all']:
                created_periods.extend(self._create_monthly_periods(company))

            if self.period_type in ['quarter', 'all']:
                created_periods.extend(self._create_quarterly_periods(company))

            if self.period_type in ['year', 'all']:
                created_periods.extend(self._create_yearly_period(company))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Створені періоди',
            'res_model': 'budget.period',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', [p.id for p in created_periods])],
            'context': {'default_company_id': companies[0].id if len(companies) == 1 else False}
        }

    def _create_monthly_periods(self, company):
        """Створення місячних періодів"""
        periods = []
        month_names = {
            1: 'Січень', 2: 'Лютий', 3: 'Березень', 4: 'Квітень',
            5: 'Травень', 6: 'Червень', 7: 'Липень', 8: 'Серпень',
            9: 'Вересень', 10: 'Жовтень', 11: 'Листопад', 12: 'Грудень'
        }

        for month in range(int(self.start_month), int(self.end_month) + 1):
            # Перевіряємо чи не існує вже такий період
            existing = self.env['budget.period'].search([
                ('company_id', '=', company.id),
                ('period_type', '=', 'month'),
                ('date_start', '=', date(self.year, month, 1))
            ])

            if existing:
                continue

            date_start = date(self.year, month, 1)
            date_end = date_start + relativedelta(months=1) - relativedelta(days=1)

            period = self.env['budget.period'].create({
                'name': f"{month_names[month]} {self.year}",
                'period_type': 'month',
                'date_start': date_start,
                'date_end': date_end,
                'company_id': company.id,
                'state': 'draft'
            })
            periods.append(period)

        return periods

    def _create_quarterly_periods(self, company):
        """Створення квартальних періодів"""
        periods = []
        quarters = [
            (1, 'I квартал', 1, 3),
            (2, 'II квартал', 4, 6),
            (3, 'III квартал', 7, 9),
            (4, 'IV квартал', 10, 12)
        ]

        for quarter_num, quarter_name, start_month, end_month in quarters:
            # Перевіряємо перетин з обраним діапазоном
            if end_month < int(self.start_month) or start_month > int(self.end_month):
                continue

            # Перевіряємо чи не існує вже такий період
            existing = self.env['budget.period'].search([
                ('company_id', '=', company.id),
                ('period_type', '=', 'quarter'),
                ('date_start', '=', date(self.year, start_month, 1))
            ])

            if existing:
                continue

            date_start = date(self.year, start_month, 1)
            date_end = date(self.year, end_month + 1, 1) - relativedelta(days=1) if end_month < 12 else date(self.year,
                                                                                                             12, 31)

            period = self.env['budget.period'].create({
                'name': f"{quarter_name} {self.year}",
                'period_type': 'quarter',
                'date_start': date_start,
                'date_end': date_end,
                'company_id': company.id,
                'state': 'draft'
            })
            periods.append(period)

        return periods

    def _create_yearly_period(self, company):
        """Створення річного періоду"""
        # Перевіряємо чи не існує вже такий період
        existing = self.env['budget.period'].search([
            ('company_id', '=', company.id),
            ('period_type', '=', 'year'),
            ('date_start', '=', date(self.year, 1, 1))
        ])

        if existing:
            return []

        period = self.env['budget.period'].create({
            'name': f"{self.year} рік",
            'period_type': 'year',
            'date_start': date(self.year, 1, 1),
            'date_end': date(self.year, 12, 31),
            'company_id': company.id,
            'state': 'draft'
        })

        return [period]
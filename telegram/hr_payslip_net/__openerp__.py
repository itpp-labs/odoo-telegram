{
    'name': 'HR Payslip Net',
    'summary' : 'Adds payslip net filed to hr.payroll',
    'version': '1.0.0',
    'category': 'Human Resources',
    'author': 'IT-Projects LLC',
    'license': 'LGPL-3',
    'website': 'https://twitter.com/yelizariev',
    'description': """Adds net filed to hr.payroll. Takes it from details_by_salary_rule_category table where CODE == 'NET'. Can be used for reports.""",
    'depends': ['base','hr_payroll'],
    'installable': True
}

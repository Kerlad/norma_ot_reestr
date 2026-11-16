"""Training plan and «Текущая ситуация» snapshot of the summary tab (moved from employee_summary_tab)."""
import logging
from datetime import datetime

from dateutil.relativedelta import relativedelta
from PySide6.QtWidgets import QCheckBox, QDialog

from db import EmployeesRepo, EmployeeProgramsRepo
from utils.dialog_base import BaseDialog
from utils.training_rules import get_dynamic_status, compute_expiry_date
from utils.audit import log_audit
from utils.toast import Toast

logger = logging.getLogger(__name__)


def _tab_module():
    """Resolve PlanDialog through the tab module at call time (circular import; tests patch it there)."""
    import tabs.employee_summary_tab as tab_module
    return tab_module


def _show_current_snapshot(tab):
    today = datetime.now()
    plan_data = []

    for emp in EmployeesRepo.get_all():
        progs = EmployeeProgramsRepo.get_by_employee(emp['id'])
        need_progs = [p for p in progs if p.get('need_training') == 1]
        if not need_progs:
            continue

        for p in need_progs:
            prog_id = p.get('program_id', 0)
            last_exam = p.get('exam_date') or ''
            stored_status = p.get('status', 'not_trained')
            effective_status = get_dynamic_status(stored_status, last_exam, prog_id, tab._b_period_3years,
                                                  result=p.get('result'))

            if effective_status == 'not_trained':
                reason = 'Не обучен'
                priority = 'Высокий'
                expiry = (today + relativedelta(days=60)).strftime('%d.%m.%Y')
            elif effective_status == 'expired':
                reason = 'Просрочено'
                priority = 'Высокий'
                try:
                    ed = compute_expiry_date(last_exam, prog_id, tab._b_period_3years)
                    expiry = ed.strftime('%d.%m.%Y')
                except (ValueError, IndexError):
                    expiry = ''
            else:
                reason = 'Обучен'
                priority = 'Низкий'
                try:
                    ed = compute_expiry_date(last_exam, prog_id, tab._b_period_3years)
                    expiry = ed.strftime('%d.%m.%Y')
                except (ValueError, IndexError):
                    expiry = ''

            plan_data.append({
                'last_name': emp['last_name'], 'first_name': emp['first_name'],
                'middle_name': emp['middle_name'], 'snils': emp['snils'],
                'position': emp['position'], 'program': str(prog_id),
                'last_exam_date': last_exam, 'expiry_date': expiry,
                'reason': reason,
                'priority': priority,
            })

    plan_data.sort(key=lambda x: (
        {"Высокий": 0, "Средний": 1, "Низкий": 2}.get(x['priority'], 3), x['last_name']))

    if not plan_data:
        Toast.info(tab, "Нет данных для отображения")
        return

    log_audit("EXPORT_SNAPSHOT", f"rows={len(plan_data)}")

    title = f"Текущая ситуация на {today.strftime('%d.%m.%Y')}"
    plan_dlg = _tab_module().PlanDialog(plan_data, title, tab, current_mode="snapshot", on_switch=tab._switch_plan_mode)
    plan_dlg.exec()


def _generate_plan(tab, current_year=True):
    year = datetime.now().year if current_year else datetime.now().year + 1
    plan_year = year
    today = datetime.now()

    dialog = BaseDialog(tab, f"План обучения на {plan_year} год", min_width=460, min_height=320,
                        subtitle="Кого включить в план")
    layout = dialog.body_layout()

    cb_not_trained = QCheckBox("Включать не обученных"); cb_not_trained.setChecked(True)
    layout.addWidget(cb_not_trained)
    cb_expired = QCheckBox("Включать просроченных"); cb_expired.setChecked(True)
    layout.addWidget(cb_expired)
    cb_expiring = QCheckBox("Включать истекающих в планируемом году"); cb_expiring.setChecked(True)
    layout.addWidget(cb_expiring)
    cb_failed = QCheckBox("Включать неуспешно прошедших"); cb_failed.setChecked(True)
    layout.addWidget(cb_failed)

    layout.addStretch()
    plan_data = []

    def do_generate():
        employees = EmployeesRepo.get_all()
        for emp in employees:
            progs = EmployeeProgramsRepo.get_by_employee(emp['id'])
            need_progs = [p for p in progs if p.get('need_training') == 1]
            if not need_progs:
                continue

            status = tab._get_employee_status(progs)

            if status == 'not_trained' and cb_not_trained.isChecked():
                for p in need_progs:
                    prog_id = p.get('program_id', 0)
                    last_exam = p.get('exam_date') or ''
                    plan_data.append({
                        'last_name': emp['last_name'], 'first_name': emp['first_name'],
                        'middle_name': emp['middle_name'], 'snils': emp['snils'],
                        'position': emp['position'], 'program': str(prog_id),
                        'last_exam_date': last_exam,
                        'expiry_date': (today + relativedelta(days=60)).strftime('%d.%m.%Y'),
                        'reason': 'Не обучен', 'priority': 'Высокий',
                    })

            elif status == 'expired' and cb_expired.isChecked():
                for p in need_progs:
                    prog_id = p.get('program_id', 0)
                    last_exam = p.get('exam_date') or ''
                    plan_data.append({
                        'last_name': emp['last_name'], 'first_name': emp['first_name'],
                        'middle_name': emp['middle_name'], 'snils': emp['snils'],
                        'position': emp['position'], 'program': str(prog_id),
                        'last_exam_date': last_exam,
                        'expiry_date': (today + relativedelta(days=30)).strftime('%d.%m.%Y'),
                        'reason': 'Просрочено', 'priority': 'Высокий',
                    })

            else:
                if cb_expiring.isChecked():
                    for p in need_progs:
                        pid = p.get('program_id', 0)
                        last_exam = p.get('exam_date') or ''
                        if not last_exam:
                            continue
                        try:
                            expiry_date = compute_expiry_date(last_exam, pid, tab._b_period_3years)
                            if expiry_date.year == plan_year:
                                plan_data.append({
                                    'last_name': emp['last_name'], 'first_name': emp['first_name'],
                                    'middle_name': emp['middle_name'], 'snils': emp['snils'],
                                    'position': emp['position'], 'program': str(pid),
                                    'last_exam_date': last_exam,
                                    'expiry_date': expiry_date.strftime('%d.%m.%Y'),
                                    'reason': 'Истекает срок действия', 'priority': 'Средний',
                                })
                        except (ValueError, IndexError):
                            pass

                if cb_failed.isChecked():
                    failed_progs = [p for p in need_progs if p.get('result') == 0]
                    for p in failed_progs:
                        prog_id = p.get('program_id', 0)
                        last_exam = p.get('exam_date') or ''
                        plan_data.append({
                            'last_name': emp['last_name'], 'first_name': emp['first_name'],
                            'middle_name': emp['middle_name'], 'snils': emp['snils'],
                            'position': emp['position'], 'program': str(prog_id),
                            'last_exam_date': last_exam,
                            'expiry_date': (today + relativedelta(days=60)).strftime('%d.%m.%Y'),
                            'reason': 'Неудовлетворительный результат', 'priority': 'Высокий',
                        })

        n = sum(1 for x in plan_data if x['reason'] == 'Не обучен')
        e = sum(1 for x in plan_data if x['reason'] == 'Просрочено')
        t = sum(1 for x in plan_data if x['reason'] == 'Истекает срок действия')
        log_audit("EXPORT_PLAN", f"rows={len(plan_data)}, not_trained={n}, expired={e}, trained={t}")

        plan_data.sort(key=lambda x: (
            {"Высокий": 0, "Средний": 1, "Низкий": 2}.get(x['priority'], 3), x['last_name']))
        dialog.accept()

    dialog.add_action_buttons("Сформировать", do_generate)

    if dialog.exec() == QDialog.DialogCode.Rejected or not plan_data:
        if not plan_data:
            Toast.info(tab, "Нет сотрудников для включения в план")
        return

    title = f"План обучения на {plan_year} год"
    plan_dlg = _tab_module().PlanDialog(plan_data, title, tab, current_mode="year_current" if current_year else "year_next",
                          on_switch=tab._switch_plan_mode)
    plan_dlg.exec()

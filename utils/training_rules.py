"""
Training period rules for programs.
Easily removable module - delete this file and remove all references
in employee_summary_tab.py to disable this feature.

Business rule (ПП РФ № 2464 в редакции, действующей с 01.09.2026;
подтверждено владельцем продукта / специалистом по ОТ 18.10.2026):
  все программы (№1-4 и №6-29) — обучение и проверка знаний 1 раз в 3 года.
  До 01.09.2026 программы В (№6-29) — 1 раз в год: ветка b_period_3years=False,
  с v3.6.0 в UI не используется (UX-04).
Коды программ: 1-4 и 6-29 (кода 5 нет — его нет и в XSD реестра).
"""
from datetime import datetime
from dateutil.relativedelta import relativedelta


TYPE_B_PROGRAMS = set(range(6, 30))


def get_training_period_years(program_id: int, b_period_3years: bool = True) -> int:
    """
    Returns training period in years for a given program.

    Args:
        program_id: Program number (1-29)
        b_period_3years: True = type B uses 3yr (post-Sept 2026),
                         False = type B uses 1yr (pre-Sept 2026)

    Returns:
        Training period in years
    """
    if program_id in TYPE_B_PROGRAMS:
        return 3 if b_period_3years else 1
    return 3


def compute_expiry_date(exam_date_str: str, program_id: int, b_period_3years: bool = True) -> datetime:
    """
    Compute the expiry date for a program given its exam date.
    """
    if not exam_date_str:
        return None
    dt = datetime.strptime(exam_date_str.split()[0], '%d.%m.%Y')
    years = get_training_period_years(program_id, b_period_3years)
    return dt + relativedelta(years=years)


def is_program_expired(exam_date_str: str, program_id: int, b_period_3years: bool = True) -> bool:
    """
    Check if a program is expired based on exam date and training period.
    """
    try:
        expiry = compute_expiry_date(exam_date_str, program_id, b_period_3years)
    except (ValueError, IndexError, AttributeError):
        return False
    # No exam date: not trained rather than expired (status logic handles it)
    return expiry is not None and expiry < datetime.now()


def get_dynamic_status(stored_status: str, exam_date: str, program_id: int,
                       b_period_3years: bool = True, result=None) -> str:
    """
    Effective status as of today.

    The status stored in the DB is computed at sync time and goes stale: a program
    'trained' in 2024 must become 'expired' once the 3-year period ends, without
    waiting for the next registry query. So 'trained'/'expired' are always re-derived
    from the exam date. Before v3.6.0 this happened only in the 1-year mode.

    Args:
        stored_status: Status from DB ('trained', 'not_trained', 'expired', None)
        exam_date: Exam date string (DD.MM.YYYY)
        program_id: Program number
        b_period_3years: Type B period flag
        result: Exam result (0 = failed); used when stored_status is empty

    Returns:
        'trained', 'expired' or 'not_trained' (or the stored value if the date is invalid)
    """
    has_date = bool(exam_date and str(exam_date).strip())
    if not stored_status:
        if not has_date or result == 0 or result == '0':
            return 'not_trained'
        stored_status = 'trained'
    if stored_status in ('trained', 'expired') and has_date:
        try:
            expiry = compute_expiry_date(exam_date, program_id, b_period_3years)
        except (ValueError, IndexError, AttributeError):
            return stored_status
        return 'expired' if expiry < datetime.now() else 'trained'
    return stored_status

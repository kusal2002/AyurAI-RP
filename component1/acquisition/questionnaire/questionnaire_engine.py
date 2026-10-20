"""AyurAI questionnaire v1: deterministic, read-only branching demonstrator.

No patient responses are stored by this module. All included scenarios are fictional.
Question bank and eligibility must receive supervisor/ERC approval before research use.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BANK_PATH = Path(__file__).with_name('question_bank_v1.json')
RED_FLAGS = ('SAF01','SAF02','SAF03','SAF04')


def load_bank(path: Path = BANK_PATH) -> dict[str, Any]:
    bank = json.loads(path.read_text(encoding='utf-8'))
    questions = bank.get('questions', [])
    ids = [q['id'] for q in questions]
    if not questions or len(ids) != len(set(ids)):
        raise ValueError('Question bank is empty or contains duplicate question IDs.')
    return bank


def get_field(field: str, profile: dict, answers: dict) -> Any:
    prefix, sep, key = field.partition('.')
    if not sep:
        raise ValueError('Condition must use profile.X or answers.X')
    if prefix == 'profile':
        return profile.get(key)
    if prefix == 'answers':
        return answers.get(key)
    raise ValueError('Unsupported condition prefix: ' + prefix)


def matches(rule: dict | None, profile: dict, answers: dict) -> bool:
    """No eval() or AI decisions; only explicit whitelist operators."""
    if rule is None:
        return True
    if 'all' in rule:
        return all(matches(x, profile, answers) for x in rule['all'])
    if 'any' in rule:
        return any(matches(x, profile, answers) for x in rule['any'])
    value = get_field(rule['field'], profile, answers)
    if value is None:
        return False
    operator = rule['op']
    compare = rule['value']
    if operator == 'eq':
        return value == compare
    if operator == 'lt':
        return isinstance(value, (float, int)) and not isinstance(value, bool) and value < compare
    if operator == 'gte':
        return isinstance(value, (float, int)) and not isinstance(value, bool) and value >= compare
    raise ValueError('Unsupported rule operator: ' + operator)


def get_visible_questions(bank: dict, profile: dict, answers: dict) -> list[dict]:
    """Return currently applicable questions in source-bank order."""
    questions = [q for q in bank['questions'] if matches(q.get('when'), profile, answers)]
    if any(answers.get(qid) == 'yes' for qid in RED_FLAGS) or (profile.get('pregnancy_status') == 'pregnant' and answers.get('PR06') == 'yes'):
        return [q for q in questions if q['section'] in ('registration', 'immediate_safety', 'clinical_review')]
    if answers.get('REG05') != 'yes':
        return [q for q in questions if q['section'] in ('registration', 'immediate_safety')]
    return questions


def get_status(profile: dict, answers: dict) -> dict:
    safety_triggers = [qid for qid in RED_FLAGS if answers.get(qid) == 'yes']
    if profile.get('pregnancy_status') == 'pregnant' and answers.get('PR06') == 'yes':
        safety_triggers.append('PR06')
    consent_ok = answers.get('REG05') == 'yes'
    if isinstance(profile.get('age_months'), int) and profile['age_months'] < 216:
        consent_ok = consent_ok and answers.get('CH02') == 'yes'  # Guardian permission
    ppg_consent = answers.get('REG06') == 'yes'
    image_consent = answers.get('REG07') == 'yes'
    ppg_discomfort = [qid for qid in ('P02','P05','P06') if answers.get(qid) == 'yes']
    return {
        'questionnaire_version': '1.0.0-prototype',
        'study_eligibility': 'pending_clinical_supervisor_and_erc_approval',
        'child_minimum_age_approved': False,
        'urgent_clinician_review': bool(safety_triggers),
        'urgent_response_ids': safety_triggers,
        'can_continue_prototype_capture': consent_ok and not bool(safety_triggers),
        'ppg_acquisition_allowed': consent_ok and ppg_consent and not bool(safety_triggers) and not bool(ppg_discomfort),
        'image_acquisition_allowed': consent_ok and image_consent and not bool(safety_triggers) and answers.get('IMG05') != 'yes',
        'ppg_discomfort_response_ids': ppg_discomfort,
        'clinical_risk_category': None,
        'notes': 'Flags are for clinician review and prototype capture control; no diagnosis or autonomous triage.'
    }


def validate_answers(bank: dict, answers: dict) -> None:
    by_id = {q['id']: q for q in bank['questions']}
    invalid_ids = set(answers) - set(by_id)
    if invalid_ids:
        raise ValueError('Answers contain unknown question ID(s): ' + str(sorted(invalid_ids)))
    for qid, value in answers.items():
        question = by_id[qid]
        if question['type'] == 'choice' and value not in question['options']:
            raise ValueError(f'Invalid answer for {qid}: {value!r}; valid: {question["options"]}')
        if question['type'] == 'integer' and not isinstance(value,int):
            raise ValueError(f'{qid} must be an integer')
        if question['type'].startswith('repeatable_') and not isinstance(value,list):
            raise ValueError(f'{qid} must be a list of structured items')


def print_demo(bank: dict, scenario: str):
    profile: dict[str, Any] = {
        'age_months': 360,
        'pregnancy_status': 'not_pregnant',
        'collect_ppg': True,
        'collect_images': True,
        'include_asthavidha': False,
        'include_review': True,
        'demo': True,
    }
    answers = {
        'REG05': 'yes', 'REG06': 'yes', 'REG07': 'yes',
        'SAF01': 'no', 'SAF02': 'no', 'SAF03': 'no', 'SAF04': 'no',
        'C01': 'yes', 'C08': 'no', 'C09': 'no', 'C10': 'no',
        'C15': 'yes', 'C16': 'yes', 'C17': 'yes',
        'C20': 'no',
    }
    if scenario == 'child':
        profile['age_months'] = 36
        profile['pregnancy_status'] = 'not_applicable'
        answers['REG04'] = 'parent_or_guardian'
        answers['CH02'] = 'yes'
    elif scenario == 'pregnancy':
        profile['pregnancy_status'] = 'pregnant'
        answers['C20'] = 'yes'
    elif scenario == 'urgent':
        answers['SAF01'] = 'yes'
    elif scenario != 'adult':
        raise ValueError('Unknown demo scenario')
    validate_answers(bank, answers)
    visible = get_visible_questions(bank,profile,answers)
    sections = {}
    for q in visible: sections[q['section']] = sections.get(q['section'],0)+1
    status = get_status(profile,answers)
    print(f'\nSCENARIO: {scenario.upper()} — FICTIONAL RESPONSES ONLY')
    print('Questions visible:',len(visible))
    print('Active sections:',', '.join(f'{k}({v})' for k,v in sections.items()))
    for chosen in ('SY01','CH01','CH08','CH09','PR01','MED01','MED02','ALG01','P05'):
        if any(q['id'] == chosen for q in visible):
            q = next(q for q in visible if q['id']==chosen)
            print(f'  Example branch: {chosen}: {q["prompt"]}')
    print('Safety / capture state:',json.dumps({k:status[k] for k in ('urgent_clinician_review','can_continue_prototype_capture','ppg_acquisition_allowed','image_acquisition_allowed','clinical_risk_category')}))
    return visible,status


def smoke_test(bank: dict) -> None:
    # Deterministic branch smoke tests — no real patient data.
    p={'age_months': 360, 'pregnancy_status':'not_pregnant','collect_ppg': True,'collect_images':True}
    a={'REG05':'yes','REG06':'yes','REG07':'yes','C01':'yes','C15':'yes','SAF01':'no'}
    base={q['id'] for q in get_visible_questions(bank,p,a)}
    assert 'SY01' in base and 'MED01' in base and 'CH01' not in base and 'PR01' not in base
    assert 'MEN01' not in base
    assert 'P05' in base and 'IMG01' in base
    p['age_months']=12
    child={q['id'] for q in get_visible_questions(bank,p,a)}
    assert 'CH01' in child and 'CH08' in child and 'CH09' not in child
    p['age_months']=120
    older={q['id'] for q in get_visible_questions(bank,p,a)}
    assert 'CH08' not in older and 'CH09' in older
    p['age_months']=312
    p['pregnancy_status']='pregnant'
    pregnant={q['id'] for q in get_visible_questions(bank,p,a)}
    assert 'PR01' in pregnant
    a['REG07']='no'
    assert 'IMG01' not in {q['id'] for q in get_visible_questions(bank,p,a)}
    assert not get_status(p,a)['image_acquisition_allowed']
    a['REG07']='yes'
    a['SAF01']='yes'
    assert get_status(p,a)['urgent_clinician_review']
    assert 'C01' not in {q['id'] for q in get_visible_questions(bank,p,a)}
    assert not get_status(p,a)['can_continue_prototype_capture']
    a['SAF01']='no'
    a['P05']='yes'
    assert not get_status(p,a)['ppg_acquisition_allowed']
    print('Branch checks passed: adult / infant / child / pregnancy / consent / urgent / PPG discomfort')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--demo', choices=['adult','child','pregnancy','urgent','all'], default='all')
    args=ap.parse_args()
    bank=load_bank()
    print('AYURAI QUESTIONNAIRE BRANCHING ENGINE (PROTOTYPE)')
    print('Question bank:',BANK_PATH)
    print('Version:',bank['version'],'| Questions:',len(bank['questions']))
    print('Approval:',bank['approval_status'])
    smoke_test(bank)
    scenarios=['adult','child','pregnancy','urgent'] if args.demo=='all' else [args.demo]
    for s in scenarios:print_demo(bank,s)
    print('\nNo database written, no patient information collected.')

if __name__ == '__main__':
    main()

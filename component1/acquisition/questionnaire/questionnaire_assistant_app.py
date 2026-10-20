"""AyurAI short adaptive questionnaire — FICTIONAL DEMO ONLY.

Run from repository root:
  .\\component1\\.venv\\Scripts\\python.exe -m streamlit run .\\component1\\acquisition\\questionnaire\\questionnaire_assistant_app.py

The question bank is unchanged. Prototype is not approved for real patient data.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from questionnaire_engine import load_bank, validate_answers, get_status, matches

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT.parent / 'datasets'
BANK = load_bank()
QUESTION_BY_ID = {q['id']: q for q in BANK['questions']}
SESSION_PATTERN = re.compile(r'demo_[0-9a-fA-F]{8}')

# Ten fixed questions; the first four double as the mandatory safety screen.
COMMON_IDS = ('SAF01','SAF02','SAF03','SAF04',
              'C01','C02','C03','C06','C08','C10')
MAX_FOLLOWUPS = 10
FOLLOWUP_ORDER = (
    'BL01','BL02','BL03',                 # Recent bleeding
    'PR01','PR02','PR03','PR04','PR05',   # Pregnancy
    'CH04','CH06','CH08','CH09',         # Age-appropriate child history
    'LAB01','LAB02',                    # Previous anaemia (if applicable)
    'SY01','SY02','SY04',               # Symptoms
)
STAGES = ('age','sex','consent','common','followups','medications','allergies','review')


def profile_for(age_months: int, sex: str, pregnancy_status: str) -> dict:
    if age_months < 0 or age_months > 12*120:
        raise ValueError('Invalid age')
    return {
        'age_months': age_months,
        'sex_reported_for_demo': sex,
        'pregnancy_status': pregnancy_status,
        'collect_ppg': True,
        'collect_images': True,
        'include_asthavidha': False,
        'include_review': False,
        'demo': True,
    }


def select_followups(profile: dict, answers: dict) -> list[str]:
    """Select at most ten relevant bank questions, once common questions finish."""
    result = []
    for qid in FOLLOWUP_ORDER:
        q = QUESTION_BY_ID[qid]
        if matches(q.get('when'), profile, answers):
            result.append(qid)
        if len(result) == MAX_FOLLOWUPS:
            break
    return result


def safety_state(profile: dict, answers: dict) -> dict:
    base = dict(get_status(profile, answers))
    checks = list(COMMON_IDS[:4])
    if profile.get('pregnancy_status') == 'pregnant':
        checks.append('PR06')
    unclear = [qid for qid in checks if answers.get(qid) not in ('yes','no')]
    triggered = [qid for qid in checks if answers.get(qid) == 'yes']
    if triggered or unclear:
        base['can_continue_prototype_capture'] = False
        base['ppg_acquisition_allowed'] = False
        base['image_acquisition_allowed'] = False
    base['urgent_clinician_review'] = bool(triggered)
    base['safety_unresolved'] = unclear
    # Finger-contact safety must be checked in the later sensor workflow.
    base['ppg_acquisition_allowed'] = False
    base['ppg_pending_finger_comfort_check'] = True
    base['clinical_risk_category'] = None
    return base


def parse_items(raw: str, kind: str) -> list[dict]:
    """Accept one fictional item per line: name | details."""
    entries = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        p = [s.strip() for s in line.split('|',1)]
        if not p[0]:
            continue
        if kind == 'medication':
            entries.append({'name': p[0], 'dose_or_details': p[1] if len(p)>1 else 'not_provided'})
        else:
            entries.append({'substance': p[0], 'reaction_or_details': p[1] if len(p)>1 else 'not_provided'})
    return entries


def finalize_answers(age_months: int, consent_ppg: bool, consent_images: bool,
                     consent: bool, answers: dict, meds: str, herbals: str,
                     allergies: str, no_meds: bool, no_allergies: bool) -> dict:
    """Convert final two interview screens to original bank IDs."""
    if not consent:
        raise ValueError('Consent not given; no questionnaire will be saved')
    if not (no_meds or meds.strip() or herbals.strip()):
        raise ValueError('Please answer the medication question')
    if not (no_allergies or allergies.strip()):
        raise ValueError('Please answer the allergies question')
    if no_meds and (meds.strip() or herbals.strip()):
        raise ValueError('Choose either no medications or list the medications')
    if no_allergies and allergies.strip():
        raise ValueError('Choose either no allergies or list the allergies')
    result = dict(answers)
    result['REG02'] = age_months
    result['REG05'] = 'yes'
    result['REG06'] = 'yes' if consent_ppg else 'no'
    result['REG07'] = 'yes' if consent_images else 'no'
    result['C15'] = 'yes' if meds.strip() else 'no'
    result['C16'] = 'yes' if herbals.strip() else 'no'
    result['C17'] = 'yes' if allergies.strip() else 'no'
    if meds.strip():
        result['MED01'] = parse_items(meds,'medication')
    if herbals.strip():
        result['MED02'] = parse_items(herbals,'medication')
    if allergies.strip():
        result['ALG01'] = parse_items(allergies,'allergy')
    validate_answers(BANK,result)
    return result


def save_demo(session_id: str, profile: dict, answers: dict, data_root: Path=DATA_ROOT) -> dict:
    """Store only fictional data, in the same questionnaire_responses SQLite schema."""
    if not SESSION_PATTERN.fullmatch(session_id):
        raise ValueError('Use a demo_XXXXXXXX session ID')
    if not (data_root/'live_sessions'/session_id/'manifest.json').is_file():
        raise FileNotFoundError('Existing webcam demo session manifest not found')
    if not profile.get('demo') or answers.get('REG05') != 'yes':
        raise ValueError('Only consented fictional demonstrations can be saved')
    validate_answers(BANK,answers)
    status = safety_state(profile, answers)
    if status['urgent_clinician_review'] or status['safety_unresolved']:
        raise ValueError('Clinician review required; routine questionnaire save is blocked')
    scenario = ('child' if profile['age_months'] < 216 else
                'pregnancy' if profile['pregnancy_status']=='pregnant' else 'adult')
    data_root.mkdir(parents=True,exist_ok=True)
    db=data_root/'screening_sessions.sqlite3'
    with sqlite3.connect(db) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS questionnaire_responses (
            session_id TEXT PRIMARY KEY,
            question_bank_version TEXT NOT NULL,
            scenario TEXT NOT NULL,
            is_fictional_demo INTEGER NOT NULL CHECK(is_fictional_demo=1),
            profile_json TEXT NOT NULL,
            answers_json TEXT NOT NULL,
            status_json TEXT NOT NULL,
            completion_status TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL)''')
        conn.execute('''INSERT INTO questionnaire_responses
             (session_id,question_bank_version,scenario,is_fictional_demo,
              profile_json,answers_json,status_json,completion_status,updated_at_utc)
             VALUES (?,?,?,1,?,?,?,?,?)
             ON CONFLICT(session_id) DO UPDATE SET
               question_bank_version=excluded.question_bank_version,
               scenario=excluded.scenario,
               profile_json=excluded.profile_json,
               answers_json=excluded.answers_json,
               status_json=excluded.status_json,
               completion_status=excluded.completion_status,
               updated_at_utc=excluded.updated_at_utc
             WHERE questionnaire_responses.is_fictional_demo=1''',
             (session_id,BANK['version'],scenario,json.dumps(profile),json.dumps(answers),
              json.dumps(status),'short_interview_demo',datetime.now(timezone.utc).isoformat()))
        found=conn.execute('SELECT is_fictional_demo FROM questionnaire_responses WHERE session_id=?',(session_id,)).fetchone()
        if found != (1,):
            raise ValueError('Cannot overwrite a non-demo questionnaire')
    return {'session_id':session_id,'answers_saved':len(answers),'status':status,'database':str(db)}


def app():
    import streamlit as st
    st.set_page_config(page_title='AyurAI | Short Guided Intake',page_icon='🩺',layout='centered')
    st.title('AyurAI · Guided Clinical Intake')
    st.warning('FICTIONAL DEMO ONLY — do not enter real patient details. Supervisor/ERC approval pending.')
    st.caption('Age → Sex → Consent → 10 common symptom/safety questions → up to 10 relevant follow-ups → Medications → Allergies → Finish')

    defaults={'si_stage':'age','si_idx':0,'si_answers':{},'si_followups':[],
              'si_age_years':25,'si_age_extra_months':0,'si_sex':'not_recorded',
              'si_pregnancy':'not_applicable','si_ppg':False,'si_images':False,
              'si_guardian':False,'si_meds':'','si_herbals':'','si_allergies':'',
              'si_no_meds':False,'si_no_allergies':False,'si_session':'demo_c44cd0a6'}
    for k,v in defaults.items():
        if k not in st.session_state:
            st.session_state[k]=v
    ss=st.session_state
    with st.sidebar:
        st.subheader('Fictional session')
        st.text_input('Existing webcam session ID',key='si_session')
        st.write('Status: ',ss.si_stage.replace('_',' ').title())
        if st.button('Start a new fictional intake'):
            for k,v in defaults.items():
                ss[k]=v.copy() if isinstance(v,(dict,list)) else v
            st.rerun()
    stage=ss.si_stage
    age_months=int(ss.si_age_years)*12+int(ss.si_age_extra_months)
    profile=profile_for(age_months,ss.si_sex,ss.si_pregnancy)
    answers=ss.si_answers

    def advance(next_stage):
        ss.si_stage=next_stage
        ss.si_idx=0
        st.rerun()

    def previous(prev_stage):
        ss.si_stage=prev_stage
        st.rerun()

    if stage=='age':
        st.subheader('1 · How old is the patient?')
        with st.form('age_form'):
            years=st.number_input('Age in completed years (fictional)',min_value=0,max_value=120,value=int(ss.si_age_years),step=1)
            months=st.number_input('Extra completed months (0–11)',min_value=0,max_value=11,value=int(ss.si_age_extra_months),step=1)
            go=st.form_submit_button('Next: Sex →',type='primary')
        if go:
            ss.si_age_years=int(years)
            ss.si_age_extra_months=int(months)
            advance('sex')
        return

    if stage=='sex':
        st.subheader('2 · Sex and relevant clinical context')
        with st.form('sex_form'):
            opts=['not_recorded','female','male','intersex','prefer_not_to_answer']
            sex=st.selectbox('Sex (patient-reported, for fictional demonstration)',opts,index=opts.index(ss.si_sex))
            p_opts=['not_applicable','pregnant','not_pregnant','unknown','prefer_not_to_answer']
            preg=st.selectbox('Pregnancy status, if applicable',p_opts,index=p_opts.index(ss.si_pregnancy),
                              help='Separate from sex. Used only to activate appropriate follow-up questions.')
            back=st.form_submit_button('← Back')
            go=st.form_submit_button('Next: Consent →',type='primary')
        if back: previous('age')
        if go:
            ss.si_sex=sex
            ss.si_pregnancy=preg
            advance('consent')
        return

    if stage=='consent':
        st.subheader('3 · Are you comfortable taking part in this questionnaire and screening tests?')
        st.caption('For a real study, this would require approved information and a formal consent process.')
        with st.form('consent_form'):
            consent=st.radio('Consent for the fictional questionnaire and screening demonstration?',
                             ['Select an answer','Yes','No'],index=0)
            ppg=st.checkbox('Separately allow finger PPG recording',value=ss.si_ppg)
            images=st.checkbox('Separately allow webcam photographs',value=ss.si_images)
            guardian=st.checkbox('Guardian permission confirmed (fictional)',value=ss.si_guardian) if age_months<216 else True
            back=st.form_submit_button('← Back')
            go=st.form_submit_button('Continue →',type='primary')
        if back: previous('sex')
        if go:
            if consent=='Select an answer':
                st.error('Please select Yes or No.')
            elif consent=='No':
                st.info('Consent declined. Interview stopped; nothing saved.')
            elif not guardian:
                st.error('For a child, guardian permission must be confirmed to proceed.')
            else:
                ss.si_ppg=ppg
                ss.si_images=images
                ss.si_guardian=guardian
                answers['REG05']='yes'
                answers['REG06']='yes' if ppg else 'no'
                answers['REG07']='yes' if images else 'no'
                answers['REG02']=age_months
                if age_months<216:
                    answers['CH02']='yes'
                advance('common')
        return

    if stage in ('common','followups'):
        if stage=='common':
            ids=list(COMMON_IDS)
            if profile['pregnancy_status']=='pregnant':
                ids.insert(4,'PR06')  # pregnancy-specific urgent safety question
            heading='4 · Common symptoms and essential safety'
        else:
            ids=list(ss.si_followups)
            heading='5 · Relevant follow-up questions'
        if not ids:
            advance('medications')
        idx=min(ss.si_idx,len(ids)-1)
        qid=ids[idx]
        q=QUESTION_BY_ID[qid]
        st.subheader(heading)
        st.progress((idx+1)/len(ids),text=f'Question {idx+1} of {len(ids)} in this section')
        st.markdown(f'**{q["prompt"]}**')
        with st.form(f'question_{stage}_{qid}'):
            if q['type']=='choice':
                options=['— Choose an answer —']+q['options']
                old=answers.get(qid)
                v=st.selectbox('Answer',options,index=options.index(old) if old in options else 0)
            elif q['type']=='integer':
                old=answers.get(qid)
                v=st.text_input('Number',value='' if old is None else str(old))
            else:
                v=st.text_area('Fictional answer',value=str(answers.get(qid,'')))
            back=st.form_submit_button('← Back')
            go=st.form_submit_button('Next →',type='primary')
        if back:
            if idx>0:
                ss.si_idx=idx-1
                st.rerun()
            else:
                if stage=='common': previous('consent')
                else:
                    ss.si_stage='common'
                    ss.si_idx=len(COMMON_IDS) + (1 if profile['pregnancy_status']=='pregnant' else 0)-1
                    st.rerun()
        if go:
            if q['type']=='choice' and v=='— Choose an answer —':
                st.error('Please answer this question, or choose Not sure / Prefer not to answer.')
                return
            if q['type']=='choice':
                answers[qid]=v
            elif q['type']=='integer':
                try: answers[qid]=int(v)
                except ValueError:
                    st.error('Please enter a whole number.')
                    return
            elif v.strip():
                answers[qid]=v.strip()
            else:
                answers.pop(qid,None)
            if qid in ('SAF01','SAF02','SAF03','SAF04','PR06') and v!='no':
                st.error('Safety concern or unclear response: stop routine screening and request clinician review.')
                ss.si_stage='stopped'
                st.rerun()
            if idx+1<len(ids):
                ss.si_idx=idx+1
                st.rerun()
            if stage=='common':
                ss.si_followups=select_followups(profile,answers)
                advance('followups' if ss.si_followups else 'medications')
            else:
                advance('medications')
        return

    if stage=='stopped':
        st.error('Screening stopped: urgent or unresolved safety response. Seek clinician review; no AI risk prediction.')
        st.caption('No fictional questionnaire has been saved.')
        return

    if stage=='medications':
        st.subheader('6 · What medicines or supplements are you taking currently?')
        st.caption('Include prescribed, over-the-counter, vitamins, Ayurvedic and herbal products. Fictional examples only.')
        with st.form('med_form'):
            no_meds=st.checkbox('No current medicines, supplements or herbal products',value=ss.si_no_meds)
            meds=st.text_area('Conventional medicines and supplements (one per line: name | dose, frequency)',value=ss.si_meds)
            herbs=st.text_area('Ayurvedic / herbal products (one per line: name | details)',value=ss.si_herbals)
            back=st.form_submit_button('← Back')
            go=st.form_submit_button('Next: Allergies →',type='primary')
        if back:
            if ss.si_followups:
                ss.si_stage='followups'; ss.si_idx=len(ss.si_followups)-1; st.rerun()
            ss.si_stage='common'; ss.si_idx=len(COMMON_IDS)+(1 if profile['pregnancy_status']=='pregnant' else 0)-1; st.rerun()
        if go:
            if no_meds and (meds.strip() or herbs.strip()):
                st.error('Either select no medications or list them, not both.')
            elif not no_meds and not meds.strip() and not herbs.strip():
                st.error('Please answer, or select no current medicines.')
            else:
                ss.si_no_meds=no_meds; ss.si_meds=meds; ss.si_herbals=herbs
                advance('allergies')
        return

    if stage=='allergies':
        st.subheader('7 · Do you have any known allergies or previous adverse reactions?')
        with st.form('allergy_form'):
            no_all=st.checkbox('No known allergies or adverse reactions',value=ss.si_no_allergies)
            all_text=st.text_area('List substance | reaction (one fictional example per line)',value=ss.si_allergies)
            back=st.form_submit_button('← Back')
            go=st.form_submit_button('Review and finish →',type='primary')
        if back: previous('medications')
        if go:
            if no_all and all_text.strip():
                st.error('Choose no known allergies or list reactions, not both.')
            elif not no_all and not all_text.strip():
                st.error('Please answer, or select no known allergies.')
            else:
                ss.si_no_allergies=no_all; ss.si_allergies=all_text
                advance('review')
        return

    if stage=='review':
        st.subheader('8 · Intake complete')
        st.success('Short questionnaire complete. No further questions.')
        try:
            final=finalize_answers(age_months,ss.si_ppg,ss.si_images,True,answers,
                                   ss.si_meds,ss.si_herbals,ss.si_allergies,
                                   ss.si_no_meds,ss.si_no_allergies)
        except ValueError as exc:
            st.error(str(exc)); return
        state=safety_state(profile,final)
        st.write(f'Common questions: {len(COMMON_IDS)} (+1 pregnancy safety question if applicable)')
        st.write(f'Adaptive follow-ups: {len(ss.si_followups)} / {MAX_FOLLOWUPS}')
        st.write('Medications and allergies: last two questions completed')
        st.info('Finger-contact discomfort must be checked during sensor placement. PPG acquisition is not yet cleared.')
        with st.expander('Technical safety/consent summary'):
            st.json(state)
        if st.button('Save fictional intake to existing session',type='primary'):
            try:
                result=save_demo(ss.si_session,profile,final)
            except (ValueError,FileNotFoundError,sqlite3.Error) as exc:
                st.error(str(exc))
            else:
                st.success(f'Saved {result["answers_saved"]} responses to local SQLite: {result["session_id"]}')
        st.caption('Screening only; no clinical diagnosis or patient-specific risk category produced here.')


if __name__=='__main__':
    app()

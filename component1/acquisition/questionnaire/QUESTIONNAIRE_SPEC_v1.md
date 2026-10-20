# AyurAI Clinical Questionnaire v1 — PROTOTYPE DRAFT

Status: **Clinical supervisor / ethics approval pending**. Age eligibility is deliberately **not set**. No real-patient enrolment through this prototype.

## Purpose and sources

- **Clinical intake (draft, not taken from the PDF):** registration, safety, anaemia symptoms, bleeding, laboratory history, diet, medication and allergy reconciliation, acquisition comfort.
- **Asthavidha (from the user-supplied four-page questionnaire):** N1–N4, J1–J6, D1–D5, S1–S6, V1–V4, M1–M5, U1–U4, A1–A6 and DS1–DS8 (48 questions). These questions are **optional clinician-guided traditional observations** and do not automatically count as validated anaemia evidence.
- Question wording, eligibility, translations, clinical red flags and scoring need prospective clinical review before actual research collection.

## Patient groups / conditional branching

| Branch | Activation | Action |
|---|---|---|
| Registration and immediate safety | Everyone | Ask consent/permission and urgent symptoms early |
| Core anaemia history | Prototype permission REG05=yes, no urgent flags | Ask common questions C01–C20 |
| Symptom detail | Any C01–C07=yes | Show SY01–SY06 |
| Bleeding | C10=yes | Show BL01–BL04 |
| Relevant menstruation | C20=yes (clinician-assessed applicability) | Show MEN01–MEN04 privately |
| Past anaemia/Hb | C08=yes or C09=yes | Show LAB01–LAB04 |
| General history | Any C11–C14 or C18=yes | Show HX01–HX03 |
| Medicine/OTC/supplement | C15=yes | Repeatable MED01 items |
| Ayurvedic/herbal products | C16=yes | Repeatable MED02 items |
| Allergies/reactions | C17=yes | Repeatable ALG01 items |
| Child/caregiver | profile.age_months < 216 | CH01–CH07; CH08 if under 24 months; CH09 if 24–215 months; require guardian permission for capture |
| Pregnancy | profile.pregnancy_status == pregnant | PR01–PR06; **independent of** age branch (clinician handles any special situation) |
| PPG | profile.collect_ppg=true, REG06=yes | P01–P07; stop measurement on pain, injury or tingling |
| Camera | profile.collect_images=true, REG07=yes | IMG01–IMG05; allow skip/withdrawal |
| Asthavidha | profile.include_asthavidha=true | Traditional assessment bank (not a clinical diagnosis) |
| Clinician review | profile.include_review=true | REV01–REV02 |

## Safety/consent state machine

- **REG05 not yes:** no regular intake or capture, only registration and safety.
- **SAF01–SAF04 yes:** halt normal questioning/acquisition and refer to clinical assistant/clinician. **PR06 yes:** flag clinician review for pregnancy bleeding.
- **REG06=no/unknown:** no PPG recording. **REG07=no/unknown:** no image capture.
- **P02, P05 or P06=yes:** stop/avoid finger-sensor measurement pending assessment, do not press harder.
- **IMG05=yes:** do not capture further images.
- **Child:** require documented guardian permission (CH02=yes), and record age-appropriate assent assessment (CH03). First study's child minimum age remains unset.
- **Missing data != No.** Do not infer answers from webcam/PPG. The engine currently provides *no* final anaemia-risk classification.

## Patient and privacy data model (next implementation)

- `patients`: pseudonymous study-specific ID; identity map held separately, if approved.
- `screening_sessions`: unique session ID, patient ID, version, timestamps, operator, consent and protocol status.
- `questionnaire_answers`: session ID, question-bank version, question ID, answer value, who provided it (patient/caregiver/assistant), time, review status.
- `medication_items`: session ID, category, product, strength, dose, route, frequency, timing, verified status. Share structured data with Component 3 only under appropriate authorization.
- `allergy_items`: session ID, substance, reaction, severity, confirmation status.
- `clinical_flags`: session ID, trigger ID, escalation/review state; no autonomous diagnosis.
- Raw images, PPG streams and clinical responses stay in local protected storage outside Git. Clinical deployments need authorization, RBAC, audit logs, backup/restore and appropriate encryption.

## CLI acceptance tests

1. `python questionnaire_engine.py --demo all` prints **4 fictional** scenarios (adult / child / pregnancy / urgent).
2. The engine verifies 7 groups of branching/consent/safety assertions.
3. Child branch appears only when age < 216 months; infant feeding vs older child questions differ.
4. Pregnancy branch appears when pregnancy_status is `pregnant`.
5. Safety response blocks acquisition, and sensor pain disables PPG capture.
6. Script reads JSON and never opens or modifies the existing SQLite databases.

## Scope and next steps

The current engine **selects questions and flags acquisition permission** only. It does not persist real answers, calculate clinical risk or provide conversational AI. Implement a clinical-assistant review UI and SQLite questionnaire persistence next; integrate with the existing `demo_...` session ID later, using **fictional demonstration responses** until approvals are in place.

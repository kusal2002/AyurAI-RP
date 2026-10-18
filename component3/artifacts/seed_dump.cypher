CREATE CONSTRAINT herb_id_unique IF NOT EXISTS FOR (h:Herb) REQUIRE h.id IS UNIQUE;

CREATE CONSTRAINT drug_id_unique IF NOT EXISTS FOR (d:Drug) REQUIRE d.id IS UNIQUE;

CREATE CONSTRAINT compound_name_unique IF NOT EXISTS FOR (c:Compound) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT enzyme_name_unique IF NOT EXISTS FOR (e:Enzyme) REQUIRE e.name IS UNIQUE;

CREATE CONSTRAINT target_name_unique IF NOT EXISTS FOR (t:Target) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT condition_name_unique IF NOT EXISTS FOR (cond:Condition) REQUIRE cond.name IS UNIQUE;

MERGE (h:Herb {id: 'HERB-001'}) SET h.common_name = 'Punarnava', h.sanskrit_name = 'Punarnava', h.botanical_name = 'Boerhavia diffusa', h.traditional_uses = ['Pandu Roga', 'Shotha (Edema)', 'Diuretic', 'Yakritodara'];

MERGE (c:Compound {name: 'Punarnavine'});
MATCH (h:Herb {id: 'HERB-001'}), (c:Compound {name: 'Punarnavine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Boeravinones'});
MATCH (h:Herb {id: 'HERB-001'}), (c:Compound {name: 'Boeravinones'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Rotenoids'});
MATCH (h:Herb {id: 'HERB-001'}), (c:Compound {name: 'Rotenoids'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Liriodendrin'});
MATCH (h:Herb {id: 'HERB-001'}), (c:Compound {name: 'Liriodendrin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Severe Renal Failure (eGFR < 15 unmonitored)'});
MATCH (h:Herb {id: 'HERB-001'}), (cond:Condition {name: 'Severe Renal Failure (eGFR < 15 unmonitored)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'First trimester pregnancy without guidance'});
MATCH (h:Herb {id: 'HERB-001'}), (cond:Condition {name: 'First trimester pregnancy without guidance'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-002'}) SET h.common_name = 'Amalaki', h.sanskrit_name = 'Amalaki', h.botanical_name = 'Phyllanthus emblica', h.traditional_uses = ['Pandu Roga', 'Rasayana', 'Enhances Iron Absorption', 'Pitta Shamaka'];

MERGE (c:Compound {name: 'Ascorbic Acid'});
MATCH (h:Herb {id: 'HERB-002'}), (c:Compound {name: 'Ascorbic Acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Ellagic Acid'});
MATCH (h:Herb {id: 'HERB-002'}), (c:Compound {name: 'Ellagic Acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Gallic Acid'});
MATCH (h:Herb {id: 'HERB-002'}), (c:Compound {name: 'Gallic Acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Emblicanin A & B'});
MATCH (h:Herb {id: 'HERB-002'}), (c:Compound {name: 'Emblicanin A & B'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Active hyperacidity flares with bleeding peptic ulcer'});
MATCH (h:Herb {id: 'HERB-002'}), (cond:Condition {name: 'Active hyperacidity flares with bleeding peptic ulcer'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-003'}) SET h.common_name = 'Mandura Bhasma', h.sanskrit_name = 'Mandura Bhasma', h.botanical_name = 'Ferric Oxide Calx (Fe2O3)', h.traditional_uses = ['Pandu Roga', 'Yakritodara (Hepatomegaly)', 'Plihodara (Splenomegaly)'];

MERGE (c:Compound {name: 'Ferric Oxide'});
MATCH (h:Herb {id: 'HERB-003'}), (c:Compound {name: 'Ferric Oxide'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Ferrous Iron'});
MATCH (h:Herb {id: 'HERB-003'}), (c:Compound {name: 'Ferrous Iron'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Trace Minerals'});
MATCH (h:Herb {id: 'HERB-003'}), (c:Compound {name: 'Trace Minerals'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Hemochromatosis'});
MATCH (h:Herb {id: 'HERB-003'}), (cond:Condition {name: 'Hemochromatosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Thalassemia major'});
MATCH (h:Herb {id: 'HERB-003'}), (cond:Condition {name: 'Thalassemia major'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Active Peptic Ulcer'});
MATCH (h:Herb {id: 'HERB-003'}), (cond:Condition {name: 'Active Peptic Ulcer'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Severe CKD Stage 4-5'});
MATCH (h:Herb {id: 'HERB-003'}), (cond:Condition {name: 'Severe CKD Stage 4-5'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-004'}) SET h.common_name = 'Ashwagandha', h.sanskrit_name = 'Ashwagandha', h.botanical_name = 'Withania somnifera', h.traditional_uses = ['Balya', 'Daurbalya (Debility)', 'Pandu adjuvant', 'Rasayana'];

MERGE (c:Compound {name: 'Withaferin A'});
MATCH (h:Herb {id: 'HERB-004'}), (c:Compound {name: 'Withaferin A'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Withanolide D'});
MATCH (h:Herb {id: 'HERB-004'}), (c:Compound {name: 'Withanolide D'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Sitoindosides'});
MATCH (h:Herb {id: 'HERB-004'}), (c:Compound {name: 'Sitoindosides'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Somniferine'});
MATCH (h:Herb {id: 'HERB-004'}), (c:Compound {name: 'Somniferine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Pregnancy (uterine stimulant risk in high doses)'});
MATCH (h:Herb {id: 'HERB-004'}), (cond:Condition {name: 'Pregnancy (uterine stimulant risk in high doses)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Hyperthyroidism'});
MATCH (h:Herb {id: 'HERB-004'}), (cond:Condition {name: 'Hyperthyroidism'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Active autoimmune flare'});
MATCH (h:Herb {id: 'HERB-004'}), (cond:Condition {name: 'Active autoimmune flare'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-005'}) SET h.common_name = 'Yashtimadhu', h.sanskrit_name = 'Yashtimadhu', h.botanical_name = 'Glycyrrhiza glabra', h.traditional_uses = ['Pitta shamaka', 'Raktapitta', 'Rasayana', 'Gastric mucosal protective'];

MERGE (c:Compound {name: 'Glycyrrhizin'});
MATCH (h:Herb {id: 'HERB-005'}), (c:Compound {name: 'Glycyrrhizin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Glabridin'});
MATCH (h:Herb {id: 'HERB-005'}), (c:Compound {name: 'Glabridin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Liquiritigenin'});
MATCH (h:Herb {id: 'HERB-005'}), (c:Compound {name: 'Liquiritigenin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Isoliquiritigenin'});
MATCH (h:Herb {id: 'HERB-005'}), (c:Compound {name: 'Isoliquiritigenin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Uncontrolled Hypertension'});
MATCH (h:Herb {id: 'HERB-005'}), (cond:Condition {name: 'Uncontrolled Hypertension'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Hypokalemia'});
MATCH (h:Herb {id: 'HERB-005'}), (cond:Condition {name: 'Hypokalemia'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Severe CKD Stage 4-5'});
MATCH (h:Herb {id: 'HERB-005'}), (cond:Condition {name: 'Severe CKD Stage 4-5'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Cirrhosis'});
MATCH (h:Herb {id: 'HERB-005'}), (cond:Condition {name: 'Cirrhosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-006'}) SET h.common_name = 'Guduchi', h.sanskrit_name = 'Guduchi', h.botanical_name = 'Tinospora cordifolia', h.traditional_uses = ['Pandu', 'Jwara', 'Deepana', 'Rasayana', 'Rakta Prasadana'];

MERGE (c:Compound {name: 'Tinosporaside'});
MATCH (h:Herb {id: 'HERB-006'}), (c:Compound {name: 'Tinosporaside'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Cordifolioside'});
MATCH (h:Herb {id: 'HERB-006'}), (c:Compound {name: 'Cordifolioside'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Berberine'});
MATCH (h:Herb {id: 'HERB-006'}), (c:Compound {name: 'Berberine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Tinosporine'});
MATCH (h:Herb {id: 'HERB-006'}), (c:Compound {name: 'Tinosporine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Severe autoimmune hepatitis without monitoring'});
MATCH (h:Herb {id: 'HERB-006'}), (cond:Condition {name: 'Severe autoimmune hepatitis without monitoring'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Hypoglycemia (additive risk)'});
MATCH (h:Herb {id: 'HERB-006'}), (cond:Condition {name: 'Hypoglycemia (additive risk)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-007'}) SET h.common_name = 'Haritaki', h.sanskrit_name = 'Haritaki', h.botanical_name = 'Terminalia chebula', h.traditional_uses = ['Anulomana', 'Pandu', 'Shotha', 'Deepana'];

MERGE (c:Compound {name: 'Chebulic acid'});
MATCH (h:Herb {id: 'HERB-007'}), (c:Compound {name: 'Chebulic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Chebulinic acid'});
MATCH (h:Herb {id: 'HERB-007'}), (c:Compound {name: 'Chebulinic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Corilagin'});
MATCH (h:Herb {id: 'HERB-007'}), (c:Compound {name: 'Corilagin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Tannins'});
MATCH (h:Herb {id: 'HERB-007'}), (c:Compound {name: 'Tannins'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Severe acute dehydration'});
MATCH (h:Herb {id: 'HERB-007'}), (cond:Condition {name: 'Severe acute dehydration'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Pregnancy (purgative anthraquinone effect)'});
MATCH (h:Herb {id: 'HERB-007'}), (cond:Condition {name: 'Pregnancy (purgative anthraquinone effect)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-008'}) SET h.common_name = 'Shatavari', h.sanskrit_name = 'Shatavari', h.botanical_name = 'Asparagus racemosus', h.traditional_uses = ['Rasayana', 'Stanya', 'Pitta-Vata Pandu', 'Nutritive tonic'];

MERGE (c:Compound {name: 'Shatavarin I-IV'});
MATCH (h:Herb {id: 'HERB-008'}), (c:Compound {name: 'Shatavarin I-IV'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Sarsasapogenin'});
MATCH (h:Herb {id: 'HERB-008'}), (c:Compound {name: 'Sarsasapogenin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Isoflavones'});
MATCH (h:Herb {id: 'HERB-008'}), (c:Compound {name: 'Isoflavones'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Estrogen-sensitive malignancies'});
MATCH (h:Herb {id: 'HERB-008'}), (cond:Condition {name: 'Estrogen-sensitive malignancies'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Severe congestive heart failure fluid overload'});
MATCH (h:Herb {id: 'HERB-008'}), (cond:Condition {name: 'Severe congestive heart failure fluid overload'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-009'}) SET h.common_name = 'Dhatri Lauha', h.sanskrit_name = 'Dhatri Lauha', h.botanical_name = 'Classical Compound (Amalaki + Lauha Bhasma + Yashtimadhu)', h.traditional_uses = ['Pandu Roga Gold Standard', 'Kshaya', 'Pitta Pandu'];

MERGE (c:Compound {name: 'Elemental Iron'});
MATCH (h:Herb {id: 'HERB-009'}), (c:Compound {name: 'Elemental Iron'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Ascorbic Acid'});
MATCH (h:Herb {id: 'HERB-009'}), (c:Compound {name: 'Ascorbic Acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Glycyrrhizin'});
MATCH (h:Herb {id: 'HERB-009'}), (c:Compound {name: 'Glycyrrhizin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Tannins'});
MATCH (h:Herb {id: 'HERB-009'}), (c:Compound {name: 'Tannins'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Hemochromatosis'});
MATCH (h:Herb {id: 'HERB-009'}), (cond:Condition {name: 'Hemochromatosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Active GI bleeding'});
MATCH (h:Herb {id: 'HERB-009'}), (cond:Condition {name: 'Active GI bleeding'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Concurrent oral tetracyclines without 4h gap'});
MATCH (h:Herb {id: 'HERB-009'}), (cond:Condition {name: 'Concurrent oral tetracyclines without 4h gap'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-010'}) SET h.common_name = 'Punarnava Mandura', h.sanskrit_name = 'Punarnavadi Mandura', h.botanical_name = 'Classical Herbo-Mineral Compound', h.traditional_uses = ['Pandu Roga', 'Kaphaja Pandu', 'Shotha', 'Grahani'];

MERGE (c:Compound {name: 'Punarnavine'});
MATCH (h:Herb {id: 'HERB-010'}), (c:Compound {name: 'Punarnavine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Ferric Oxide Calx'});
MATCH (h:Herb {id: 'HERB-010'}), (c:Compound {name: 'Ferric Oxide Calx'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Triphala Tannins'});
MATCH (h:Herb {id: 'HERB-010'}), (c:Compound {name: 'Triphala Tannins'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Gingerols'});
MATCH (h:Herb {id: 'HERB-010'}), (c:Compound {name: 'Gingerols'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'End-stage renal failure (eGFR < 15)'});
MATCH (h:Herb {id: 'HERB-010'}), (cond:Condition {name: 'End-stage renal failure (eGFR < 15)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Hemochromatosis'});
MATCH (h:Herb {id: 'HERB-010'}), (cond:Condition {name: 'Hemochromatosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Severe peptic ulceration'});
MATCH (h:Herb {id: 'HERB-010'}), (cond:Condition {name: 'Severe peptic ulceration'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-011'}) SET h.common_name = 'Navayasa Lauha', h.sanskrit_name = 'Navayasa Churna / Lauha', h.botanical_name = 'Classical Compound (Trikatu + Triphala + Musta + Vidanga + Chitraka + Lauha Bhasma)', h.traditional_uses = ['Pandu Roga First-line', 'Kamala (Jaundice)', 'Hridroga adjuvant'];

MERGE (c:Compound {name: 'Piperine'});
MATCH (h:Herb {id: 'HERB-011'}), (c:Compound {name: 'Piperine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Chebulic acid'});
MATCH (h:Herb {id: 'HERB-011'}), (c:Compound {name: 'Chebulic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Embelin'});
MATCH (h:Herb {id: 'HERB-011'}), (c:Compound {name: 'Embelin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Plumbagin'});
MATCH (h:Herb {id: 'HERB-011'}), (c:Compound {name: 'Plumbagin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Elemental Iron'});
MATCH (h:Herb {id: 'HERB-011'}), (c:Compound {name: 'Elemental Iron'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Severe gastritis flare'});
MATCH (h:Herb {id: 'HERB-011'}), (cond:Condition {name: 'Severe gastritis flare'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Active ulcerative colitis'});
MATCH (h:Herb {id: 'HERB-011'}), (cond:Condition {name: 'Active ulcerative colitis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Pregnancy first trimester'});
MATCH (h:Herb {id: 'HERB-011'}), (cond:Condition {name: 'Pregnancy first trimester'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-012'}) SET h.common_name = 'Arogyavardhini Vati', h.sanskrit_name = 'Arogyavardhini Vati', h.botanical_name = 'Classical Herbo-Mineral Mineral Compound', h.traditional_uses = ['Pandu with Hepatic Involvement', 'Kamala', 'Yakrit Vikara', 'Deepana-Pachana'];

MERGE (c:Compound {name: 'Picroside I & II'});
MATCH (h:Herb {id: 'HERB-012'}), (c:Compound {name: 'Picroside I & II'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Guggulsterones'});
MATCH (h:Herb {id: 'HERB-012'}), (c:Compound {name: 'Guggulsterones'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Azadirachtin'});
MATCH (h:Herb {id: 'HERB-012'}), (c:Compound {name: 'Azadirachtin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Purified Mercury & Sulphur Calx'});
MATCH (h:Herb {id: 'HERB-012'}), (c:Compound {name: 'Purified Mercury & Sulphur Calx'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Lauha Bhasma'});
MATCH (h:Herb {id: 'HERB-012'}), (c:Compound {name: 'Lauha Bhasma'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Pregnancy and lactation'});
MATCH (h:Herb {id: 'HERB-012'}), (cond:Condition {name: 'Pregnancy and lactation'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Severe renal impairment (eGFR < 30)'});
MATCH (h:Herb {id: 'HERB-012'}), (cond:Condition {name: 'Severe renal impairment (eGFR < 30)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Pediatric use < 12 years'});
MATCH (h:Herb {id: 'HERB-012'}), (cond:Condition {name: 'Pediatric use < 12 years'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-013'}) SET h.common_name = 'Chandraprabha Vati', h.sanskrit_name = 'Chandraprabha Vati', h.botanical_name = 'Classical Herbo-Mineral Polyherbal', h.traditional_uses = ['Pandu with urinary debility', 'Prameha', 'Daurbalya', 'Rasayana'];

MERGE (c:Compound {name: 'Fulvic acid'});
MATCH (h:Herb {id: 'HERB-013'}), (c:Compound {name: 'Fulvic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Guggulsterones'});
MATCH (h:Herb {id: 'HERB-013'}), (c:Compound {name: 'Guggulsterones'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Berberine'});
MATCH (h:Herb {id: 'HERB-013'}), (c:Compound {name: 'Berberine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Piperine'});
MATCH (h:Herb {id: 'HERB-013'}), (c:Compound {name: 'Piperine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Iron Calx'});
MATCH (h:Herb {id: 'HERB-013'}), (c:Compound {name: 'Iron Calx'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Bleeding diathesis'});
MATCH (h:Herb {id: 'HERB-013'}), (cond:Condition {name: 'Bleeding diathesis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Severe hyperacidity flare'});
MATCH (h:Herb {id: 'HERB-013'}), (cond:Condition {name: 'Severe hyperacidity flare'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-014'}) SET h.common_name = 'Lohasava', h.sanskrit_name = 'Lohasava', h.botanical_name = 'Fermented Iron Calx Arishta', h.traditional_uses = ['Pandu Roga', 'Shotha', 'Jataragni Mandya', 'Gulma'];

MERGE (c:Compound {name: 'Bioavailable Ferrous Citrate'});
MATCH (h:Herb {id: 'HERB-014'}), (c:Compound {name: 'Bioavailable Ferrous Citrate'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Piperine'});
MATCH (h:Herb {id: 'HERB-014'}), (c:Compound {name: 'Piperine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Triphala Tannins'});
MATCH (h:Herb {id: 'HERB-014'}), (c:Compound {name: 'Triphala Tannins'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Self-generated Alcohol (5-10%)'});
MATCH (h:Herb {id: 'HERB-014'}), (c:Compound {name: 'Self-generated Alcohol (5-10%)'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Gastric ulcer perforation risk'});
MATCH (h:Herb {id: 'HERB-014'}), (cond:Condition {name: 'Gastric ulcer perforation risk'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Alcohol dependence'});
MATCH (h:Herb {id: 'HERB-014'}), (cond:Condition {name: 'Alcohol dependence'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Active hyperacidity'});
MATCH (h:Herb {id: 'HERB-014'}), (cond:Condition {name: 'Active hyperacidity'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-015'}) SET h.common_name = 'Drakshasava', h.sanskrit_name = 'Drakshasava', h.botanical_name = 'Fermented Raisin Formulation', h.traditional_uses = ['Pandu debility', 'Daurbalya', 'Kshaya', 'Raktapitta'];

MERGE (c:Compound {name: 'Resveratrol'});
MATCH (h:Herb {id: 'HERB-015'}), (c:Compound {name: 'Resveratrol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Tartaric acid'});
MATCH (h:Herb {id: 'HERB-015'}), (c:Compound {name: 'Tartaric acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Polyphenols'});
MATCH (h:Herb {id: 'HERB-015'}), (c:Compound {name: 'Polyphenols'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Piperine'});
MATCH (h:Herb {id: 'HERB-015'}), (c:Compound {name: 'Piperine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Uncontrolled Diabetes Mellitus (high glycemic load)'});
MATCH (h:Herb {id: 'HERB-015'}), (cond:Condition {name: 'Uncontrolled Diabetes Mellitus (high glycemic load)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Alcohol aversion'});
MATCH (h:Herb {id: 'HERB-015'}), (cond:Condition {name: 'Alcohol aversion'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-016'}) SET h.common_name = 'Kasisa Bhasma', h.sanskrit_name = 'Kasisa Bhasma', h.botanical_name = 'Incinerated Green Vitriol (FeSO4 . 7H2O)', h.traditional_uses = ['Pandu Roga', 'Kasa', 'Shwasa', 'Artavajanana'];

MERGE (c:Compound {name: 'Ferrous Sulphate'});
MATCH (h:Herb {id: 'HERB-016'}), (c:Compound {name: 'Ferrous Sulphate'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Iron Oxide'});
MATCH (h:Herb {id: 'HERB-016'}), (c:Compound {name: 'Iron Oxide'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Trace Sulphur'});
MATCH (h:Herb {id: 'HERB-016'}), (c:Compound {name: 'Trace Sulphur'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Iron storage diseases'});
MATCH (h:Herb {id: 'HERB-016'}), (cond:Condition {name: 'Iron storage diseases'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Severe non-iron deficiency hemolytic anemia'});
MATCH (h:Herb {id: 'HERB-016'}), (cond:Condition {name: 'Severe non-iron deficiency hemolytic anemia'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-017'}) SET h.common_name = 'Swarna Makshika Bhasma', h.sanskrit_name = 'Swarna Makshika Bhasma', h.botanical_name = 'Incinerated Chalcopyrite (CuFeS2)', h.traditional_uses = ['Pandu Roga', 'Anidra', 'Hridroga', 'Rasayana'];

MERGE (c:Compound {name: 'Copper-Iron Sulphide Calx'});
MATCH (h:Herb {id: 'HERB-017'}), (c:Compound {name: 'Copper-Iron Sulphide Calx'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Trace Gold'});
MATCH (h:Herb {id: 'HERB-017'}), (c:Compound {name: 'Trace Gold'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Micro-elements'});
MATCH (h:Herb {id: 'HERB-017'}), (c:Compound {name: 'Micro-elements'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Wilson\'s disease'});
MATCH (h:Herb {id: 'HERB-017'}), (cond:Condition {name: 'Wilson\'s disease'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Advanced hepatic cirrhosis'});
MATCH (h:Herb {id: 'HERB-017'}), (cond:Condition {name: 'Advanced hepatic cirrhosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Hemochromatosis'});
MATCH (h:Herb {id: 'HERB-017'}), (cond:Condition {name: 'Hemochromatosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-018'}) SET h.common_name = 'Loha Bhasma', h.sanskrit_name = 'Lauha Bhasma (100 Puti)', h.botanical_name = 'Incinerated Elemental Iron Calx', h.traditional_uses = ['Classical Pandu treatment', 'Rakta Dhatu Vardhana', 'Ayusya', 'Vaya Sthapana'];

MERGE (c:Compound {name: 'Microfine Elemental Fe (Fe2O3/Fe3O4)'});
MATCH (h:Herb {id: 'HERB-018'}), (c:Compound {name: 'Microfine Elemental Fe (Fe2O3/Fe3O4)'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Magnetic nano-particles'});
MATCH (h:Herb {id: 'HERB-018'}), (c:Compound {name: 'Magnetic nano-particles'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Hemolytic anemia without iron deficiency'});
MATCH (h:Herb {id: 'HERB-018'}), (cond:Condition {name: 'Hemolytic anemia without iron deficiency'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Hemochromatosis'});
MATCH (h:Herb {id: 'HERB-018'}), (cond:Condition {name: 'Hemochromatosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Severe ulcerative lesions'});
MATCH (h:Herb {id: 'HERB-018'}), (cond:Condition {name: 'Severe ulcerative lesions'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-019'}) SET h.common_name = 'Dadima', h.sanskrit_name = 'Dadima', h.botanical_name = 'Punica granatum', h.traditional_uses = ['Pandu Roga Diet', 'Raktapitta', 'Hridya', 'Rochana', 'Deepana'];

MERGE (c:Compound {name: 'Punicalagin'});
MATCH (h:Herb {id: 'HERB-019'}), (c:Compound {name: 'Punicalagin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Ellagic acid'});
MATCH (h:Herb {id: 'HERB-019'}), (c:Compound {name: 'Ellagic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Anthocyanins'});
MATCH (h:Herb {id: 'HERB-019'}), (c:Compound {name: 'Anthocyanins'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Punicic acid'});
MATCH (h:Herb {id: 'HERB-019'}), (c:Compound {name: 'Punicic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Hypotension when combined with high-dose ACE inhibitors (additive)'});
MATCH (h:Herb {id: 'HERB-019'}), (cond:Condition {name: 'Hypotension when combined with high-dose ACE inhibitors (additive)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-020'}) SET h.common_name = 'Draksha', h.sanskrit_name = 'Draksha', h.botanical_name = 'Vitis vinifera', h.traditional_uses = ['Pandu nutritional support', 'Daurbalya', 'Vata-Pitta Shamana', 'Virechana mridu'];

MERGE (c:Compound {name: 'Resveratrol'});
MATCH (h:Herb {id: 'HERB-020'}), (c:Compound {name: 'Resveratrol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Proanthocyanidins'});
MATCH (h:Herb {id: 'HERB-020'}), (c:Compound {name: 'Proanthocyanidins'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Flavonoids'});
MATCH (h:Herb {id: 'HERB-020'}), (c:Compound {name: 'Flavonoids'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Iron minerals'});
MATCH (h:Herb {id: 'HERB-020'}), (c:Compound {name: 'Iron minerals'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Diabetic gastroparesis in acute state'});
MATCH (h:Herb {id: 'HERB-020'}), (cond:Condition {name: 'Diabetic gastroparesis in acute state'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Unchecked hyperglycemia in high doses'});
MATCH (h:Herb {id: 'HERB-020'}), (cond:Condition {name: 'Unchecked hyperglycemia in high doses'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-021'}) SET h.common_name = 'Bibhitaki', h.sanskrit_name = 'Bibhitaki', h.botanical_name = 'Terminalia bellirica', h.traditional_uses = ['Triphala constituent in Pandu', 'Kaphaja Pandu', 'Rakta Shodhaka'];

MERGE (c:Compound {name: 'Bellericanin'});
MATCH (h:Herb {id: 'HERB-021'}), (c:Compound {name: 'Bellericanin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Gallic acid'});
MATCH (h:Herb {id: 'HERB-021'}), (c:Compound {name: 'Gallic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Ellagic acid'});
MATCH (h:Herb {id: 'HERB-021'}), (c:Compound {name: 'Ellagic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Beta-sitosterol'});
MATCH (h:Herb {id: 'HERB-021'}), (c:Compound {name: 'Beta-sitosterol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Severe dry cough with mucosal erosion'});
MATCH (h:Herb {id: 'HERB-021'}), (cond:Condition {name: 'Severe dry cough with mucosal erosion'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Marked emaciation'});
MATCH (h:Herb {id: 'HERB-021'}), (cond:Condition {name: 'Marked emaciation'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-022'}) SET h.common_name = 'Musta', h.sanskrit_name = 'Musta', h.botanical_name = 'Cyperus rotundus', h.traditional_uses = ['Amapachana in Pandu', 'Grahani', 'Yakritottejaka', 'Jwara'];

MERGE (c:Compound {name: 'Cyperene'});
MATCH (h:Herb {id: 'HERB-022'}), (c:Compound {name: 'Cyperene'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Cyperotundone'});
MATCH (h:Herb {id: 'HERB-022'}), (c:Compound {name: 'Cyperotundone'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Patchoulenone'});
MATCH (h:Herb {id: 'HERB-022'}), (c:Compound {name: 'Patchoulenone'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Rotundene'});
MATCH (h:Herb {id: 'HERB-022'}), (c:Compound {name: 'Rotundene'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Severe chronic constipation (Grahi action)'});
MATCH (h:Herb {id: 'HERB-022'}), (cond:Condition {name: 'Severe chronic constipation (Grahi action)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-023'}) SET h.common_name = 'Vidanga', h.sanskrit_name = 'Vidanga', h.botanical_name = 'Embelia ribes', h.traditional_uses = ['Krimija Pandu (Helminth-induced anemia)', 'Deepana', 'Anulomana'];

MERGE (c:Compound {name: 'Embelin'});
MATCH (h:Herb {id: 'HERB-023'}), (c:Compound {name: 'Embelin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Homoembelin'});
MATCH (h:Herb {id: 'HERB-023'}), (c:Compound {name: 'Homoembelin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Vilangin'});
MATCH (h:Herb {id: 'HERB-023'}), (c:Compound {name: 'Vilangin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Quercitol'});
MATCH (h:Herb {id: 'HERB-023'}), (c:Compound {name: 'Quercitol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Contraceptive desire / fertility therapy (antifertility activity documented)'});
MATCH (h:Herb {id: 'HERB-023'}), (cond:Condition {name: 'Contraceptive desire / fertility therapy (antifertility activity documented)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Pregnancy'});
MATCH (h:Herb {id: 'HERB-023'}), (cond:Condition {name: 'Pregnancy'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-024'}) SET h.common_name = 'Shunthi', h.sanskrit_name = 'Shunthi', h.botanical_name = 'Zingiber officinale', h.traditional_uses = ['Agnideepana', 'Bioavailability enhancer for iron bhasmas', 'Amadoshahara'];

MERGE (c:Compound {name: '6-Gingerol'});
MATCH (h:Herb {id: 'HERB-024'}), (c:Compound {name: '6-Gingerol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: '6-Shogaol'});
MATCH (h:Herb {id: 'HERB-024'}), (c:Compound {name: '6-Shogaol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Zingiberene'});
MATCH (h:Herb {id: 'HERB-024'}), (c:Compound {name: 'Zingiberene'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Paradol'});
MATCH (h:Herb {id: 'HERB-024'}), (c:Compound {name: 'Paradol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Active bleeding peptic ulcer'});
MATCH (h:Herb {id: 'HERB-024'}), (cond:Condition {name: 'Active bleeding peptic ulcer'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Concomitant high-dose anticoagulant therapy (monitor)'});
MATCH (h:Herb {id: 'HERB-024'}), (cond:Condition {name: 'Concomitant high-dose anticoagulant therapy (monitor)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-025'}) SET h.common_name = 'Pippali', h.sanskrit_name = 'Pippali', h.botanical_name = 'Piper longum', h.traditional_uses = ['Yogavahi (Bioenhancer for iron absorption)', 'Plihodara', 'Deepana'];

MERGE (c:Compound {name: 'Piperine'});
MATCH (h:Herb {id: 'HERB-025'}), (c:Compound {name: 'Piperine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Piperlongumine'});
MATCH (h:Herb {id: 'HERB-025'}), (c:Compound {name: 'Piperlongumine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Piperlonguminine'});
MATCH (h:Herb {id: 'HERB-025'}), (c:Compound {name: 'Piperlonguminine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Pipernonaline'});
MATCH (h:Herb {id: 'HERB-025'}), (c:Compound {name: 'Pipernonaline'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Acute gastritis with ulceration'});
MATCH (h:Herb {id: 'HERB-025'}), (cond:Condition {name: 'Acute gastritis with ulceration'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Pitta prakopa state without cooling Anupana'});
MATCH (h:Herb {id: 'HERB-025'}), (cond:Condition {name: 'Pitta prakopa state without cooling Anupana'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-026'}) SET h.common_name = 'Maricha', h.sanskrit_name = 'Maricha', h.botanical_name = 'Piper nigrum', h.traditional_uses = ['Trikatu component', 'Pramathi (Channel-clearing for Dhatu nourishment)', 'Deepana'];

MERGE (c:Compound {name: 'Piperine'});
MATCH (h:Herb {id: 'HERB-026'}), (c:Compound {name: 'Piperine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Chavicine'});
MATCH (h:Herb {id: 'HERB-026'}), (c:Compound {name: 'Chavicine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Piperidine'});
MATCH (h:Herb {id: 'HERB-026'}), (c:Compound {name: 'Piperidine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Caryophyllene'});
MATCH (h:Herb {id: 'HERB-026'}), (c:Compound {name: 'Caryophyllene'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Active peptic ulceration'});
MATCH (h:Herb {id: 'HERB-026'}), (cond:Condition {name: 'Active peptic ulceration'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Severe esophageal reflux'});
MATCH (h:Herb {id: 'HERB-026'}), (cond:Condition {name: 'Severe esophageal reflux'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-027'}) SET h.common_name = 'Shilajit', h.sanskrit_name = 'Shuddha Shilajit', h.botanical_name = 'Asphaltum punjabianum', h.traditional_uses = ['Rasayana', 'Kshaya', 'Pandu adjuvant', 'Dhatu Poshaka'];

MERGE (c:Compound {name: 'Fulvic acid'});
MATCH (h:Herb {id: 'HERB-027'}), (c:Compound {name: 'Fulvic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Humic acid'});
MATCH (h:Herb {id: 'HERB-027'}), (c:Compound {name: 'Humic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Dibenzo-alpha-pyrones'});
MATCH (h:Herb {id: 'HERB-027'}), (c:Compound {name: 'Dibenzo-alpha-pyrones'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Micro-trace elements'});
MATCH (h:Herb {id: 'HERB-027'}), (c:Compound {name: 'Micro-trace elements'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Hyperuricemia / active gouty arthritis'});
MATCH (h:Herb {id: 'HERB-027'}), (cond:Condition {name: 'Hyperuricemia / active gouty arthritis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Hemochromatosis'});
MATCH (h:Herb {id: 'HERB-027'}), (cond:Condition {name: 'Hemochromatosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Severe cardiac failure'});
MATCH (h:Herb {id: 'HERB-027'}), (cond:Condition {name: 'Severe cardiac failure'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-028'}) SET h.common_name = 'Katuki', h.sanskrit_name = 'Katuki', h.botanical_name = 'Picrorhiza kurroa', h.traditional_uses = ['Yakritodara in Pandu', 'Kamala', 'Bile secretagogue', 'Pitta Rechana'];

MERGE (c:Compound {name: 'Picroside I'});
MATCH (h:Herb {id: 'HERB-028'}), (c:Compound {name: 'Picroside I'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Picroside II'});
MATCH (h:Herb {id: 'HERB-028'}), (c:Compound {name: 'Picroside II'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Kutkoside'});
MATCH (h:Herb {id: 'HERB-028'}), (c:Compound {name: 'Kutkoside'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Apocynin'});
MATCH (h:Herb {id: 'HERB-028'}), (c:Compound {name: 'Apocynin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Severe non-infectious chronic diarrhea'});
MATCH (h:Herb {id: 'HERB-028'}), (cond:Condition {name: 'Severe non-infectious chronic diarrhea'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Hypotension with cardiac glycosides'});
MATCH (h:Herb {id: 'HERB-028'}), (cond:Condition {name: 'Hypotension with cardiac glycosides'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-029'}) SET h.common_name = 'Manjistha', h.sanskrit_name = 'Manjistha', h.botanical_name = 'Rubia cordifolia', h.traditional_uses = ['Raktashodhaka', 'Pandu Raktapitta', 'Varnya', 'Rasayana'];

MERGE (c:Compound {name: 'Purpurin'});
MATCH (h:Herb {id: 'HERB-029'}), (c:Compound {name: 'Purpurin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Munjistin'});
MATCH (h:Herb {id: 'HERB-029'}), (c:Compound {name: 'Munjistin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Alizarin'});
MATCH (h:Herb {id: 'HERB-029'}), (c:Compound {name: 'Alizarin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Rubiadin'});
MATCH (h:Herb {id: 'HERB-029'}), (c:Compound {name: 'Rubiadin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'Pregnancy (mild emmenagogue)'});
MATCH (h:Herb {id: 'HERB-029'}), (cond:Condition {name: 'Pregnancy (mild emmenagogue)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (cond:Condition {name: 'Severe acute nephrolithiasis'});
MATCH (h:Herb {id: 'HERB-029'}), (cond:Condition {name: 'Severe acute nephrolithiasis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-030'}) SET h.common_name = 'Sariva', h.sanskrit_name = 'Shveta Sariva', h.botanical_name = 'Hemidesmus indicus', h.traditional_uses = ['Pitta Pandu', 'Daha Prashamana', 'Rakta Prasadana', 'Deepana'];

MERGE (c:Compound {name: '2-Hydroxy-4-methoxybenzaldehyde'});
MATCH (h:Herb {id: 'HERB-030'}), (c:Compound {name: '2-Hydroxy-4-methoxybenzaldehyde'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Lupeol'});
MATCH (h:Herb {id: 'HERB-030'}), (c:Compound {name: 'Lupeol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Hemidesmin'});
MATCH (h:Herb {id: 'HERB-030'}), (c:Compound {name: 'Hemidesmin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (c:Compound {name: 'Resin acids'});
MATCH (h:Herb {id: 'HERB-030'}), (c:Compound {name: 'Resin acids'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MERGE (cond:Condition {name: 'None prominent at therapeutic doses; caution in marked bradycardia'});
MATCH (h:Herb {id: 'HERB-030'}), (cond:Condition {name: 'None prominent at therapeutic doses; caution in marked bradycardia'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (e:Enzyme {name: 'CYP3A4'}) SET e.description = 'Major drug-metabolizing cytochrome P450 enzyme responsible for oxidation of >50% of marketed pharmaceuticals.';

MERGE (e:Enzyme {name: 'CYP2C9'}) SET e.description = 'Key enzyme for narrow-therapeutic-index drugs including S-warfarin, NSAIDs, and Losartan bioactivation.';

MERGE (e:Enzyme {name: 'CYP2C19'}) SET e.description = 'Critical for metabolism of proton pump inhibitors, antiepileptics, and bioactivation of clopidogrel.';

MERGE (e:Enzyme {name: 'CYP2D6'}) SET e.description = 'Responsible for metabolism of cardiovascular beta-blockers, antiarrhythmics, SSRIs, and tricyclic antidepressants.';

MERGE (e:Enzyme {name: 'CYP1A2'}) SET e.description = 'Metabolizes methylxanthines, theophylline, and certain atypical antipsychotics; inhibited by fluoroquinolones.';

MERGE (e:Enzyme {name: 'CYP2B6'}) SET e.description = 'Involved in the clearance of antineoplastics, bupropion, and certain antiretrovirals and psychotropics.';

MERGE (e:Enzyme {name: 'CYP2C8'}) SET e.description = 'Metabolizes thiazolidinediones, paclitaxel, repaglinide, and certain statins.';

MERGE (e:Enzyme {name: 'CYP2E1'}) SET e.description = 'Metabolizes small hydrophobic and halogenated compounds including paracetamol and ethanol.';

MERGE (e:Enzyme {name: 'P-glycoprotein (ABCB1)'}) SET e.description = 'ATP-dependent intestinal and blood-brain-barrier efflux transporter controlling drug bioavailability.';

MERGE (e:Enzyme {name: 'OAT1/OAT3 (SLC22A6/SLC22A8)'}) SET e.description = 'Renal proximal tubule basolateral uptake transporters responsible for active tubular secretion of organic anions.';

MERGE (d:Drug {id: 'DRUG-001'}) SET d.generic_name = 'Metformin', d.drug_class = 'Biguanide Antidiabetic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'OCT1'});
MATCH (d:Drug {id: 'DRUG-001'}), (e:Enzyme {name: 'OCT1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'OCT2'});
MATCH (d:Drug {id: 'DRUG-001'}), (e:Enzyme {name: 'OCT2'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'MATE1'});
MATCH (d:Drug {id: 'DRUG-001'}), (e:Enzyme {name: 'MATE1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'AMPK'});
MATCH (d:Drug {id: 'DRUG-001'}), (t:Target {name: 'AMPK'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-002'}) SET d.generic_name = 'Omeprazole', d.drug_class = 'Proton Pump Inhibitor (PPI)', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2C19'});
MATCH (d:Drug {id: 'DRUG-002'}), (e:Enzyme {name: 'CYP2C19'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-002'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'H+/K+ ATPase'});
MATCH (d:Drug {id: 'DRUG-002'}), (t:Target {name: 'H+/K+ ATPase'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-003'}) SET d.generic_name = 'Atorvastatin', d.drug_class = 'HMG-CoA Reductase Inhibitor', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-003'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'HMG-CoA Reductase'});
MATCH (d:Drug {id: 'DRUG-003'}), (t:Target {name: 'HMG-CoA Reductase'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-004'}) SET d.generic_name = 'Losartan', d.drug_class = 'Angiotensin II Receptor Blocker (ARB)', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2C9'});
MATCH (d:Drug {id: 'DRUG-004'}), (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-004'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'AT1 Receptor'});
MATCH (d:Drug {id: 'DRUG-004'}), (t:Target {name: 'AT1 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-005'}) SET d.generic_name = 'Amlodipine', d.drug_class = 'Dihydropyridine Calcium Channel Blocker', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-005'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'L-type Calcium Channels'});
MATCH (d:Drug {id: 'DRUG-005'}), (t:Target {name: 'L-type Calcium Channels'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-006'}) SET d.generic_name = 'Ferrous Sulfate', d.drug_class = 'Oral Hematinic / Iron Supplement', d.narrow_therapeutic_index = false;

MERGE (t:Target {name: 'DMT1'});
MATCH (d:Drug {id: 'DRUG-006'}), (t:Target {name: 'DMT1'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (t:Target {name: 'Transferrin'});
MATCH (d:Drug {id: 'DRUG-006'}), (t:Target {name: 'Transferrin'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-007'}) SET d.generic_name = 'Levothyroxine', d.drug_class = 'Synthetic Thyroid Hormone', d.narrow_therapeutic_index = true;

MERGE (e:Enzyme {name: 'Deiodinase'});
MATCH (d:Drug {id: 'DRUG-007'}), (e:Enzyme {name: 'Deiodinase'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-007'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'UGT1A1'});
MATCH (d:Drug {id: 'DRUG-007'}), (e:Enzyme {name: 'UGT1A1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Thyroid Hormone Receptors TR-alpha/beta'});
MATCH (d:Drug {id: 'DRUG-007'}), (t:Target {name: 'Thyroid Hormone Receptors TR-alpha/beta'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-008'}) SET d.generic_name = 'Clonazepam', d.drug_class = 'Benzodiazepine Anticonvulsant / Anxiolytic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-008'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'GABA-A Receptor'});
MATCH (d:Drug {id: 'DRUG-008'}), (t:Target {name: 'GABA-A Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-009'}) SET d.generic_name = 'Warfarin', d.drug_class = 'Vitamin K Antagonist Anticoagulant', d.narrow_therapeutic_index = true;

MERGE (e:Enzyme {name: 'CYP2C9'});
MATCH (d:Drug {id: 'DRUG-009'}), (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP1A2'});
MATCH (d:Drug {id: 'DRUG-009'}), (e:Enzyme {name: 'CYP1A2'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-009'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'VKORC1'});
MATCH (d:Drug {id: 'DRUG-009'}), (t:Target {name: 'VKORC1'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-010'}) SET d.generic_name = 'Aspirin', d.drug_class = 'Antiplatelet / NSAID', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'Esterases'});
MATCH (d:Drug {id: 'DRUG-010'}), (e:Enzyme {name: 'Esterases'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP2C9'});
MATCH (d:Drug {id: 'DRUG-010'}), (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'COX-1'});
MATCH (d:Drug {id: 'DRUG-010'}), (t:Target {name: 'COX-1'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (t:Target {name: 'COX-2'});
MATCH (d:Drug {id: 'DRUG-010'}), (t:Target {name: 'COX-2'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-011'}) SET d.generic_name = 'Enalapril', d.drug_class = 'ACE Inhibitor Antihypertensive', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'Hepatic Carboxylesterase-1'});
MATCH (d:Drug {id: 'DRUG-011'}), (e:Enzyme {name: 'Hepatic Carboxylesterase-1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Angiotensin-Converting Enzyme'});
MATCH (d:Drug {id: 'DRUG-011'}), (t:Target {name: 'Angiotensin-Converting Enzyme'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-012'}) SET d.generic_name = 'Ramipril', d.drug_class = 'ACE Inhibitor Antihypertensive', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'Hepatic Esterases'});
MATCH (d:Drug {id: 'DRUG-012'}), (e:Enzyme {name: 'Hepatic Esterases'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Angiotensin-Converting Enzyme'});
MATCH (d:Drug {id: 'DRUG-012'}), (t:Target {name: 'Angiotensin-Converting Enzyme'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-013'}) SET d.generic_name = 'Atenolol', d.drug_class = 'Beta-1 Selective Adrenergic Blocker', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'Minimal hepatic (Renal excretion 85%)'});
MATCH (d:Drug {id: 'DRUG-013'}), (e:Enzyme {name: 'Minimal hepatic (Renal excretion 85%)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Beta-1 Adrenergic Receptor'});
MATCH (d:Drug {id: 'DRUG-013'}), (t:Target {name: 'Beta-1 Adrenergic Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-014'}) SET d.generic_name = 'Bisoprolol', d.drug_class = 'Beta-1 Selective Adrenergic Blocker', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-014'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP2D6'});
MATCH (d:Drug {id: 'DRUG-014'}), (e:Enzyme {name: 'CYP2D6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Beta-1 Adrenergic Receptor'});
MATCH (d:Drug {id: 'DRUG-014'}), (t:Target {name: 'Beta-1 Adrenergic Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-015'}) SET d.generic_name = 'Hydrochlorothiazide', d.drug_class = 'Thiazide Diuretic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'Renal elimination unchanged'});
MATCH (d:Drug {id: 'DRUG-015'}), (e:Enzyme {name: 'Renal elimination unchanged'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Na+/Cl- Cotransporter NCCT'});
MATCH (d:Drug {id: 'DRUG-015'}), (t:Target {name: 'Na+/Cl- Cotransporter NCCT'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-016'}) SET d.generic_name = 'Furosemide', d.drug_class = 'Loop Diuretic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2C9'});
MATCH (d:Drug {id: 'DRUG-016'}), (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'Glucuronidation'});
MATCH (d:Drug {id: 'DRUG-016'}), (e:Enzyme {name: 'Glucuronidation'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Na+/K+/2Cl- Cotransporter NKCC2'});
MATCH (d:Drug {id: 'DRUG-016'}), (t:Target {name: 'Na+/K+/2Cl- Cotransporter NKCC2'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-017'}) SET d.generic_name = 'Spironolactone', d.drug_class = 'Potassium-Sparing Aldosterone Antagonist', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-017'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Mineralocorticoid Receptor'});
MATCH (d:Drug {id: 'DRUG-017'}), (t:Target {name: 'Mineralocorticoid Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-018'}) SET d.generic_name = 'Digoxin', d.drug_class = 'Cardiac Glycoside Inotrope', d.narrow_therapeutic_index = true;

MERGE (e:Enzyme {name: 'P-gp / ABCB1 Substrate'});
MATCH (d:Drug {id: 'DRUG-018'}), (e:Enzyme {name: 'P-gp / ABCB1 Substrate'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Na+/K+ ATPase'});
MATCH (d:Drug {id: 'DRUG-018'}), (t:Target {name: 'Na+/K+ ATPase'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-019'}) SET d.generic_name = 'Glibenclamide', d.drug_class = 'Sulfonylurea Antidiabetic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2C9'});
MATCH (d:Drug {id: 'DRUG-019'}), (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-019'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'SUR1 / Kir6.2 channel'});
MATCH (d:Drug {id: 'DRUG-019'}), (t:Target {name: 'SUR1 / Kir6.2 channel'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-020'}) SET d.generic_name = 'Gliclazide', d.drug_class = 'Second-Generation Sulfonylurea', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2C9'});
MATCH (d:Drug {id: 'DRUG-020'}), (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP2C19'});
MATCH (d:Drug {id: 'DRUG-020'}), (e:Enzyme {name: 'CYP2C19'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'SUR1 Pancreatic Beta Cell Receptor'});
MATCH (d:Drug {id: 'DRUG-020'}), (t:Target {name: 'SUR1 Pancreatic Beta Cell Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-021'}) SET d.generic_name = 'Sitagliptin', d.drug_class = 'DPP-4 Inhibitor Antidiabetic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-021'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP2C8'});
MATCH (d:Drug {id: 'DRUG-021'}), (e:Enzyme {name: 'CYP2C8'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Dipeptidyl Peptidase-4'});
MATCH (d:Drug {id: 'DRUG-021'}), (t:Target {name: 'Dipeptidyl Peptidase-4'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-022'}) SET d.generic_name = 'Empagliflozin', d.drug_class = 'SGLT-2 Inhibitor', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'UGT2B7'});
MATCH (d:Drug {id: 'DRUG-022'}), (e:Enzyme {name: 'UGT2B7'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'UGT1A3'});
MATCH (d:Drug {id: 'DRUG-022'}), (e:Enzyme {name: 'UGT1A3'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'UGT1A8'});
MATCH (d:Drug {id: 'DRUG-022'}), (e:Enzyme {name: 'UGT1A8'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Sodium-Glucose Cotransporter 2'});
MATCH (d:Drug {id: 'DRUG-022'}), (t:Target {name: 'Sodium-Glucose Cotransporter 2'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-023'}) SET d.generic_name = 'Pantoprazole', d.drug_class = 'Proton Pump Inhibitor', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2C19'});
MATCH (d:Drug {id: 'DRUG-023'}), (e:Enzyme {name: 'CYP2C19'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-023'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'H+/K+ ATPase'});
MATCH (d:Drug {id: 'DRUG-023'}), (t:Target {name: 'H+/K+ ATPase'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-024'}) SET d.generic_name = 'Ranitidine', d.drug_class = 'H2 Receptor Antagonist', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP1A2'});
MATCH (d:Drug {id: 'DRUG-024'}), (e:Enzyme {name: 'CYP1A2'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP2D6'});
MATCH (d:Drug {id: 'DRUG-024'}), (e:Enzyme {name: 'CYP2D6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Histamine H2 Receptor'});
MATCH (d:Drug {id: 'DRUG-024'}), (t:Target {name: 'Histamine H2 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-025'}) SET d.generic_name = 'Ciprofloxacin', d.drug_class = 'Fluoroquinolone Antibiotic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP1A2 (Strong Inhibitor)'});
MATCH (d:Drug {id: 'DRUG-025'}), (e:Enzyme {name: 'CYP1A2 (Strong Inhibitor)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Bacterial DNA Gyrase'});
MATCH (d:Drug {id: 'DRUG-025'}), (t:Target {name: 'Bacterial DNA Gyrase'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (t:Target {name: 'Topoisomerase IV'});
MATCH (d:Drug {id: 'DRUG-025'}), (t:Target {name: 'Topoisomerase IV'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-026'}) SET d.generic_name = 'Doxycycline', d.drug_class = 'Tetracycline Antibiotic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'Non-enzymatic Chelation'});
MATCH (d:Drug {id: 'DRUG-026'}), (e:Enzyme {name: 'Non-enzymatic Chelation'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Bacterial 30S Ribosome Subunit'});
MATCH (d:Drug {id: 'DRUG-026'}), (t:Target {name: 'Bacterial 30S Ribosome Subunit'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-027'}) SET d.generic_name = 'Amoxicillin', d.drug_class = 'Aminopenicillin Antibiotic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'Renal excretion unchanged'});
MATCH (d:Drug {id: 'DRUG-027'}), (e:Enzyme {name: 'Renal excretion unchanged'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Penicillin-Binding Proteins (PBPs)'});
MATCH (d:Drug {id: 'DRUG-027'}), (t:Target {name: 'Penicillin-Binding Proteins (PBPs)'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-028'}) SET d.generic_name = 'Azithromycin', d.drug_class = 'Macrolide Antibiotic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP3A4 (Weak)'});
MATCH (d:Drug {id: 'DRUG-028'}), (e:Enzyme {name: 'CYP3A4 (Weak)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'Biliary excretion'});
MATCH (d:Drug {id: 'DRUG-028'}), (e:Enzyme {name: 'Biliary excretion'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Bacterial 50S Ribosome Subunit'});
MATCH (d:Drug {id: 'DRUG-028'}), (t:Target {name: 'Bacterial 50S Ribosome Subunit'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-029'}) SET d.generic_name = 'Ibuprofen', d.drug_class = 'NSAID Non-selective', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2C9'});
MATCH (d:Drug {id: 'DRUG-029'}), (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP2C8'});
MATCH (d:Drug {id: 'DRUG-029'}), (e:Enzyme {name: 'CYP2C8'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'COX-1'});
MATCH (d:Drug {id: 'DRUG-029'}), (t:Target {name: 'COX-1'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (t:Target {name: 'COX-2'});
MATCH (d:Drug {id: 'DRUG-029'}), (t:Target {name: 'COX-2'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-030'}) SET d.generic_name = 'Diclofenac', d.drug_class = 'Acetic Acid Derivative NSAID', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2C9'});
MATCH (d:Drug {id: 'DRUG-030'}), (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'UGT2B7'});
MATCH (d:Drug {id: 'DRUG-030'}), (e:Enzyme {name: 'UGT2B7'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'COX-1'});
MATCH (d:Drug {id: 'DRUG-030'}), (t:Target {name: 'COX-1'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (t:Target {name: 'COX-2'});
MATCH (d:Drug {id: 'DRUG-030'}), (t:Target {name: 'COX-2'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-031'}) SET d.generic_name = 'Paracetamol', d.drug_class = 'Aniline Analgesic / Antipyretic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2E1'});
MATCH (d:Drug {id: 'DRUG-031'}), (e:Enzyme {name: 'CYP2E1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'UGT1A6'});
MATCH (d:Drug {id: 'DRUG-031'}), (e:Enzyme {name: 'UGT1A6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'SULT1A1'});
MATCH (d:Drug {id: 'DRUG-031'}), (e:Enzyme {name: 'SULT1A1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Central TRPA1'});
MATCH (d:Drug {id: 'DRUG-031'}), (t:Target {name: 'Central TRPA1'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (t:Target {name: 'COX-3 putative'});
MATCH (d:Drug {id: 'DRUG-031'}), (t:Target {name: 'COX-3 putative'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-032'}) SET d.generic_name = 'Tramadol', d.drug_class = 'Opioid Analgesic / SNRI', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2D6'});
MATCH (d:Drug {id: 'DRUG-032'}), (e:Enzyme {name: 'CYP2D6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-032'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Mu-opioid receptor'});
MATCH (d:Drug {id: 'DRUG-032'}), (t:Target {name: 'Mu-opioid receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (t:Target {name: 'Serotonin/Norepinephrine transporter'});
MATCH (d:Drug {id: 'DRUG-032'}), (t:Target {name: 'Serotonin/Norepinephrine transporter'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-033'}) SET d.generic_name = 'Sertraline', d.drug_class = 'Selective Serotonin Reuptake Inhibitor (SSRI)', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2B6'});
MATCH (d:Drug {id: 'DRUG-033'}), (e:Enzyme {name: 'CYP2B6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP2C19'});
MATCH (d:Drug {id: 'DRUG-033'}), (e:Enzyme {name: 'CYP2C19'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP2D6'});
MATCH (d:Drug {id: 'DRUG-033'}), (e:Enzyme {name: 'CYP2D6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-033'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Serotonin Transporter (SERT)'});
MATCH (d:Drug {id: 'DRUG-033'}), (t:Target {name: 'Serotonin Transporter (SERT)'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-034'}) SET d.generic_name = 'Fluoxetine', d.drug_class = 'Selective Serotonin Reuptake Inhibitor (SSRI)', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2D6 (Potent Inhibitor)'});
MATCH (d:Drug {id: 'DRUG-034'}), (e:Enzyme {name: 'CYP2D6 (Potent Inhibitor)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP2C9'});
MATCH (d:Drug {id: 'DRUG-034'}), (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-034'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Serotonin Transporter (SERT)'});
MATCH (d:Drug {id: 'DRUG-034'}), (t:Target {name: 'Serotonin Transporter (SERT)'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-035'}) SET d.generic_name = 'Amitriptyline', d.drug_class = 'Tricyclic Antidepressant (TCA)', d.narrow_therapeutic_index = true;

MERGE (e:Enzyme {name: 'CYP2D6'});
MATCH (d:Drug {id: 'DRUG-035'}), (e:Enzyme {name: 'CYP2D6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP2C19'});
MATCH (d:Drug {id: 'DRUG-035'}), (e:Enzyme {name: 'CYP2C19'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-035'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: '5-HT/NE Reuptake'});
MATCH (d:Drug {id: 'DRUG-035'}), (t:Target {name: '5-HT/NE Reuptake'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (t:Target {name: 'H1 Receptor'});
MATCH (d:Drug {id: 'DRUG-035'}), (t:Target {name: 'H1 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (t:Target {name: 'M1 Receptor'});
MATCH (d:Drug {id: 'DRUG-035'}), (t:Target {name: 'M1 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-036'}) SET d.generic_name = 'Gabapentin', d.drug_class = 'Gabapentinoid Anticonvulsant', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'Renal elimination (LAT1 transporter)'});
MATCH (d:Drug {id: 'DRUG-036'}), (e:Enzyme {name: 'Renal elimination (LAT1 transporter)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Alpha-2-delta Voltage-Gated Calcium Channels'});
MATCH (d:Drug {id: 'DRUG-036'}), (t:Target {name: 'Alpha-2-delta Voltage-Gated Calcium Channels'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-037'}) SET d.generic_name = 'Carbamazepine', d.drug_class = 'Iminostilbene Anticonvulsant', d.narrow_therapeutic_index = true;

MERGE (e:Enzyme {name: 'CYP3A4 (Potent Auto-Inducer)'});
MATCH (d:Drug {id: 'DRUG-037'}), (e:Enzyme {name: 'CYP3A4 (Potent Auto-Inducer)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP2C8'});
MATCH (d:Drug {id: 'DRUG-037'}), (e:Enzyme {name: 'CYP2C8'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Voltage-Gated Sodium Channels'});
MATCH (d:Drug {id: 'DRUG-037'}), (t:Target {name: 'Voltage-Gated Sodium Channels'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-038'}) SET d.generic_name = 'Phenytoin', d.drug_class = 'Hydantoin Anticonvulsant', d.narrow_therapeutic_index = true;

MERGE (e:Enzyme {name: 'CYP2C9'});
MATCH (d:Drug {id: 'DRUG-038'}), (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP2C19 (Potent Inducer)'});
MATCH (d:Drug {id: 'DRUG-038'}), (e:Enzyme {name: 'CYP2C19 (Potent Inducer)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Voltage-Gated Sodium Channels'});
MATCH (d:Drug {id: 'DRUG-038'}), (t:Target {name: 'Voltage-Gated Sodium Channels'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-039'}) SET d.generic_name = 'Prednisolone', d.drug_class = 'Systemic Corticosteroid', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-039'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: '11-beta-HSD1'});
MATCH (d:Drug {id: 'DRUG-039'}), (e:Enzyme {name: '11-beta-HSD1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Glucocorticoid Receptor'});
MATCH (d:Drug {id: 'DRUG-039'}), (t:Target {name: 'Glucocorticoid Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-040'}) SET d.generic_name = 'Methotrexate', d.drug_class = 'Antimetabolite Immunosuppressant', d.narrow_therapeutic_index = true;

MERGE (e:Enzyme {name: 'Renal clearance (OAT1/OAT3)'});
MATCH (d:Drug {id: 'DRUG-040'}), (e:Enzyme {name: 'Renal clearance (OAT1/OAT3)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'Aldehyde oxidase'});
MATCH (d:Drug {id: 'DRUG-040'}), (e:Enzyme {name: 'Aldehyde oxidase'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Dihydrofolate Reductase (DHFR)'});
MATCH (d:Drug {id: 'DRUG-040'}), (t:Target {name: 'Dihydrofolate Reductase (DHFR)'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-041'}) SET d.generic_name = 'Clopidogrel', d.drug_class = 'Thienopyridine Antiplatelet', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2C19 (Bioactivation)'});
MATCH (d:Drug {id: 'DRUG-041'}), (e:Enzyme {name: 'CYP2C19 (Bioactivation)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-041'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP1A2'});
MATCH (d:Drug {id: 'DRUG-041'}), (e:Enzyme {name: 'CYP1A2'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Platelet P2Y12 Receptor'});
MATCH (d:Drug {id: 'DRUG-041'}), (t:Target {name: 'Platelet P2Y12 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-042'}) SET d.generic_name = 'Simvastatin', d.drug_class = 'HMG-CoA Reductase Inhibitor', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP3A4 (Major)'});
MATCH (d:Drug {id: 'DRUG-042'}), (e:Enzyme {name: 'CYP3A4 (Major)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'HMG-CoA Reductase'});
MATCH (d:Drug {id: 'DRUG-042'}), (t:Target {name: 'HMG-CoA Reductase'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-043'}) SET d.generic_name = 'Calcium Carbonate', d.drug_class = 'Mineral Supplement / Phosphate Binder', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'Gastrointestinal Chelation'});
MATCH (d:Drug {id: 'DRUG-043'}), (e:Enzyme {name: 'Gastrointestinal Chelation'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Calcium-Sensing Receptor'});
MATCH (d:Drug {id: 'DRUG-043'}), (t:Target {name: 'Calcium-Sensing Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-044'}) SET d.generic_name = 'Folic Acid', d.drug_class = 'Water-soluble Vitamin Hematinic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'Dihydrofolate Reductase'});
MATCH (d:Drug {id: 'DRUG-044'}), (e:Enzyme {name: 'Dihydrofolate Reductase'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Folate Receptors FOLR1/FOLR2'});
MATCH (d:Drug {id: 'DRUG-044'}), (t:Target {name: 'Folate Receptors FOLR1/FOLR2'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-045'}) SET d.generic_name = 'Hydroxyzine', d.drug_class = 'First-Generation Antihistamine', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'Alcohol Dehydrogenase'});
MATCH (d:Drug {id: 'DRUG-045'}), (e:Enzyme {name: 'Alcohol Dehydrogenase'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4/5'});
MATCH (d:Drug {id: 'DRUG-045'}), (e:Enzyme {name: 'CYP3A4/5'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Histamine H1 Receptor'});
MATCH (d:Drug {id: 'DRUG-045'}), (t:Target {name: 'Histamine H1 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (t:Target {name: '5-HT2A Receptor'});
MATCH (d:Drug {id: 'DRUG-045'}), (t:Target {name: '5-HT2A Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-046'}) SET d.generic_name = 'Diazepam', d.drug_class = 'Long-Acting Benzodiazepine', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2C19'});
MATCH (d:Drug {id: 'DRUG-046'}), (e:Enzyme {name: 'CYP2C19'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-046'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'GABA-A Receptor'});
MATCH (d:Drug {id: 'DRUG-046'}), (t:Target {name: 'GABA-A Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-047'}) SET d.generic_name = 'Metoprolol', d.drug_class = 'Beta-1 Selective Adrenergic Blocker', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP2D6 (Major)'});
MATCH (d:Drug {id: 'DRUG-047'}), (e:Enzyme {name: 'CYP2D6 (Major)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Beta-1 Adrenergic Receptor'});
MATCH (d:Drug {id: 'DRUG-047'}), (t:Target {name: 'Beta-1 Adrenergic Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-048'}) SET d.generic_name = 'Salbutamol', d.drug_class = 'Short-Acting Beta-2 Adrenergic Agonist', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'SULT1A3'});
MATCH (d:Drug {id: 'DRUG-048'}), (e:Enzyme {name: 'SULT1A3'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Beta-2 Adrenergic Receptor'});
MATCH (d:Drug {id: 'DRUG-048'}), (t:Target {name: 'Beta-2 Adrenergic Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-049'}) SET d.generic_name = 'Domperidone', d.drug_class = 'Dopamine D2 Receptor Antagonist Prokinetic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'CYP3A4'});
MATCH (d:Drug {id: 'DRUG-049'}), (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Peripheral Dopamine D2 Receptor'});
MATCH (d:Drug {id: 'DRUG-049'}), (t:Target {name: 'Peripheral Dopamine D2 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-050'}) SET d.generic_name = 'Cephalexin', d.drug_class = 'First-Generation Cephalosporin Antibiotic', d.narrow_therapeutic_index = false;

MERGE (e:Enzyme {name: 'Renal excretion unchanged (>90%)'});
MATCH (d:Drug {id: 'DRUG-050'}), (e:Enzyme {name: 'Renal excretion unchanged (>90%)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MERGE (t:Target {name: 'Bacterial Cell Wall Penicillin-Binding Proteins'});
MATCH (d:Drug {id: 'DRUG-050'}), (t:Target {name: 'Bacterial Cell Wall Penicillin-Binding Proteins'}) MERGE (d)-[:ACTS_ON]->(t);

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Ashwagandha') AND toLower(d.generic_name) = toLower('Clonazepam') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-001'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'GABA-A receptor agonistic synergism leading to enhanced central nervous system depression and excessive daytime sedation.', r.evidence_level = 'Established', r.pmid = '31405862';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Ashwagandha') AND toLower(d.generic_name) = toLower('Levothyroxine') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-002'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Withania stimulates endogenous thyroid hormone synthesis (T3 and T4), potentially causing subclinical hyperthyroidism or thyrotoxicosis when co-administered with Levothyroxine.', r.evidence_level = 'Established', r.pmid = '28829155';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Mandura Bhasma') AND toLower(d.generic_name) = toLower('Levothyroxine') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-003'}]->(d) SET r.severity = 'High', r.mechanism = 'Ferric ions in Mandura form insoluble ferric-thyroxine chelates in the acidic gastric lumen, reducing oral bioavailability of Levothyroxine by 40-60%.', r.evidence_level = 'Established', r.pmid = '2183431';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Mandura Bhasma') AND toLower(d.generic_name) = toLower('Omeprazole') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-004'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Proton pump inhibitors elevate gastric pH, which reduces the solubility and gastrointestinal reduction of Fe3+ in Mandura Bhasma, thereby diminishing therapeutic iron bioavailability.', r.evidence_level = 'Established', r.pmid = '23901244';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Yashtimadhu') AND toLower(d.generic_name) = toLower('Losartan') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-005'}]->(d) SET r.severity = 'High', r.mechanism = 'Glycyrrhizin inhibits 11-beta-hydroxysteroid dehydrogenase type 2, resulting in cortisol-induced mineralocorticoid receptor hyperactivation, sodium retention, hypokalemia, and elevated blood pressure, directly antagonizing the antihypertensive efficacy of Losartan.', r.evidence_level = 'Established', r.pmid = '12030999';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Yashtimadhu') AND toLower(d.generic_name) = toLower('Warfarin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-006'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Glabridin exhibits weak CYP2C9 inhibition, which can reduce S-warfarin clearance and elevate INR, increasing hemorrhagic risk.', r.evidence_level = 'Probable', r.pmid = '18465169';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Punarnava') AND toLower(d.generic_name) = toLower('Losartan') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-007'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Additive natriuretic and potassium-sparing tendencies may lead to transient hypotension and hyperkalemia if baseline renal function is impaired.', r.evidence_level = 'Probable', r.pmid = '25271874';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Guduchi') AND toLower(d.generic_name) = toLower('Metformin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-008'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Berberine and related alkaloids in Tinospora cordifolia enhance insulin sensitivity and AMPK phosphorylation, producing additive blood-glucose lowering with Metformin.', r.evidence_level = 'Probable', r.pmid = '22837322';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Mandura Bhasma') AND toLower(d.generic_name) = toLower('Ciprofloxacin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-009'}]->(d) SET r.severity = 'High', r.mechanism = 'Multivalent ferric cations chelate with fluoroquinolones in the gut, reducing ciprofloxacin absorption by up to 75%.', r.evidence_level = 'Established', r.pmid = '1940733';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Mandura Bhasma') AND toLower(d.generic_name) = toLower('Doxycycline') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-010'}]->(d) SET r.severity = 'High', r.mechanism = 'Iron salts bind orally administered doxycycline forming unabsorbable chelate complexes.', r.evidence_level = 'Established', r.pmid = '1133592';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Yashtimadhu') AND toLower(d.generic_name) = toLower('Hydrochlorothiazide') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-011'}]->(d) SET r.severity = 'High', r.mechanism = 'Glycyrrhizin and thiazide diuretics both promote urinary potassium wasting, precipitating profound hypokalemia and arrhythmias.', r.evidence_level = 'Established', r.pmid = '10410408';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Yashtimadhu') AND toLower(d.generic_name) = toLower('Furosemide') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-012'}]->(d) SET r.severity = 'High', r.mechanism = 'Combined kaliuretic activity of loop diuretic and licorice leads to dangerous potassium depletion.', r.evidence_level = 'Established', r.pmid = '15379899';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Yashtimadhu') AND toLower(d.generic_name) = toLower('Digoxin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-013'}]->(d) SET r.severity = 'High', r.mechanism = 'Licorice-induced hypokalemia sensitizes myocardial tissue to digitalis toxicity, triggering potentially fatal arrhythmias.', r.evidence_level = 'Established', r.pmid = '11056417';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Ashwagandha') AND toLower(d.generic_name) = toLower('Diazepam') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-014'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Additive central inhibitory GABAergic actions potentiate psychomotor impairment and sedation.', r.evidence_level = 'Established', r.pmid = '18617529';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Pippali') AND toLower(d.generic_name) = toLower('Phenytoin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-015'}]->(d) SET r.severity = 'High', r.mechanism = 'Piperine downregulates intestinal and hepatic CYP2C9 and P-glycoprotein, significantly elevating phenytoin AUC and serum concentrations toward toxic thresholds.', r.evidence_level = 'Established', r.pmid = '3742456';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Pippali') AND toLower(d.generic_name) = toLower('Propranolol') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-016'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Piperine enhances oral bioavailability and peak plasma concentrations of propranolol via intestinal glucuronidation inhibition.', r.evidence_level = 'Established', r.pmid = '10714457';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Maricha') AND toLower(d.generic_name) = toLower('Atorvastatin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-017'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Black pepper piperine inhibits enterocyte P-glycoprotein efflux and CYP3A4, increasing systemic statin exposure and risk of myopathy.', r.evidence_level = 'Probable', r.pmid = '23625327';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Punarnava') AND toLower(d.generic_name) = toLower('Furosemide') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-018'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Additive diuretic action may cause excessive volume contraction, prerenal azotemia, and postural dizziness.', r.evidence_level = 'Probable', r.pmid = '12895674';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Guduchi') AND toLower(d.generic_name) = toLower('Gliclazide') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-019'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Additive stimulation of pancreatic insulin release and peripheral glucose utilization.', r.evidence_level = 'Probable', r.pmid = '21479357';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Haritaki') AND toLower(d.generic_name) = toLower('Aspirin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-020'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'High tannin concentration and astringent properties of Haritaki combined with COX-1 inhibition may accentuate gastric mucosal friability.', r.evidence_level = 'Probable', r.pmid = '23281140';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Amalaki') AND toLower(d.generic_name) = toLower('Ferrous Sulfate') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-021'}]->(d) SET r.severity = 'Low', r.mechanism = 'Ascorbic acid maintains dietary and supplemental iron in the soluble Fe2+ ferrous state, enhancing DMT1 enterocyte uptake.', r.evidence_level = 'Established', r.pmid = '6940487';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shilajit') AND toLower(d.generic_name) = toLower('Metformin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-022'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Fulvic acid complexes improve insulin sensitivity, potentially deepening glucose-lowering effects of biguanides.', r.evidence_level = 'Probable', r.pmid = '27051082';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Katuki') AND toLower(d.generic_name) = toLower('Atorvastatin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-023'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Picroside components modulate hepatic CYP3A4 and biliary transporters, which may slightly alter statin clearance.', r.evidence_level = 'Possible', r.pmid = '18037651';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Manjistha') AND toLower(d.generic_name) = toLower('Warfarin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-024'}]->(d) SET r.severity = 'High', r.mechanism = 'Anthraquinones in Rubia cordifolia demonstrate antiplatelet and antithrombotic properties, compounding bleeding risks with vitamin K antagonists.', r.evidence_level = 'Established', r.pmid = '17336034';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Sariva') AND toLower(d.generic_name) = toLower('Amlodipine') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-025'}]->(d) SET r.severity = 'Low', r.mechanism = 'Mild peripheral vasodilation and natriuretic support may moderately enhance calcium channel blocker efficacy.', r.evidence_level = 'Possible', r.pmid = '18759195';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Navayasa Lauha') AND toLower(d.generic_name) = toLower('Levothyroxine') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-026'}]->(d) SET r.severity = 'High', r.mechanism = 'Iron content binds levothyroxine in gastric fluid, preventing absorption.', r.evidence_level = 'Established', r.pmid = '8064115';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Navayasa Lauha') AND toLower(d.generic_name) = toLower('Omeprazole') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-027'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Reduced gastric acidity diminishes the bio-dissolution of Lauha Bhasma.', r.evidence_level = 'Established', r.pmid = '18582445';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Arogyavardhini Vati') AND toLower(d.generic_name) = toLower('Methotrexate') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-028'}]->(d) SET r.severity = 'High', r.mechanism = 'Herbo-mineral constituents and Katuki in Arogyavardhini compete for organic anion renal excretory pathways, elevating methotrexate toxicity risk.', r.evidence_level = 'Probable', r.pmid = '22131759';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Arogyavardhini Vati') AND toLower(d.generic_name) = toLower('Atorvastatin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-029'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Both agents undergo significant hepatic clearance; heavy liver workload in pre-existing hepatic compromise.', r.evidence_level = 'Possible', r.pmid = '26009664';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Chandraprabha Vati') AND toLower(d.generic_name) = toLower('Spironolactone') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-030'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Potassium retention combined with multiple diuretic herb components may alter electrolyte homeostasis.', r.evidence_level = 'Possible', r.pmid = '23798883';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Lohasava') AND toLower(d.generic_name) = toLower('Metformin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-031'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Alcohol content in fermented asava combined with high-dose metformin can exacerbate dyspepsia and lactic acidosis vulnerability if patient is dehydrated.', r.evidence_level = 'Probable', r.pmid = '14684534';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Drakshasava') AND toLower(d.generic_name) = toLower('Glibenclamide') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-032'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Natural fruit sugars in Drakshasava may cause transient postprandial glucose spike followed by sulfonylurea-driven drop.', r.evidence_level = 'Possible', r.pmid = '21846312';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Kasisa Bhasma') AND toLower(d.generic_name) = toLower('Levothyroxine') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-033'}]->(d) SET r.severity = 'High', r.mechanism = 'Ferrous sulphate in Kasisa precipitates levothyroxine absorption.', r.evidence_level = 'Established', r.pmid = '1617415';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Swarna Makshika Bhasma') AND toLower(d.generic_name) = toLower('Penicillamine') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-034'}]->(d) SET r.severity = 'High', r.mechanism = 'Copper-iron calx binds penicillamine chelator, mutually neutralizing therapeutic effects.', r.evidence_level = 'Established', r.pmid = '3144185';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Loha Bhasma') AND toLower(d.generic_name) = toLower('Ciprofloxacin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-035'}]->(d) SET r.severity = 'High', r.mechanism = 'Insoluble iron-quinolone complex impairs antibiotic efficacy.', r.evidence_level = 'Established', r.pmid = '2263432';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Dadima') AND toLower(d.generic_name) = toLower('Ramipril') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-036'}]->(d) SET r.severity = 'Low', r.mechanism = 'Natural ACE-inhibitory tannins in pomegranate extract complement synthetic ACE inhibition.', r.evidence_level = 'Probable', r.pmid = '11483373';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shunthi') AND toLower(d.generic_name) = toLower('Aspirin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-037'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Gingerols inhibit thromboxane synthetase and COX-1, presenting additive antiplatelet effects with low-dose aspirin.', r.evidence_level = 'Established', r.pmid = '17569207';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shunthi') AND toLower(d.generic_name) = toLower('Warfarin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-038'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Mild platelet aggregation inhibition increases bleeding propensity in warfarinized patients.', r.evidence_level = 'Probable', r.pmid = '20849265';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Vidanga') AND toLower(d.generic_name) = toLower('Metronidazole') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-039'}]->(d) SET r.severity = 'Low', r.mechanism = 'Embelin demonstrates complementary anthelmintic and protozoal clearance.', r.evidence_level = 'Possible', r.pmid = '21913867';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Katuki') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-040'}]->(d) SET r.severity = 'Low', r.mechanism = 'Picrosides preserve hepatic glutathione pools against NAPQI oxidative depletion.', r.evidence_level = 'Probable', r.pmid = '1672322';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Ashwagandha') AND toLower(d.generic_name) = toLower('Amitriptyline') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-041'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Sedative withanolides potentiate central antihistaminic and anticholinergic drowsiness of amitriptyline.', r.evidence_level = 'Probable', r.pmid = '25857501';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Ashwagandha') AND toLower(d.generic_name) = toLower('Prednisolone') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-042'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Immune-activating withanolides may counteract immunosuppressive goals of steroid therapy.', r.evidence_level = 'Possible', r.pmid = '20689973';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shatavari') AND toLower(d.generic_name) = toLower('Furosemide') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-043'}]->(d) SET r.severity = 'Low', r.mechanism = 'Mild aquaretic properties of Asparagus saponins complement loop diuretic action.', r.evidence_level = 'Possible', r.pmid = '20888359';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Pippali') AND toLower(d.generic_name) = toLower('Theophylline') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-044'}]->(d) SET r.severity = 'High', r.mechanism = 'Piperine increases oral bioavailability, peak plasma concentration, and AUC of theophylline by >100%.', r.evidence_level = 'Established', r.pmid = '6730707';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Pippali') AND toLower(d.generic_name) = toLower('Rifampin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-045'}]->(d) SET r.severity = 'Low', r.mechanism = 'Piperine facilitates antitubercular bioavailability, documented in standard fixed-dose combinations.', r.evidence_level = 'Established', r.pmid = '11984240';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Haritaki') AND toLower(d.generic_name) = toLower('Glibenclamide') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-046'}]->(d) SET r.severity = 'Moderate', r.mechanism = 'Chebulic acid promotes glucose uptake in peripheral tissues, enhancing hypoglycemic action.', r.evidence_level = 'Probable', r.pmid = '21388523';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Bibhitaki') AND toLower(d.generic_name) = toLower('Atorvastatin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-047'}]->(d) SET r.severity = 'Low', r.mechanism = 'Polyphenols in Terminalia bellirica show complementary hypolipidemic actions.', r.evidence_level = 'Possible', r.pmid = '27088162';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Musta') AND toLower(d.generic_name) = toLower('Omeprazole') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-048'}]->(d) SET r.severity = 'Low', r.mechanism = 'Sesquiterpenes in Cyperus rotundus stimulate gastric mucus secretion without modifying proton pump inhibition.', r.evidence_level = 'Probable', r.pmid = '19429315';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Punarnava Mandura') AND toLower(d.generic_name) = toLower('Ciprofloxacin') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-049'}]->(d) SET r.severity = 'High', r.mechanism = 'Iron content binds ciprofloxacin in GI lumen, halting therapeutic antibacterial action.', r.evidence_level = 'Established', r.pmid = '2168925';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Dhatri Lauha') AND toLower(d.generic_name) = toLower('Doxycycline') MERGE (h)-[r:INTERACTS_WITH {id: 'INT-050'}]->(d) SET r.severity = 'High', r.mechanism = 'Elemental iron complexes with tetracycline nucleus reducing absorption by over 60%.', r.evidence_level = 'Established', r.pmid = '4545089';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Amalaki') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-051'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Amalaki') AND toLower(d.generic_name) = toLower('Amlodipine') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-052'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Amalaki') AND toLower(d.generic_name) = toLower('Metformin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-053'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Amalaki') AND toLower(d.generic_name) = toLower('Cephalexin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-054'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Amalaki') AND toLower(d.generic_name) = toLower('Folic Acid') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-055'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Punarnava') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-056'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Punarnava') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-057'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Punarnava') AND toLower(d.generic_name) = toLower('Domperidone') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-058'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Punarnava') AND toLower(d.generic_name) = toLower('Folic Acid') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-059'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Ashwagandha') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-060'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Ashwagandha') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-061'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Ashwagandha') AND toLower(d.generic_name) = toLower('Cephalexin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-062'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Ashwagandha') AND toLower(d.generic_name) = toLower('Folic Acid') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-063'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Guduchi') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-064'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Guduchi') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-065'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Guduchi') AND toLower(d.generic_name) = toLower('Ranitidine') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-066'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Guduchi') AND toLower(d.generic_name) = toLower('Folic Acid') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-067'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shatavari') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-068'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shatavari') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-069'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shatavari') AND toLower(d.generic_name) = toLower('Omeprazole') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-070'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shatavari') AND toLower(d.generic_name) = toLower('Folic Acid') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-071'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Dadima') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-072'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Dadima') AND toLower(d.generic_name) = toLower('Metformin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-073'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Dadima') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-074'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Draksha') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-075'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Draksha') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-076'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Musta') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-077'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Musta') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-078'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Sariva') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-079'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Sariva') AND toLower(d.generic_name) = toLower('Metformin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-080'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Sariva') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-081'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Bibhitaki') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-082'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Bibhitaki') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-083'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Haritaki') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-084'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Haritaki') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-085'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Vidanga') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-086'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Vidanga') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-087'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shunthi') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-088'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shunthi') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-089'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shunthi') AND toLower(d.generic_name) = toLower('Metformin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-090'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shilajit') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-091'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shilajit') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-092'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Manjistha') AND toLower(d.generic_name) = toLower('Paracetamol') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-093'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Manjistha') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-094'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Draksha') AND toLower(d.generic_name) = toLower('Metformin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-095'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Dadima') AND toLower(d.generic_name) = toLower('Folic Acid') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-096'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Katuki') AND toLower(d.generic_name) = toLower('Amoxicillin') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-097'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Amalaki') AND toLower(d.generic_name) = toLower('Hydroxyzine') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-098'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Punarnava') AND toLower(d.generic_name) = toLower('Hydroxyzine') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-099'}]->(d) SET r.evidence_level = 'Established Safe';

MATCH (h:Herb), (d:Drug) WHERE toLower(h.common_name) = toLower('Shatavari') AND toLower(d.generic_name) = toLower('Hydroxyzine') MERGE (h)-[r:COMPATIBLE_WITH {id: 'INT-100'}]->(d) SET r.evidence_level = 'Established Safe';
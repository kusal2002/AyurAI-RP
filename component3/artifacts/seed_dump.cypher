CREATE CONSTRAINT herb_id_unique IF NOT EXISTS FOR (h:Herb) REQUIRE h.id IS UNIQUE;

CREATE CONSTRAINT drug_id_unique IF NOT EXISTS FOR (d:Drug) REQUIRE d.id IS UNIQUE;

CREATE CONSTRAINT compound_name_unique IF NOT EXISTS FOR (c:Compound) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT enzyme_name_unique IF NOT EXISTS FOR (e:Enzyme) REQUIRE e.name IS UNIQUE;

CREATE CONSTRAINT target_name_unique IF NOT EXISTS FOR (t:Target) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT condition_name_unique IF NOT EXISTS FOR (cond:Condition) REQUIRE cond.name IS UNIQUE;

MERGE (h:Herb {id: 'HERB-001'}) SET h.common_name = 'Punarnava', h.sanskrit_name = 'Punarnava', h.botanical_name = 'Boerhavia diffusa', h.traditional_uses = ['Pandu Roga', 'Shotha (Edema)', 'Diuretic', 'Yakritodara'];

MATCH (h:Herb {id: 'HERB-001'}) MERGE (c:Compound {name: 'Punarnavine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-001'}) MERGE (c:Compound {name: 'Boeravinones'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-001'}) MERGE (c:Compound {name: 'Rotenoids'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-001'}) MERGE (c:Compound {name: 'Liriodendrin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-001'}) MERGE (cond:Condition {name: 'Severe Renal Failure (eGFR < 15 unmonitored)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-001'}) MERGE (cond:Condition {name: 'First trimester pregnancy without guidance'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-002'}) SET h.common_name = 'Amalaki', h.sanskrit_name = 'Amalaki', h.botanical_name = 'Phyllanthus emblica', h.traditional_uses = ['Pandu Roga', 'Rasayana', 'Enhances Iron Absorption', 'Pitta Shamaka'];

MATCH (h:Herb {id: 'HERB-002'}) MERGE (c:Compound {name: 'Ascorbic Acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-002'}) MERGE (c:Compound {name: 'Ellagic Acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-002'}) MERGE (c:Compound {name: 'Gallic Acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-002'}) MERGE (c:Compound {name: 'Emblicanin A & B'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-002'}) MERGE (cond:Condition {name: 'Active hyperacidity flares with bleeding peptic ulcer'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-003'}) SET h.common_name = 'Mandura Bhasma', h.sanskrit_name = 'Mandura Bhasma', h.botanical_name = 'Ferric Oxide Calx (Fe2O3)', h.traditional_uses = ['Pandu Roga', 'Yakritodara (Hepatomegaly)', 'Plihodara (Splenomegaly)'];

MATCH (h:Herb {id: 'HERB-003'}) MERGE (c:Compound {name: 'Ferric Oxide'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-003'}) MERGE (c:Compound {name: 'Ferrous Iron'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-003'}) MERGE (c:Compound {name: 'Trace Minerals'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-003'}) MERGE (cond:Condition {name: 'Hemochromatosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-003'}) MERGE (cond:Condition {name: 'Thalassemia major'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-003'}) MERGE (cond:Condition {name: 'Active Peptic Ulcer'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-003'}) MERGE (cond:Condition {name: 'Severe CKD Stage 4-5'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-004'}) SET h.common_name = 'Ashwagandha', h.sanskrit_name = 'Ashwagandha', h.botanical_name = 'Withania somnifera', h.traditional_uses = ['Balya', 'Daurbalya (Debility)', 'Pandu adjuvant', 'Rasayana'];

MATCH (h:Herb {id: 'HERB-004'}) MERGE (c:Compound {name: 'Withaferin A'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-004'}) MERGE (c:Compound {name: 'Withanolide D'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-004'}) MERGE (c:Compound {name: 'Sitoindosides'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-004'}) MERGE (c:Compound {name: 'Somniferine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-004'}) MERGE (cond:Condition {name: 'Pregnancy (uterine stimulant risk in high doses)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-004'}) MERGE (cond:Condition {name: 'Hyperthyroidism'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-004'}) MERGE (cond:Condition {name: 'Active autoimmune flare'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-005'}) SET h.common_name = 'Yashtimadhu', h.sanskrit_name = 'Yashtimadhu', h.botanical_name = 'Glycyrrhiza glabra', h.traditional_uses = ['Pitta shamaka', 'Raktapitta', 'Rasayana', 'Gastric mucosal protective'];

MATCH (h:Herb {id: 'HERB-005'}) MERGE (c:Compound {name: 'Glycyrrhizin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-005'}) MERGE (c:Compound {name: 'Glabridin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-005'}) MERGE (c:Compound {name: 'Liquiritigenin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-005'}) MERGE (c:Compound {name: 'Isoliquiritigenin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-005'}) MERGE (cond:Condition {name: 'Uncontrolled Hypertension'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-005'}) MERGE (cond:Condition {name: 'Hypokalemia'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-005'}) MERGE (cond:Condition {name: 'Severe CKD Stage 4-5'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-005'}) MERGE (cond:Condition {name: 'Cirrhosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-006'}) SET h.common_name = 'Guduchi', h.sanskrit_name = 'Guduchi', h.botanical_name = 'Tinospora cordifolia', h.traditional_uses = ['Pandu', 'Jwara', 'Deepana', 'Rasayana', 'Rakta Prasadana'];

MATCH (h:Herb {id: 'HERB-006'}) MERGE (c:Compound {name: 'Tinosporaside'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-006'}) MERGE (c:Compound {name: 'Cordifolioside'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-006'}) MERGE (c:Compound {name: 'Berberine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-006'}) MERGE (c:Compound {name: 'Tinosporine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-006'}) MERGE (cond:Condition {name: 'Severe autoimmune hepatitis without monitoring'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-006'}) MERGE (cond:Condition {name: 'Hypoglycemia (additive risk)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-007'}) SET h.common_name = 'Haritaki', h.sanskrit_name = 'Haritaki', h.botanical_name = 'Terminalia chebula', h.traditional_uses = ['Anulomana', 'Pandu', 'Shotha', 'Deepana'];

MATCH (h:Herb {id: 'HERB-007'}) MERGE (c:Compound {name: 'Chebulic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-007'}) MERGE (c:Compound {name: 'Chebulinic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-007'}) MERGE (c:Compound {name: 'Corilagin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-007'}) MERGE (c:Compound {name: 'Tannins'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-007'}) MERGE (cond:Condition {name: 'Severe acute dehydration'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-007'}) MERGE (cond:Condition {name: 'Pregnancy (purgative anthraquinone effect)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-008'}) SET h.common_name = 'Shatavari', h.sanskrit_name = 'Shatavari', h.botanical_name = 'Asparagus racemosus', h.traditional_uses = ['Rasayana', 'Stanya', 'Pitta-Vata Pandu', 'Nutritive tonic'];

MATCH (h:Herb {id: 'HERB-008'}) MERGE (c:Compound {name: 'Shatavarin I-IV'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-008'}) MERGE (c:Compound {name: 'Sarsasapogenin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-008'}) MERGE (c:Compound {name: 'Isoflavones'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-008'}) MERGE (cond:Condition {name: 'Estrogen-sensitive malignancies'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-008'}) MERGE (cond:Condition {name: 'Severe congestive heart failure fluid overload'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-009'}) SET h.common_name = 'Dhatri Lauha', h.sanskrit_name = 'Dhatri Lauha', h.botanical_name = 'Classical Compound (Amalaki + Lauha Bhasma + Yashtimadhu)', h.traditional_uses = ['Pandu Roga Gold Standard', 'Kshaya', 'Pitta Pandu'];

MATCH (h:Herb {id: 'HERB-009'}) MERGE (c:Compound {name: 'Elemental Iron'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-009'}) MERGE (c:Compound {name: 'Ascorbic Acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-009'}) MERGE (c:Compound {name: 'Glycyrrhizin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-009'}) MERGE (c:Compound {name: 'Tannins'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-009'}) MERGE (cond:Condition {name: 'Hemochromatosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-009'}) MERGE (cond:Condition {name: 'Active GI bleeding'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-009'}) MERGE (cond:Condition {name: 'Concurrent oral tetracyclines without 4h gap'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-010'}) SET h.common_name = 'Punarnava Mandura', h.sanskrit_name = 'Punarnavadi Mandura', h.botanical_name = 'Classical Herbo-Mineral Compound', h.traditional_uses = ['Pandu Roga', 'Kaphaja Pandu', 'Shotha', 'Grahani'];

MATCH (h:Herb {id: 'HERB-010'}) MERGE (c:Compound {name: 'Punarnavine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-010'}) MERGE (c:Compound {name: 'Ferric Oxide Calx'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-010'}) MERGE (c:Compound {name: 'Triphala Tannins'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-010'}) MERGE (c:Compound {name: 'Gingerols'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-010'}) MERGE (cond:Condition {name: 'End-stage renal failure (eGFR < 15)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-010'}) MERGE (cond:Condition {name: 'Hemochromatosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-010'}) MERGE (cond:Condition {name: 'Severe peptic ulceration'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-011'}) SET h.common_name = 'Navayasa Lauha', h.sanskrit_name = 'Navayasa Churna / Lauha', h.botanical_name = 'Classical Compound (Trikatu + Triphala + Musta + Vidanga + Chitraka + Lauha Bhasma)', h.traditional_uses = ['Pandu Roga First-line', 'Kamala (Jaundice)', 'Hridroga adjuvant'];

MATCH (h:Herb {id: 'HERB-011'}) MERGE (c:Compound {name: 'Piperine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-011'}) MERGE (c:Compound {name: 'Chebulic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-011'}) MERGE (c:Compound {name: 'Embelin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-011'}) MERGE (c:Compound {name: 'Plumbagin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-011'}) MERGE (c:Compound {name: 'Elemental Iron'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-011'}) MERGE (cond:Condition {name: 'Severe gastritis flare'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-011'}) MERGE (cond:Condition {name: 'Active ulcerative colitis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-011'}) MERGE (cond:Condition {name: 'Pregnancy first trimester'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-012'}) SET h.common_name = 'Arogyavardhini Vati', h.sanskrit_name = 'Arogyavardhini Vati', h.botanical_name = 'Classical Herbo-Mineral Mineral Compound', h.traditional_uses = ['Pandu with Hepatic Involvement', 'Kamala', 'Yakrit Vikara', 'Deepana-Pachana'];

MATCH (h:Herb {id: 'HERB-012'}) MERGE (c:Compound {name: 'Picroside I & II'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-012'}) MERGE (c:Compound {name: 'Guggulsterones'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-012'}) MERGE (c:Compound {name: 'Azadirachtin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-012'}) MERGE (c:Compound {name: 'Purified Mercury & Sulphur Calx'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-012'}) MERGE (c:Compound {name: 'Lauha Bhasma'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-012'}) MERGE (cond:Condition {name: 'Pregnancy and lactation'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-012'}) MERGE (cond:Condition {name: 'Severe renal impairment (eGFR < 30)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-012'}) MERGE (cond:Condition {name: 'Pediatric use < 12 years'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-013'}) SET h.common_name = 'Chandraprabha Vati', h.sanskrit_name = 'Chandraprabha Vati', h.botanical_name = 'Classical Herbo-Mineral Polyherbal', h.traditional_uses = ['Pandu with urinary debility', 'Prameha', 'Daurbalya', 'Rasayana'];

MATCH (h:Herb {id: 'HERB-013'}) MERGE (c:Compound {name: 'Fulvic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-013'}) MERGE (c:Compound {name: 'Guggulsterones'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-013'}) MERGE (c:Compound {name: 'Berberine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-013'}) MERGE (c:Compound {name: 'Piperine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-013'}) MERGE (c:Compound {name: 'Iron Calx'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-013'}) MERGE (cond:Condition {name: 'Bleeding diathesis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-013'}) MERGE (cond:Condition {name: 'Severe hyperacidity flare'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-014'}) SET h.common_name = 'Lohasava', h.sanskrit_name = 'Lohasava', h.botanical_name = 'Fermented Iron Calx Arishta', h.traditional_uses = ['Pandu Roga', 'Shotha', 'Jataragni Mandya', 'Gulma'];

MATCH (h:Herb {id: 'HERB-014'}) MERGE (c:Compound {name: 'Bioavailable Ferrous Citrate'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-014'}) MERGE (c:Compound {name: 'Piperine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-014'}) MERGE (c:Compound {name: 'Triphala Tannins'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-014'}) MERGE (c:Compound {name: 'Self-generated Alcohol (5-10%)'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-014'}) MERGE (cond:Condition {name: 'Gastric ulcer perforation risk'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-014'}) MERGE (cond:Condition {name: 'Alcohol dependence'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-014'}) MERGE (cond:Condition {name: 'Active hyperacidity'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-015'}) SET h.common_name = 'Drakshasava', h.sanskrit_name = 'Drakshasava', h.botanical_name = 'Fermented Raisin Formulation', h.traditional_uses = ['Pandu debility', 'Daurbalya', 'Kshaya', 'Raktapitta'];

MATCH (h:Herb {id: 'HERB-015'}) MERGE (c:Compound {name: 'Resveratrol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-015'}) MERGE (c:Compound {name: 'Tartaric acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-015'}) MERGE (c:Compound {name: 'Polyphenols'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-015'}) MERGE (c:Compound {name: 'Piperine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-015'}) MERGE (cond:Condition {name: 'Uncontrolled Diabetes Mellitus (high glycemic load)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-015'}) MERGE (cond:Condition {name: 'Alcohol aversion'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-016'}) SET h.common_name = 'Kasisa Bhasma', h.sanskrit_name = 'Kasisa Bhasma', h.botanical_name = 'Incinerated Green Vitriol (FeSO4 . 7H2O)', h.traditional_uses = ['Pandu Roga', 'Kasa', 'Shwasa', 'Artavajanana'];

MATCH (h:Herb {id: 'HERB-016'}) MERGE (c:Compound {name: 'Ferrous Sulphate'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-016'}) MERGE (c:Compound {name: 'Iron Oxide'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-016'}) MERGE (c:Compound {name: 'Trace Sulphur'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-016'}) MERGE (cond:Condition {name: 'Iron storage diseases'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-016'}) MERGE (cond:Condition {name: 'Severe non-iron deficiency hemolytic anemia'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-017'}) SET h.common_name = 'Swarna Makshika Bhasma', h.sanskrit_name = 'Swarna Makshika Bhasma', h.botanical_name = 'Incinerated Chalcopyrite (CuFeS2)', h.traditional_uses = ['Pandu Roga', 'Anidra', 'Hridroga', 'Rasayana'];

MATCH (h:Herb {id: 'HERB-017'}) MERGE (c:Compound {name: 'Copper-Iron Sulphide Calx'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-017'}) MERGE (c:Compound {name: 'Trace Gold'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-017'}) MERGE (c:Compound {name: 'Micro-elements'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-017'}) MERGE (cond:Condition {name: 'Wilson\'s disease'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-017'}) MERGE (cond:Condition {name: 'Advanced hepatic cirrhosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-017'}) MERGE (cond:Condition {name: 'Hemochromatosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-018'}) SET h.common_name = 'Loha Bhasma', h.sanskrit_name = 'Lauha Bhasma (100 Puti)', h.botanical_name = 'Incinerated Elemental Iron Calx', h.traditional_uses = ['Classical Pandu treatment', 'Rakta Dhatu Vardhana', 'Ayusya', 'Vaya Sthapana'];

MATCH (h:Herb {id: 'HERB-018'}) MERGE (c:Compound {name: 'Microfine Elemental Fe (Fe2O3/Fe3O4)'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-018'}) MERGE (c:Compound {name: 'Magnetic nano-particles'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-018'}) MERGE (cond:Condition {name: 'Hemolytic anemia without iron deficiency'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-018'}) MERGE (cond:Condition {name: 'Hemochromatosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-018'}) MERGE (cond:Condition {name: 'Severe ulcerative lesions'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-019'}) SET h.common_name = 'Dadima', h.sanskrit_name = 'Dadima', h.botanical_name = 'Punica granatum', h.traditional_uses = ['Pandu Roga Diet', 'Raktapitta', 'Hridya', 'Rochana', 'Deepana'];

MATCH (h:Herb {id: 'HERB-019'}) MERGE (c:Compound {name: 'Punicalagin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-019'}) MERGE (c:Compound {name: 'Ellagic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-019'}) MERGE (c:Compound {name: 'Anthocyanins'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-019'}) MERGE (c:Compound {name: 'Punicic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-019'}) MERGE (cond:Condition {name: 'Hypotension when combined with high-dose ACE inhibitors (additive)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-020'}) SET h.common_name = 'Draksha', h.sanskrit_name = 'Draksha', h.botanical_name = 'Vitis vinifera', h.traditional_uses = ['Pandu nutritional support', 'Daurbalya', 'Vata-Pitta Shamana', 'Virechana mridu'];

MATCH (h:Herb {id: 'HERB-020'}) MERGE (c:Compound {name: 'Resveratrol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-020'}) MERGE (c:Compound {name: 'Proanthocyanidins'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-020'}) MERGE (c:Compound {name: 'Flavonoids'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-020'}) MERGE (c:Compound {name: 'Iron minerals'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-020'}) MERGE (cond:Condition {name: 'Diabetic gastroparesis in acute state'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-020'}) MERGE (cond:Condition {name: 'Unchecked hyperglycemia in high doses'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-021'}) SET h.common_name = 'Bibhitaki', h.sanskrit_name = 'Bibhitaki', h.botanical_name = 'Terminalia bellirica', h.traditional_uses = ['Triphala constituent in Pandu', 'Kaphaja Pandu', 'Rakta Shodhaka'];

MATCH (h:Herb {id: 'HERB-021'}) MERGE (c:Compound {name: 'Bellericanin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-021'}) MERGE (c:Compound {name: 'Gallic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-021'}) MERGE (c:Compound {name: 'Ellagic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-021'}) MERGE (c:Compound {name: 'Beta-sitosterol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-021'}) MERGE (cond:Condition {name: 'Severe dry cough with mucosal erosion'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-021'}) MERGE (cond:Condition {name: 'Marked emaciation'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-022'}) SET h.common_name = 'Musta', h.sanskrit_name = 'Musta', h.botanical_name = 'Cyperus rotundus', h.traditional_uses = ['Amapachana in Pandu', 'Grahani', 'Yakritottejaka', 'Jwara'];

MATCH (h:Herb {id: 'HERB-022'}) MERGE (c:Compound {name: 'Cyperene'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-022'}) MERGE (c:Compound {name: 'Cyperotundone'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-022'}) MERGE (c:Compound {name: 'Patchoulenone'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-022'}) MERGE (c:Compound {name: 'Rotundene'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-022'}) MERGE (cond:Condition {name: 'Severe chronic constipation (Grahi action)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-023'}) SET h.common_name = 'Vidanga', h.sanskrit_name = 'Vidanga', h.botanical_name = 'Embelia ribes', h.traditional_uses = ['Krimija Pandu (Helminth-induced anemia)', 'Deepana', 'Anulomana'];

MATCH (h:Herb {id: 'HERB-023'}) MERGE (c:Compound {name: 'Embelin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-023'}) MERGE (c:Compound {name: 'Homoembelin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-023'}) MERGE (c:Compound {name: 'Vilangin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-023'}) MERGE (c:Compound {name: 'Quercitol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-023'}) MERGE (cond:Condition {name: 'Contraceptive desire / fertility therapy (antifertility activity documented)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-023'}) MERGE (cond:Condition {name: 'Pregnancy'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-024'}) SET h.common_name = 'Shunthi', h.sanskrit_name = 'Shunthi', h.botanical_name = 'Zingiber officinale', h.traditional_uses = ['Agnideepana', 'Bioavailability enhancer for iron bhasmas', 'Amadoshahara'];

MATCH (h:Herb {id: 'HERB-024'}) MERGE (c:Compound {name: '6-Gingerol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-024'}) MERGE (c:Compound {name: '6-Shogaol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-024'}) MERGE (c:Compound {name: 'Zingiberene'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-024'}) MERGE (c:Compound {name: 'Paradol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-024'}) MERGE (cond:Condition {name: 'Active bleeding peptic ulcer'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-024'}) MERGE (cond:Condition {name: 'Concomitant high-dose anticoagulant therapy (monitor)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-025'}) SET h.common_name = 'Pippali', h.sanskrit_name = 'Pippali', h.botanical_name = 'Piper longum', h.traditional_uses = ['Yogavahi (Bioenhancer for iron absorption)', 'Plihodara', 'Deepana'];

MATCH (h:Herb {id: 'HERB-025'}) MERGE (c:Compound {name: 'Piperine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-025'}) MERGE (c:Compound {name: 'Piperlongumine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-025'}) MERGE (c:Compound {name: 'Piperlonguminine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-025'}) MERGE (c:Compound {name: 'Pipernonaline'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-025'}) MERGE (cond:Condition {name: 'Acute gastritis with ulceration'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-025'}) MERGE (cond:Condition {name: 'Pitta prakopa state without cooling Anupana'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-026'}) SET h.common_name = 'Maricha', h.sanskrit_name = 'Maricha', h.botanical_name = 'Piper nigrum', h.traditional_uses = ['Trikatu component', 'Pramathi (Channel-clearing for Dhatu nourishment)', 'Deepana'];

MATCH (h:Herb {id: 'HERB-026'}) MERGE (c:Compound {name: 'Piperine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-026'}) MERGE (c:Compound {name: 'Chavicine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-026'}) MERGE (c:Compound {name: 'Piperidine'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-026'}) MERGE (c:Compound {name: 'Caryophyllene'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-026'}) MERGE (cond:Condition {name: 'Active peptic ulceration'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-026'}) MERGE (cond:Condition {name: 'Severe esophageal reflux'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-027'}) SET h.common_name = 'Shilajit', h.sanskrit_name = 'Shuddha Shilajit', h.botanical_name = 'Asphaltum punjabianum', h.traditional_uses = ['Rasayana', 'Kshaya', 'Pandu adjuvant', 'Dhatu Poshaka'];

MATCH (h:Herb {id: 'HERB-027'}) MERGE (c:Compound {name: 'Fulvic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-027'}) MERGE (c:Compound {name: 'Humic acid'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-027'}) MERGE (c:Compound {name: 'Dibenzo-alpha-pyrones'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-027'}) MERGE (c:Compound {name: 'Micro-trace elements'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-027'}) MERGE (cond:Condition {name: 'Hyperuricemia / active gouty arthritis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-027'}) MERGE (cond:Condition {name: 'Hemochromatosis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-027'}) MERGE (cond:Condition {name: 'Severe cardiac failure'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-028'}) SET h.common_name = 'Katuki', h.sanskrit_name = 'Katuki', h.botanical_name = 'Picrorhiza kurroa', h.traditional_uses = ['Yakritodara in Pandu', 'Kamala', 'Bile secretagogue', 'Pitta Rechana'];

MATCH (h:Herb {id: 'HERB-028'}) MERGE (c:Compound {name: 'Picroside I'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-028'}) MERGE (c:Compound {name: 'Picroside II'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-028'}) MERGE (c:Compound {name: 'Kutkoside'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-028'}) MERGE (c:Compound {name: 'Apocynin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-028'}) MERGE (cond:Condition {name: 'Severe non-infectious chronic diarrhea'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-028'}) MERGE (cond:Condition {name: 'Hypotension with cardiac glycosides'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-029'}) SET h.common_name = 'Manjistha', h.sanskrit_name = 'Manjistha', h.botanical_name = 'Rubia cordifolia', h.traditional_uses = ['Raktashodhaka', 'Pandu Raktapitta', 'Varnya', 'Rasayana'];

MATCH (h:Herb {id: 'HERB-029'}) MERGE (c:Compound {name: 'Purpurin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-029'}) MERGE (c:Compound {name: 'Munjistin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-029'}) MERGE (c:Compound {name: 'Alizarin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-029'}) MERGE (c:Compound {name: 'Rubiadin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-029'}) MERGE (cond:Condition {name: 'Pregnancy (mild emmenagogue)'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MATCH (h:Herb {id: 'HERB-029'}) MERGE (cond:Condition {name: 'Severe acute nephrolithiasis'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (h:Herb {id: 'HERB-030'}) SET h.common_name = 'Sariva', h.sanskrit_name = 'Shveta Sariva', h.botanical_name = 'Hemidesmus indicus', h.traditional_uses = ['Pitta Pandu', 'Daha Prashamana', 'Rakta Prasadana', 'Deepana'];

MATCH (h:Herb {id: 'HERB-030'}) MERGE (c:Compound {name: '2-Hydroxy-4-methoxybenzaldehyde'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-030'}) MERGE (c:Compound {name: 'Lupeol'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-030'}) MERGE (c:Compound {name: 'Hemidesmin'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-030'}) MERGE (c:Compound {name: 'Resin acids'}) MERGE (h)-[:CONTAINS_COMPOUND]->(c);

MATCH (h:Herb {id: 'HERB-030'}) MERGE (cond:Condition {name: 'None prominent at therapeutic doses; caution in marked bradycardia'}) MERGE (h)-[:CONTRAINDICATED_IN]->(cond);

MERGE (e:Enzyme {name: 'CYP3A4'}) SET e.description = 'Major drug-metabolizing cytochrome P450 enzyme responsible for oxidation of >50% of marketed pharmaceuticals.';

MERGE (c:Compound {name: 'Glabridin'}) WITH c MATCH (e:Enzyme {name: 'CYP3A4'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Curcumin'}) WITH c MATCH (e:Enzyme {name: 'CYP3A4'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Picroside II'}) WITH c MATCH (e:Enzyme {name: 'CYP3A4'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Carbamazepine'}) WITH c MATCH (e:Enzyme {name: 'CYP3A4'}) MERGE (c)-[:INDUCES]->(e);

MERGE (c:Compound {name: 'Withaferin A'}) WITH c MATCH (e:Enzyme {name: 'CYP3A4'}) MERGE (c)-[:INDUCES]->(e);

MERGE (e:Enzyme {name: 'CYP2C9'}) SET e.description = 'Key enzyme for narrow-therapeutic-index drugs including S-warfarin, NSAIDs, and Losartan bioactivation.';

MERGE (c:Compound {name: 'Glabridin'}) WITH c MATCH (e:Enzyme {name: 'CYP2C9'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Withaferin A'}) WITH c MATCH (e:Enzyme {name: 'CYP2C9'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Purpurin'}) WITH c MATCH (e:Enzyme {name: 'CYP2C9'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Phenytoin'}) WITH c MATCH (e:Enzyme {name: 'CYP2C9'}) MERGE (c)-[:INDUCES]->(e);

MERGE (c:Compound {name: 'Carbamazepine'}) WITH c MATCH (e:Enzyme {name: 'CYP2C9'}) MERGE (c)-[:INDUCES]->(e);

MERGE (c:Compound {name: 'Rifampin'}) WITH c MATCH (e:Enzyme {name: 'CYP2C9'}) MERGE (c)-[:INDUCES]->(e);

MERGE (e:Enzyme {name: 'CYP2C19'}) SET e.description = 'Critical for metabolism of proton pump inhibitors, antiepileptics, and bioactivation of clopidogrel.';

MERGE (c:Compound {name: 'Tinosporaside'}) WITH c MATCH (e:Enzyme {name: 'CYP2C19'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Chebulinic acid'}) WITH c MATCH (e:Enzyme {name: 'CYP2C19'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Carbamazepine'}) WITH c MATCH (e:Enzyme {name: 'CYP2C19'}) MERGE (c)-[:INDUCES]->(e);

MERGE (c:Compound {name: 'Rifampin'}) WITH c MATCH (e:Enzyme {name: 'CYP2C19'}) MERGE (c)-[:INDUCES]->(e);

MERGE (e:Enzyme {name: 'CYP2D6'}) SET e.description = 'Responsible for metabolism of cardiovascular beta-blockers, antiarrhythmics, SSRIs, and tricyclic antidepressants.';

MERGE (c:Compound {name: 'Berberine'}) WITH c MATCH (e:Enzyme {name: 'CYP2D6'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Piperine'}) WITH c MATCH (e:Enzyme {name: 'CYP2D6'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Dexamethasone'}) WITH c MATCH (e:Enzyme {name: 'CYP2D6'}) MERGE (c)-[:INDUCES]->(e);

MERGE (e:Enzyme {name: 'CYP1A2'}) SET e.description = 'Metabolizes methylxanthines, theophylline, and certain atypical antipsychotics; inhibited by fluoroquinolones.';

MERGE (c:Compound {name: 'Ciprofloxacin'}) WITH c MATCH (e:Enzyme {name: 'CYP1A2'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Ellagic acid'}) WITH c MATCH (e:Enzyme {name: 'CYP1A2'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Curcumin'}) WITH c MATCH (e:Enzyme {name: 'CYP1A2'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Tobacco smoke'}) WITH c MATCH (e:Enzyme {name: 'CYP1A2'}) MERGE (c)-[:INDUCES]->(e);

MERGE (c:Compound {name: 'Charbroiled foods'}) WITH c MATCH (e:Enzyme {name: 'CYP1A2'}) MERGE (c)-[:INDUCES]->(e);

MERGE (c:Compound {name: 'Cruciferous vegetables'}) WITH c MATCH (e:Enzyme {name: 'CYP1A2'}) MERGE (c)-[:INDUCES]->(e);

MERGE (e:Enzyme {name: 'CYP2B6'}) SET e.description = 'Involved in the clearance of antineoplastics, bupropion, and certain antiretrovirals and psychotropics.';

MERGE (c:Compound {name: 'Triterpenoids in Boswellia / Guggulu'}) WITH c MATCH (e:Enzyme {name: 'CYP2B6'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Phenobarbital'}) WITH c MATCH (e:Enzyme {name: 'CYP2B6'}) MERGE (c)-[:INDUCES]->(e);

MERGE (c:Compound {name: 'Carbamazepine'}) WITH c MATCH (e:Enzyme {name: 'CYP2B6'}) MERGE (c)-[:INDUCES]->(e);

MERGE (e:Enzyme {name: 'CYP2C8'}) SET e.description = 'Metabolizes thiazolidinediones, paclitaxel, repaglinide, and certain statins.';

MERGE (c:Compound {name: 'Gemfibrozil'}) WITH c MATCH (e:Enzyme {name: 'CYP2C8'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Quercetin'}) WITH c MATCH (e:Enzyme {name: 'CYP2C8'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Rifampin'}) WITH c MATCH (e:Enzyme {name: 'CYP2C8'}) MERGE (c)-[:INDUCES]->(e);

MERGE (c:Compound {name: 'Carbamazepine'}) WITH c MATCH (e:Enzyme {name: 'CYP2C8'}) MERGE (c)-[:INDUCES]->(e);

MERGE (e:Enzyme {name: 'CYP2E1'}) SET e.description = 'Metabolizes small hydrophobic and halogenated compounds including paracetamol and ethanol.';

MERGE (c:Compound {name: 'Diallyl sulfide'}) WITH c MATCH (e:Enzyme {name: 'CYP2E1'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Watercress'}) WITH c MATCH (e:Enzyme {name: 'CYP2E1'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Chronic ethanol ingestion'}) WITH c MATCH (e:Enzyme {name: 'CYP2E1'}) MERGE (c)-[:INDUCES]->(e);

MERGE (c:Compound {name: 'Isoniazid'}) WITH c MATCH (e:Enzyme {name: 'CYP2E1'}) MERGE (c)-[:INDUCES]->(e);

MERGE (c:Compound {name: 'Uncontrolled diabetes'}) WITH c MATCH (e:Enzyme {name: 'CYP2E1'}) MERGE (c)-[:INDUCES]->(e);

MERGE (e:Enzyme {name: 'P-glycoprotein (ABCB1)'}) SET e.description = 'ATP-dependent intestinal and blood-brain-barrier efflux transporter controlling drug bioavailability.';

MERGE (c:Compound {name: 'Piperine'}) WITH c MATCH (e:Enzyme {name: 'P-glycoprotein (ABCB1)'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Curcumin'}) WITH c MATCH (e:Enzyme {name: 'P-glycoprotein (ABCB1)'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Withaferin A'}) WITH c MATCH (e:Enzyme {name: 'P-glycoprotein (ABCB1)'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Rifampin'}) WITH c MATCH (e:Enzyme {name: 'P-glycoprotein (ABCB1)'}) MERGE (c)-[:INDUCES]->(e);

MERGE (c:Compound {name: 'St John\'s Wort'}) WITH c MATCH (e:Enzyme {name: 'P-glycoprotein (ABCB1)'}) MERGE (c)-[:INDUCES]->(e);

MERGE (e:Enzyme {name: 'OAT1/OAT3 (SLC22A6/SLC22A8)'}) SET e.description = 'Renal proximal tubule basolateral uptake transporters responsible for active tubular secretion of organic anions.';

MERGE (c:Compound {name: 'Punarnavine'}) WITH c MATCH (e:Enzyme {name: 'OAT1/OAT3 (SLC22A6/SLC22A8)'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'Probenecid'}) WITH c MATCH (e:Enzyme {name: 'OAT1/OAT3 (SLC22A6/SLC22A8)'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (c:Compound {name: 'NSAIDs'}) WITH c MATCH (e:Enzyme {name: 'OAT1/OAT3 (SLC22A6/SLC22A8)'}) MERGE (c)-[:INHIBITS]->(e);

MERGE (d:Drug {id: 'DRUG-001'}) SET d.generic_name = 'Metformin', d.drug_class = 'Biguanide Antidiabetic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-001'}) MERGE (e:Enzyme {name: 'OCT1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-001'}) MERGE (e:Enzyme {name: 'OCT2'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-001'}) MERGE (e:Enzyme {name: 'MATE1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-001'}) MERGE (t:Target {name: 'AMPK'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-002'}) SET d.generic_name = 'Omeprazole', d.drug_class = 'Proton Pump Inhibitor (PPI)', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-002'}) MERGE (e:Enzyme {name: 'CYP2C19'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-002'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-002'}) MERGE (t:Target {name: 'H+/K+ ATPase'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-003'}) SET d.generic_name = 'Atorvastatin', d.drug_class = 'HMG-CoA Reductase Inhibitor', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-003'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-003'}) MERGE (t:Target {name: 'HMG-CoA Reductase'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-004'}) SET d.generic_name = 'Losartan', d.drug_class = 'Angiotensin II Receptor Blocker (ARB)', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-004'}) MERGE (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-004'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-004'}) MERGE (t:Target {name: 'AT1 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-005'}) SET d.generic_name = 'Amlodipine', d.drug_class = 'Dihydropyridine Calcium Channel Blocker', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-005'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-005'}) MERGE (t:Target {name: 'L-type Calcium Channels'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-006'}) SET d.generic_name = 'Ferrous Sulfate', d.drug_class = 'Oral Hematinic / Iron Supplement', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-006'}) MERGE (t:Target {name: 'DMT1'}) MERGE (d)-[:ACTS_ON]->(t);

MATCH (d:Drug {id: 'DRUG-006'}) MERGE (t:Target {name: 'Transferrin'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-007'}) SET d.generic_name = 'Levothyroxine', d.drug_class = 'Synthetic Thyroid Hormone', d.narrow_therapeutic_index = true;

MATCH (d:Drug {id: 'DRUG-007'}) MERGE (e:Enzyme {name: 'Deiodinase'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-007'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-007'}) MERGE (e:Enzyme {name: 'UGT1A1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-007'}) MERGE (t:Target {name: 'Thyroid Hormone Receptors TR-alpha/beta'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-008'}) SET d.generic_name = 'Clonazepam', d.drug_class = 'Benzodiazepine Anticonvulsant / Anxiolytic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-008'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-008'}) MERGE (t:Target {name: 'GABA-A Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-009'}) SET d.generic_name = 'Warfarin', d.drug_class = 'Vitamin K Antagonist Anticoagulant', d.narrow_therapeutic_index = true;

MATCH (d:Drug {id: 'DRUG-009'}) MERGE (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-009'}) MERGE (e:Enzyme {name: 'CYP1A2'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-009'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-009'}) MERGE (t:Target {name: 'VKORC1'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-010'}) SET d.generic_name = 'Aspirin', d.drug_class = 'Antiplatelet / NSAID', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-010'}) MERGE (e:Enzyme {name: 'Esterases'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-010'}) MERGE (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-010'}) MERGE (t:Target {name: 'COX-1'}) MERGE (d)-[:ACTS_ON]->(t);

MATCH (d:Drug {id: 'DRUG-010'}) MERGE (t:Target {name: 'COX-2'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-011'}) SET d.generic_name = 'Enalapril', d.drug_class = 'ACE Inhibitor Antihypertensive', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-011'}) MERGE (e:Enzyme {name: 'Hepatic Carboxylesterase-1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-011'}) MERGE (t:Target {name: 'Angiotensin-Converting Enzyme'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-012'}) SET d.generic_name = 'Ramipril', d.drug_class = 'ACE Inhibitor Antihypertensive', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-012'}) MERGE (e:Enzyme {name: 'Hepatic Esterases'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-012'}) MERGE (t:Target {name: 'Angiotensin-Converting Enzyme'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-013'}) SET d.generic_name = 'Atenolol', d.drug_class = 'Beta-1 Selective Adrenergic Blocker', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-013'}) MERGE (e:Enzyme {name: 'Minimal hepatic (Renal excretion 85%)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-013'}) MERGE (t:Target {name: 'Beta-1 Adrenergic Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-014'}) SET d.generic_name = 'Bisoprolol', d.drug_class = 'Beta-1 Selective Adrenergic Blocker', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-014'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-014'}) MERGE (e:Enzyme {name: 'CYP2D6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-014'}) MERGE (t:Target {name: 'Beta-1 Adrenergic Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-015'}) SET d.generic_name = 'Hydrochlorothiazide', d.drug_class = 'Thiazide Diuretic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-015'}) MERGE (e:Enzyme {name: 'Renal elimination unchanged'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-015'}) MERGE (t:Target {name: 'Na+/Cl- Cotransporter NCCT'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-016'}) SET d.generic_name = 'Furosemide', d.drug_class = 'Loop Diuretic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-016'}) MERGE (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-016'}) MERGE (e:Enzyme {name: 'Glucuronidation'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-016'}) MERGE (t:Target {name: 'Na+/K+/2Cl- Cotransporter NKCC2'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-017'}) SET d.generic_name = 'Spironolactone', d.drug_class = 'Potassium-Sparing Aldosterone Antagonist', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-017'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-017'}) MERGE (t:Target {name: 'Mineralocorticoid Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-018'}) SET d.generic_name = 'Digoxin', d.drug_class = 'Cardiac Glycoside Inotrope', d.narrow_therapeutic_index = true;

MATCH (d:Drug {id: 'DRUG-018'}) MERGE (e:Enzyme {name: 'P-gp / ABCB1 Substrate'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-018'}) MERGE (t:Target {name: 'Na+/K+ ATPase'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-019'}) SET d.generic_name = 'Glibenclamide', d.drug_class = 'Sulfonylurea Antidiabetic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-019'}) MERGE (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-019'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-019'}) MERGE (t:Target {name: 'SUR1 / Kir6.2 channel'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-020'}) SET d.generic_name = 'Gliclazide', d.drug_class = 'Second-Generation Sulfonylurea', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-020'}) MERGE (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-020'}) MERGE (e:Enzyme {name: 'CYP2C19'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-020'}) MERGE (t:Target {name: 'SUR1 Pancreatic Beta Cell Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-021'}) SET d.generic_name = 'Sitagliptin', d.drug_class = 'DPP-4 Inhibitor Antidiabetic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-021'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-021'}) MERGE (e:Enzyme {name: 'CYP2C8'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-021'}) MERGE (t:Target {name: 'Dipeptidyl Peptidase-4'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-022'}) SET d.generic_name = 'Empagliflozin', d.drug_class = 'SGLT-2 Inhibitor', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-022'}) MERGE (e:Enzyme {name: 'UGT2B7'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-022'}) MERGE (e:Enzyme {name: 'UGT1A3'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-022'}) MERGE (e:Enzyme {name: 'UGT1A8'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-022'}) MERGE (t:Target {name: 'Sodium-Glucose Cotransporter 2'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-023'}) SET d.generic_name = 'Pantoprazole', d.drug_class = 'Proton Pump Inhibitor', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-023'}) MERGE (e:Enzyme {name: 'CYP2C19'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-023'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-023'}) MERGE (t:Target {name: 'H+/K+ ATPase'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-024'}) SET d.generic_name = 'Ranitidine', d.drug_class = 'H2 Receptor Antagonist', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-024'}) MERGE (e:Enzyme {name: 'CYP1A2'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-024'}) MERGE (e:Enzyme {name: 'CYP2D6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-024'}) MERGE (t:Target {name: 'Histamine H2 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-025'}) SET d.generic_name = 'Ciprofloxacin', d.drug_class = 'Fluoroquinolone Antibiotic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-025'}) MERGE (e:Enzyme {name: 'CYP1A2 (Strong Inhibitor)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-025'}) MERGE (t:Target {name: 'Bacterial DNA Gyrase'}) MERGE (d)-[:ACTS_ON]->(t);

MATCH (d:Drug {id: 'DRUG-025'}) MERGE (t:Target {name: 'Topoisomerase IV'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-026'}) SET d.generic_name = 'Doxycycline', d.drug_class = 'Tetracycline Antibiotic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-026'}) MERGE (e:Enzyme {name: 'Non-enzymatic Chelation'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-026'}) MERGE (t:Target {name: 'Bacterial 30S Ribosome Subunit'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-027'}) SET d.generic_name = 'Amoxicillin', d.drug_class = 'Aminopenicillin Antibiotic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-027'}) MERGE (e:Enzyme {name: 'Renal excretion unchanged'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-027'}) MERGE (t:Target {name: 'Penicillin-Binding Proteins (PBPs)'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-028'}) SET d.generic_name = 'Azithromycin', d.drug_class = 'Macrolide Antibiotic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-028'}) MERGE (e:Enzyme {name: 'CYP3A4 (Weak)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-028'}) MERGE (e:Enzyme {name: 'Biliary excretion'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-028'}) MERGE (t:Target {name: 'Bacterial 50S Ribosome Subunit'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-029'}) SET d.generic_name = 'Ibuprofen', d.drug_class = 'NSAID Non-selective', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-029'}) MERGE (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-029'}) MERGE (e:Enzyme {name: 'CYP2C8'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-029'}) MERGE (t:Target {name: 'COX-1'}) MERGE (d)-[:ACTS_ON]->(t);

MATCH (d:Drug {id: 'DRUG-029'}) MERGE (t:Target {name: 'COX-2'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-030'}) SET d.generic_name = 'Diclofenac', d.drug_class = 'Acetic Acid Derivative NSAID', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-030'}) MERGE (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-030'}) MERGE (e:Enzyme {name: 'UGT2B7'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-030'}) MERGE (t:Target {name: 'COX-1'}) MERGE (d)-[:ACTS_ON]->(t);

MATCH (d:Drug {id: 'DRUG-030'}) MERGE (t:Target {name: 'COX-2'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-031'}) SET d.generic_name = 'Paracetamol', d.drug_class = 'Aniline Analgesic / Antipyretic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-031'}) MERGE (e:Enzyme {name: 'CYP2E1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-031'}) MERGE (e:Enzyme {name: 'UGT1A6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-031'}) MERGE (e:Enzyme {name: 'SULT1A1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-031'}) MERGE (t:Target {name: 'Central TRPA1'}) MERGE (d)-[:ACTS_ON]->(t);

MATCH (d:Drug {id: 'DRUG-031'}) MERGE (t:Target {name: 'COX-3 putative'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-032'}) SET d.generic_name = 'Tramadol', d.drug_class = 'Opioid Analgesic / SNRI', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-032'}) MERGE (e:Enzyme {name: 'CYP2D6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-032'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-032'}) MERGE (t:Target {name: 'Mu-opioid receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MATCH (d:Drug {id: 'DRUG-032'}) MERGE (t:Target {name: 'Serotonin/Norepinephrine transporter'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-033'}) SET d.generic_name = 'Sertraline', d.drug_class = 'Selective Serotonin Reuptake Inhibitor (SSRI)', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-033'}) MERGE (e:Enzyme {name: 'CYP2B6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-033'}) MERGE (e:Enzyme {name: 'CYP2C19'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-033'}) MERGE (e:Enzyme {name: 'CYP2D6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-033'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-033'}) MERGE (t:Target {name: 'Serotonin Transporter (SERT)'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-034'}) SET d.generic_name = 'Fluoxetine', d.drug_class = 'Selective Serotonin Reuptake Inhibitor (SSRI)', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-034'}) MERGE (e:Enzyme {name: 'CYP2D6 (Potent Inhibitor)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-034'}) MERGE (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-034'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-034'}) MERGE (t:Target {name: 'Serotonin Transporter (SERT)'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-035'}) SET d.generic_name = 'Amitriptyline', d.drug_class = 'Tricyclic Antidepressant (TCA)', d.narrow_therapeutic_index = true;

MATCH (d:Drug {id: 'DRUG-035'}) MERGE (e:Enzyme {name: 'CYP2D6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-035'}) MERGE (e:Enzyme {name: 'CYP2C19'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-035'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-035'}) MERGE (t:Target {name: '5-HT/NE Reuptake'}) MERGE (d)-[:ACTS_ON]->(t);

MATCH (d:Drug {id: 'DRUG-035'}) MERGE (t:Target {name: 'H1 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MATCH (d:Drug {id: 'DRUG-035'}) MERGE (t:Target {name: 'M1 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-036'}) SET d.generic_name = 'Gabapentin', d.drug_class = 'Gabapentinoid Anticonvulsant', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-036'}) MERGE (e:Enzyme {name: 'Renal elimination (LAT1 transporter)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-036'}) MERGE (t:Target {name: 'Alpha-2-delta Voltage-Gated Calcium Channels'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-037'}) SET d.generic_name = 'Carbamazepine', d.drug_class = 'Iminostilbene Anticonvulsant', d.narrow_therapeutic_index = true;

MATCH (d:Drug {id: 'DRUG-037'}) MERGE (e:Enzyme {name: 'CYP3A4 (Potent Auto-Inducer)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-037'}) MERGE (e:Enzyme {name: 'CYP2C8'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-037'}) MERGE (t:Target {name: 'Voltage-Gated Sodium Channels'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-038'}) SET d.generic_name = 'Phenytoin', d.drug_class = 'Hydantoin Anticonvulsant', d.narrow_therapeutic_index = true;

MATCH (d:Drug {id: 'DRUG-038'}) MERGE (e:Enzyme {name: 'CYP2C9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-038'}) MERGE (e:Enzyme {name: 'CYP2C19 (Potent Inducer)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-038'}) MERGE (t:Target {name: 'Voltage-Gated Sodium Channels'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-039'}) SET d.generic_name = 'Prednisolone', d.drug_class = 'Systemic Corticosteroid', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-039'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-039'}) MERGE (e:Enzyme {name: '11-beta-HSD1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-039'}) MERGE (t:Target {name: 'Glucocorticoid Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-040'}) SET d.generic_name = 'Methotrexate', d.drug_class = 'Antimetabolite Immunosuppressant', d.narrow_therapeutic_index = true;

MATCH (d:Drug {id: 'DRUG-040'}) MERGE (e:Enzyme {name: 'Renal clearance (OAT1/OAT3)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-040'}) MERGE (e:Enzyme {name: 'Aldehyde oxidase'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-040'}) MERGE (t:Target {name: 'Dihydrofolate Reductase (DHFR)'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-041'}) SET d.generic_name = 'Clopidogrel', d.drug_class = 'Thienopyridine Antiplatelet', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-041'}) MERGE (e:Enzyme {name: 'CYP2C19 (Bioactivation)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-041'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-041'}) MERGE (e:Enzyme {name: 'CYP1A2'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-041'}) MERGE (t:Target {name: 'Platelet P2Y12 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-042'}) SET d.generic_name = 'Simvastatin', d.drug_class = 'HMG-CoA Reductase Inhibitor', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-042'}) MERGE (e:Enzyme {name: 'CYP3A4 (Major)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-042'}) MERGE (t:Target {name: 'HMG-CoA Reductase'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-043'}) SET d.generic_name = 'Calcium Carbonate', d.drug_class = 'Mineral Supplement / Phosphate Binder', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-043'}) MERGE (e:Enzyme {name: 'Gastrointestinal Chelation'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-043'}) MERGE (t:Target {name: 'Calcium-Sensing Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-044'}) SET d.generic_name = 'Folic Acid', d.drug_class = 'Water-soluble Vitamin Hematinic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-044'}) MERGE (e:Enzyme {name: 'Dihydrofolate Reductase'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-044'}) MERGE (t:Target {name: 'Folate Receptors FOLR1/FOLR2'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-045'}) SET d.generic_name = 'Hydroxyzine', d.drug_class = 'First-Generation Antihistamine', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-045'}) MERGE (e:Enzyme {name: 'Alcohol Dehydrogenase'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-045'}) MERGE (e:Enzyme {name: 'CYP3A4/5'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-045'}) MERGE (t:Target {name: 'Histamine H1 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MATCH (d:Drug {id: 'DRUG-045'}) MERGE (t:Target {name: '5-HT2A Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-046'}) SET d.generic_name = 'Diazepam', d.drug_class = 'Long-Acting Benzodiazepine', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-046'}) MERGE (e:Enzyme {name: 'CYP2C19'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-046'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-046'}) MERGE (t:Target {name: 'GABA-A Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-047'}) SET d.generic_name = 'Metoprolol', d.drug_class = 'Beta-1 Selective Adrenergic Blocker', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-047'}) MERGE (e:Enzyme {name: 'CYP2D6 (Major)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-047'}) MERGE (t:Target {name: 'Beta-1 Adrenergic Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-048'}) SET d.generic_name = 'Salbutamol', d.drug_class = 'Short-Acting Beta-2 Adrenergic Agonist', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-048'}) MERGE (e:Enzyme {name: 'SULT1A3'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-048'}) MERGE (t:Target {name: 'Beta-2 Adrenergic Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-049'}) SET d.generic_name = 'Domperidone', d.drug_class = 'Dopamine D2 Receptor Antagonist Prokinetic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-049'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-049'}) MERGE (t:Target {name: 'Peripheral Dopamine D2 Receptor'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-050'}) SET d.generic_name = 'Cephalexin', d.drug_class = 'First-Generation Cephalosporin Antibiotic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-050'}) MERGE (e:Enzyme {name: 'Renal excretion unchanged (>90%)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-050'}) MERGE (t:Target {name: 'Bacterial Cell Wall Penicillin-Binding Proteins'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-051'}) SET d.generic_name = 'Propranolol', d.drug_class = 'Non-selective Beta Adrenergic Receptor Antagonist', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-051'}) MERGE (e:Enzyme {name: 'CYP2D6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-051'}) MERGE (e:Enzyme {name: 'CYP1A2'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-051'}) MERGE (e:Enzyme {name: 'UGT1A9'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-051'}) MERGE (t:Target {name: 'Beta-1 and Beta-2 Adrenergic Receptors'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-052'}) SET d.generic_name = 'Penicillamine', d.drug_class = 'Heavy Metal Chelating Agent', d.narrow_therapeutic_index = true;

MATCH (d:Drug {id: 'DRUG-052'}) MERGE (e:Enzyme {name: 'Hepatic methylation'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-052'}) MERGE (e:Enzyme {name: 'Renal excretion'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-052'}) MERGE (t:Target {name: 'Copper and Iron Ion Binding Chelator'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-053'}) SET d.generic_name = 'Metronidazole', d.drug_class = 'Nitroimidazole Antibacterial and Antiprotozoal', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-053'}) MERGE (e:Enzyme {name: 'CYP2A6'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-053'}) MERGE (e:Enzyme {name: 'Hepatic oxidation'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-053'}) MERGE (t:Target {name: 'Bacterial and Protozoal DNA Strand Breakdown'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-054'}) SET d.generic_name = 'Theophylline', d.drug_class = 'Methylxanthine Phosphodiesterase Inhibitor', d.narrow_therapeutic_index = true;

MATCH (d:Drug {id: 'DRUG-054'}) MERGE (e:Enzyme {name: 'CYP1A2 (Major)'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-054'}) MERGE (e:Enzyme {name: 'CYP2E1'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-054'}) MERGE (e:Enzyme {name: 'CYP3A4'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-054'}) MERGE (t:Target {name: 'Adenosine A1/A2 Receptors'}) MERGE (d)-[:ACTS_ON]->(t);

MATCH (d:Drug {id: 'DRUG-054'}) MERGE (t:Target {name: 'Non-selective PDE'}) MERGE (d)-[:ACTS_ON]->(t);

MERGE (d:Drug {id: 'DRUG-055'}) SET d.generic_name = 'Rifampin', d.drug_class = 'Rifamycin Antimycobacterial Antibiotic', d.narrow_therapeutic_index = false;

MATCH (d:Drug {id: 'DRUG-055'}) MERGE (e:Enzyme {name: 'CYP3A4 Auto-induction'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-055'}) MERGE (e:Enzyme {name: 'Biliary excretion'}) MERGE (d)-[:METABOLIZED_BY]->(e);

MATCH (d:Drug {id: 'DRUG-055'}) MERGE (t:Target {name: 'Bacterial DNA-dependent RNA Polymerase'}) MERGE (d)-[:ACTS_ON]->(t);

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
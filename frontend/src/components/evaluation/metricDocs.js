// src/components/evaluation/metricDocs.js
// Plain-language explanations of every evaluation metric.
// Written to match what the backend actually computes.

const INTERPRET = (strong, mid, weak) => [
  { range: '≥ 80%', label: strong, tone: 'emerald' },
  { range: '50–79%', label: mid, tone: 'amber' },
  { range: '< 50%', label: weak, tone: 'rose' },
]

// ── Statistical similarity ─────────────────────────────────────
export const STATISTICAL_DOC = {
  title: 'How the statistical similarity score is calculated',
  intro:
    'This score answers one question: does each synthetic column look like the same column in the real data? Every column is judged on its own, and the column scores are then averaged.',
  formula:
    'Numeric column   = average of 3 checks\n' +
    '  typical value  = 1 − min(|mean_real − mean_synth| ÷ std_real, 1)\n' +
    '  spread         = 1 − min(|std_real − std_synth| ÷ std_real, 1)\n' +
    '  shape          = 1 − KS gap\n' +
    'Category column  = 1 − JS distance\n' +
    'Overall score    = average of all column scores × 100',
  steps: [
    'Skip columns that cannot be compared fairly: IDs, dates and free text. They never lower the score.',
    'Numeric columns: compare the average, the spread (standard deviation) and the overall shape of the distribution (KS test = the largest gap between the two curves).',
    'Category columns: compare the share of rows in each category, for example 60% "Healthy" in real data against 55% in synthetic data (Jensen-Shannon distance).',
    'Turn every check into a 0–100 similarity, where 100 means identical.',
    'Average all column scores to get the overall score.',
  ],
  notes: [
    'This looks at one column at a time. It cannot tell whether columns still relate to each other correctly. Correlation & Covariance covers that.',
    'Use the Score view to find weak columns, and Real vs Synthetic to see how they differ.',
  ],
  interpretation: INTERPRET(
    'Strong match. Synthetic columns look like the real ones.',
    'Partly similar. Open the low-scoring columns in the chart.',
    'Weak match. The distributions differ a lot.',
  ),
}

// ── Correlation & covariance ───────────────────────────────────
export const CORRELATION_DOC = {
  title: 'How the correlation score is calculated',
  intro:
    'Correlation shows whether two columns move together, for example more study hours going with higher marks. This score checks whether the synthetic data keeps the same relationships as the real data.',
  formula:
    'Correlation score = (1 − average |R_real − R_synth| ÷ 2) × 100\n' +
    'Covariance score  = (1 − average scaled |C_real − C_synth|) × 100\n' +
    'Overall score     = average of the two scores',
  steps: [
    'Take the numeric columns that can be compared. IDs, dates and text are skipped.',
    'Build a correlation table for the real data and another for the synthetic data. Each cell says how strongly two columns move together, from −1 to +1.',
    'For every pair of columns, measure how far the synthetic value is from the real value.',
    'Average those gaps and convert them to a 0–100 score, where 100 means the relationships are identical.',
    'Repeat with covariance (similar idea, but it keeps the units of the columns) and average both scores.',
  ],
  notes: [
    'Relationships that are too strong are penalised as well. Real columns that are unrelated should stay unrelated in the synthetic data.',
    'If a dataset has fewer than 2 numeric columns, the relationship between category columns (Cramér\u2019s V) is compared instead, and covariance is not used.',
    'The "Pairs with the largest drift" table shows exactly which relationships changed the most.',
  ],
  interpretation: INTERPRET(
    'Relationships are well preserved.',
    'Some column pairs have drifted.',
    'Relationships are broken. Columns behave independently, or far too tightly.',
  ),
}

// ── Association between categorical columns (Cramér's V) ───────
export const CATEGORICAL_ASSOCIATION_DOC = {
  title: 'How the association score is calculated (categorical columns)',
  intro:
    'Pearson correlation only works on numbers, so it cannot be used for category columns such as Table or Field. When a dataset has fewer than 2 numeric columns, Datrixa measures the link between category columns with Cramér\u2019s V instead. It checks whether columns that were linked in the real data are still linked in the synthetic data.',
  formula:
    'V = √( χ² ÷ (n × (min(rows, cols) − 1)) )   → 0 to 1 (bias-corrected)\n' +
    'Association score = (1 − average |V_real − V_synth|) × 100',
  steps: [
    'Take the category columns that can be compared (2 to 30 distinct values each). IDs, dates and free text are skipped. At least 2 such columns are needed.',
    'For each pair of columns, count how often each combination of values appears (a cross-table).',
    'Use a chi-square test on that table to see how far the counts are from what you would expect if the two columns were unrelated.',
    'Scale the result to Cramér\u2019s V: 0 means no link, 1 means one column fully decides the other.',
    'Do this on the real data and on the synthetic data, then take the gap between the two V values for every pair.',
    'Average the gaps and convert to a 0\u2013100 score. 100 means every pair has the same strength of link in both datasets.',
  ],
  notes: [
    'This is an association measure, not a correlation. It has no direction (no plus or minus) and covariance is not calculated for category columns.',
    'On small tables, or columns with many distinct values, V can read 0 or change a lot from one dataset to the other. Treat the score as a rough guide there.',
    'With only one pair of columns, that single pair decides the whole score.',
  ],
  interpretation: INTERPRET(
    'Links between category columns are well preserved.',
    'Some column pairs are linked more or less strongly than in the real data.',
    'Links between category columns are largely lost, or invented.',
  ),
}

// ── ML utility ─────────────────────────────────────────────────
export function mlUtilityDoc(isClassification) {
  return {
    title: 'How the ML utility score is calculated',
    intro:
      'This test asks: if you trained a prediction model on the synthetic data instead of the real data, would it work just as well? Two models are trained and both are tested on the same real rows that neither model has seen.',
    formula: isClassification
      ? 'score = min(F1_real_model, F1_synthetic_model) ÷ max(F1_real_model, F1_synthetic_model) × 100'
      : 'score = min(RMSE_real_model, RMSE_synthetic_model) ÷ max(RMSE_real_model, RMSE_synthetic_model) × 100',
    steps: [
      'Choose a target column to predict. One is suggested automatically, and you can pick another in the target selector.',
      'Split the real data into a training part and a test part.',
      'Train a Random Forest on the real training part (the baseline) and score it on the real test part.',
      'Train the same kind of model on the synthetic data and score it on the same real test part.',
      isClassification
        ? 'Compare the two F1 scores (a balance of precision and recall). The closer they are, the higher the score.'
        : 'Compare the two RMSE values (the average prediction error). The closer they are, the higher the score.',
    ],
    notes: [
      'If the real-data model cannot predict the target better than a simple guess, the test is marked "not applicable", because comparing the two models would not mean anything.',
      'A score of 100 means the synthetic data teaches a model as well as the real data does. It does not mean the two datasets are identical.',
      isClassification
        ? 'The Δ column in the table is Synthetic → Real minus Real → Real, so a negative value means the synthetic-trained model did worse on that metric. Green: within 0.05 of the baseline. Amber: 0.05 to 0.15 lower. Red: more than 0.15 lower. Red marks a large gap on that one metric. It does not mean the evaluation failed.'
        : 'The Δ column in the table is Synthetic → Real minus Real → Real. For R², green means within 0.05 of the baseline, amber up to 0.20 lower, and red more than 0.20 lower. For MAE and RMSE (lower is better), the colour depends on the relative change: green up to 10% different, amber up to 25%, and red beyond that.',
    ],
    interpretation: INTERPRET(
      'Synthetic data is nearly as useful as real data for training.',
      'Useful, but some predictive signal is lost.',
      'Not a good substitute for real training data.',
    ),
  }
}

// ── Relationship / referential integrity ───────────────────────
export const RELATIONSHIP_DOC = {
  title: 'How referential integrity is calculated',
  intro:
    'In linked tables such as products and orders, every foreign key in the child table must point to a row that exists in the parent table. This score checks that the synthetic tables still follow that rule.',
  formula:
    'Relationship score = valid child rows ÷ total child rows × 100\n' +
    'Overall score      = average over all relationships',
  steps: [
    'Read the parent → child relationships you configured for the dataset group.',
    'Collect the key values (for example product_id) from the synthetic parent table.',
    'For every synthetic child row, check that its foreign key exists in that list.',
    'Divide the valid rows by all child rows to get the score for that relationship.',
    'Average the scores of all relationships.',
  ],
  notes: [
    'This applies only to multi-table generation. Single-table datasets show "—".',
  ],
  interpretation: [
    { range: '100%', label: 'Every child row has a matching parent.', tone: 'emerald' },
    { range: '< 100%', label: 'Some rows are orphaned. Their parent row does not exist.', tone: 'rose' },
  ],
}
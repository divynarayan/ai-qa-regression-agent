# AI Regression Testing Dashboard

This project provides a Streamlit dashboard for visualizing **AI regression test results**.  
Upload a CSV of evaluation outputs from baseline and new models, explore regressions, and drill into individual examples.

## Features

- **Upload CSV results** with flexible column names
- **Automatic column normalization** for common fields:
  - `id`, `prompt`, `baseline_output`, `new_output`
  - `baseline_score`, `new_score`, `status`, `regression`, `tag`
- **Automatic regression inference** from score deltas
- **Key summary metrics** (regression rate, avg delta, percentiles)
- **Interactive filters** by regression flag, tag, and score delta
- **Distribution view** of score deltas
- **Per-tag breakdown** of regression rates
- **Drill-down detail view** for individual examples

## CSV format

The app performs a best-effort mapping from your columns to internal names. The following are recognized (case-insensitive):

- **ID**: `id`, `example_id`, `sample_id`, `row_id`
- **Prompt/Input**: `prompt`, `input`, `query`
- **Baseline output**: `baseline_output`, `baseline`, `expected_output`, `reference_output`
- **New output**: `new_output`, `candidate_output`, `model_output`
- **Baseline score**: `baseline_score`, `baseline_metric`, `baseline_reward`
- **New score**: `new_score`, `candidate_score`, `score`, `metric`, `reward`
- **Status**: `status`, `result`, `label`
- **Regression flag**: `regression`, `is_regression`, `regressed`, `regression_flag`
- **Tag / scenario**: `tag`, `tags`, `category`, `scenario`

If `baseline_score` and `new_score` are present, the app computes a `score_delta` and infers `regression` using a **negative delta threshold** that you can configure in the sidebar.

If neither scores nor a regression flag are present, all examples are treated as non-regressions.

## Setup

1. **Install dependencies** (ideally in a virtual environment):

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Streamlit app**:

   ```bash
   streamlit run app.py
   ```

3. Open the URL Streamlit prints (typically `http://localhost:8501`) in your browser.

## Usage

1. From the sidebar:
   - Set the **regression threshold** (how negative the score delta must be to be counted as a regression).
   - Upload your **CSV file** with evaluation results.
2. Review the **summary metrics** and regression rate.
3. Use **filters** for regression-only, tags, and score delta ranges.
4. Explore:
   - The **examples table** for quick overview.
   - The **distribution chart** for score deltas.
   - The **tag breakdown** table for hotspots.
5. Use the **drill-down selector** to inspect a single example's prompt, baseline vs new outputs, and scores side by side.


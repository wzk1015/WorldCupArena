This file provides project-specific context and instructions to Claude.

## Project Goal

The primary goal of this project is to benchmark LLMs and deep-research agents on real-world football prediction. This involves everything from predicting the final score to more tactical details like goal scorers and in-match events.

## Key Files

- `configs/models.yaml`: Contains the list of LLMs and agents being tested. New models can be added here.
- `configs/settings.yaml`: Defines the two settings (S1 and S2) for running the models. S1 is for non-tool LLMs with injected context, and S2 is for tool-using models/agents with self-search.
- `src/`: The main source code for the project, broken down into `ingest`, `runners`, `graders`, `pipeline`, and `leaderboard`.
- `docs/usage.md`: Provides a step-by-step guide on how to use the project.
- `docs/integration.md`: Explains how to add new models to the benchmark.

## Development Process

The lifecycle of a fixture is as follows:
1.  **T-48h:** Ingest data (squads, form, news, odds) using `ingest.py`.
2.  **T-24h:** Lock the snapshot and run predictions for all models.
3.  **T+3h:** Ingest the results of the match.
4.  **T+24h:** Grade the predictions and build the leaderboard.

Contributions are welcome, especially for new model runners and ingest adapters.

## Coding Style

- The project is written in Python.
- Follow the existing code structure when adding new features.
- API keys and other secrets should be stored in a `.env` file locally and in GitHub Actions secrets for CI.
- All code should be well-documented.

## Running the Website Locally

The project website is a client-side application located in the `docs/site/` directory. It works by fetching a `data.json` file.

To run the full application locally:

1.  **Generate the data file:** This script collects all the prediction and result data into the JSON file the website needs.
    ```bash
    python3 src/leaderboard/build_site.py
    ```

2.  **Serve the website:** Use Python's built-in web server to serve the `docs/site` directory.
    ```bash
    python3 -m http.server --directory docs/site
    ```

This will make the website available, typically at `http://localhost:8000`. You'll need to re-run the `build_site.py` script whenever you want the website to reflect new prediction data.

# Generative AI Usage Appendix

This document tracks the use of generative AI tools (e.g., ChatGPT, GitHub Copilot) in this project.

## Format

For each use, document:
- **Prompt (summary)**: Brief description of what was requested
- **Used in**: File(s) where the AI-generated content was used
- **Verification**: How the output was reviewed and modified

---

## AI Usage Log

### Entry 1
**Prompt (summary)**: Inputted assignment description into the chat to generate project structure and begin building Milestone 1

**Used in**: 
- docker/compose.yaml
- Project directory structure
- Dockerfile.ingestor
- requirements.txt
- README.md
- config.yaml
- ws_ingest.py
- kafka_consume_check.py
- scoping_brief.md

**Verification**: 
- Reviewed configurations for correct service definitions
- Verified Kafka and MLflow ports and networking
- Tested directory structure matches assignment requirements


### Entry 2
**Prompt (summary)**: linked coinbase API documentation to cursor agent for proper API handling
**Used in**: 
- ws_ingest.py

**Verification**: 
- Manually compared API implementation
- Program ran for initial testing


### Entry 3
**Prompt (summary)**: test milestone 1
**Used in**: 
- compose.yaml
- ws_ingest.py
- milestone1_test_results.md

**Verification**: 
- Initial testing passed
- Test results documented in milestone1_test_results.md


### Entry 4
**Prompt (summary)**: began building milestone 2, re-attached milestone 2 requirements for memory/context
**Used in**: 
- featurizer.py
- replay.py
- eda.ipynb
- generate_evidently_report.py

**Verification**: 
- manually ran EDA and featurizer thoroughly and edited code wherever broken


### Entry 5
**Prompt (summary)**: linked evidently documentation to cursor agent for proper implementation
**Used in**: 
- generate_evidently_report.py

**Verification**: 
- milestone 2 requirements complete
- manual review of generated evidently report


### Entry 6
**Prompt (summary)**: began building milestone 3, re-attached milestone 3 requirements for memory/context
**Used in**: 
- train.py
- infer.py
- generate_eval_report.py
- generate_evidently_report.py
- model_card_v1.md

**Verification**: 
- looked somewhat in-depthly at the code generated, all scripts ran with data leakage issues

## Chat Log #2

### Entry 7
**Prompt (summary)**: bug fixes in training ML model, while running generated test cases
**Used in**: 
- train.py

**Verification**: 
- verified against the fix plan Cursor agent generated
- reviewed result confusion matrices, ROC-AUC, label logging, test scores


### Entry 8
**Prompt (summary)**: addressing issues with not having positively labeled data in validation/test set; offered solutions in either expanding the range of volatility classification, or doing a stratified temporal split
**Used in**: 
- train.py
- config.yaml
- config_temporal_90.yaml
- compare_solutions.py
- solution_comparison.md

**Verification**: 
- compared generated solutions and reported results


## Chat Log #3

### Entry 9
**Prompt (summary)**: investigating data leakage issues since initial testing had super high accuracy
**Used in**: 
- eda.ipynb
- featurizer.py
- data_leakage_fix.md

**Verification**: 
- summarized findings were indicative of results
- further testing replicated good data leakage fixes


## Chat Log #4

### Entry 10
**Prompt (summary)**: investigating low accuracy issues with model after data leakage fixes
**Used in**: 
- model_perforamnce_analysis.md
- train.py
- compare_all_models.py
- model_improvements_summary.py

**Verification**: 
- summarized findings were indicative of results
- further testing replicated good performance from newly improved data modeling


### Entry 11
**Prompt (summary)**: updating model card, model eval, and evidently report
**Used in**: 
- generate_model_comparison_report.py
- model_card_v1.md
- model_eval.md

**Verification**: 
- N/A


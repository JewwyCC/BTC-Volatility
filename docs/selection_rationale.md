## Selection Rationale

# Selection
We selected Jerry's XGBoost model since it has the highest testing PR-AUC (approximately 0.4678).

# Explanation
Given that the detection of short-term volatility spikes is a highly imbalanced classifiation task, PR-AUC is the most meaningful metric, and since no other individual models exceeded this performance, it is the strongest on predictive grounds.

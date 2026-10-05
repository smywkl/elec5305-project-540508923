# Phase 2 — Fixed-HRTF Mechanism Study

Phase 2 is complete through Phase 2.11. It validates the binaural renderer, compares oracle and estimated stems, explains the downstream-error mechanism, and tests whether that mechanism survives common-filter and source-position controls. The experiments use the frozen 10-song test sample, one 30-second excerpt per song, official pretrained HTDemucs-FT estimates and CIPIC `subject_003`.

The documents below are ordered by experimental dependency. Earlier documents preserve the status known at that stage; later documents provide the current conclusions.

| Stage | Purpose | Documentation |
|---|---|---|
| 2.1 | Validate CIPIC loading, coordinate lookup, HRIR convolution and binaural cue behaviour. | [HRTF renderer validation](phase2_1_hrtf_validation.md) |
| 2.2 | Build the oracle fixed-HRTF rendering pipeline from ground-truth stems. | [Oracle pipeline](phase2_2_oracle_pipeline.md) |
| 2.3 | Compare oracle and HTDemucs-FT rendering on a controlled development track. | [Single-track comparison](phase2_3_single_track_comparison.md) |
| 2.4 | Validate source metrics and freeze the final static experiment protocol. | [Metric and protocol freeze](phase2_4_metric_and_protocol_freeze.md) |
| 2.5a | Deterministically select the official 10-song test set and complete preflight checks. | [Final-test preflight](phase2_5a_final_test_preflight.md) |
| 2.5b | Run the final fixed-HRTF experiment and quantify downstream fidelity under colocated, moderate and wide conditions. | [Final static experiment](phase2_5b_final_static_experiment.md) |
| 2.6 | Freeze the cancellation, attribution, localisation and robustness analysis plan. | [Mechanism protocol](phase2_6_mechanism_protocol.md) |
| 2.7 | Decompose rendered stem errors and establish cross-stem error cancellation as the central mechanism. | [Error interaction](phase2_7_error_interaction.md) |
| 2.8 | Attribute downstream error by independent stem effects and exact four-player Shapley values. | [Stem attribution](phase2_8_stem_attribution.md) |
| 2.9 | Localise surviving relative error across frequency bands and GT-defined transient frames. | [Spectro-temporal localisation](phase2_9_spectrotemporal_localization.md) |
| 2.10 | Test seven common-HRTF directions and all 480 differential source-position assignments. | [Robustness controls](phase2_10_robustness_controls.md) |
| 2.11a | Freeze the exploratory assignment-sensitivity decomposition after Phase 2.10. | [Assignment-sensitivity protocol](phase2_11_assignment_sensitivity_protocol.md) |
| 2.11b | Explain assignment-dependent magnitude through own-error load and signed stem-pair interactions. | [Assignment-sensitivity results](phase2_11b_assignment_sensitivity_results.md) |

## Reading the Main Result

For stem error `e_j` and binaural filter `H_j`, the downstream error is `D = Σ H_j e_j`. When every stem uses the same filter, cross-stem errors remain strongly cancelling. Different per-stem HRTFs alter the errors before summation and substantially increase the amount that survives.

The strongest summary evidence is:

- median Error Retention Ratio `R`: 0.04590 colocated, 0.88786 moderate and 0.81703 wide;
- seven common-HRTF median `R` values: 0.04156–0.04594;
- 480/480 differential assignments above the matched song-level common-filter baseline;
- assignment magnitude governed by song-specific stem-pair interactions rather than a universal angular rule.

These results describe objective downstream binaural mismatch in the frozen experiment. They do not establish perceived degradation, audibility or localisation accuracy.

## Reproduction Boundary

The frozen definitions are in [`../../config/phase2/`](../../config/phase2/). Python handles separator evaluation, source metrics and result aggregation; MATLAB handles HRTF rendering and core DSP computations. Each stage document records its actual entry points and validation gates. Large datasets and generated outputs are local and intentionally excluded from Git.

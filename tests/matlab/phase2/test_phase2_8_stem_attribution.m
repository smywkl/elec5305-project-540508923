%% Synthetic regression tests for Phase 2.8 exact stem attribution

oldPath = path;
cleanupPath = onCleanup(@() path(oldPath));
scriptPath = mfilename("fullpath");
repoRoot = fileparts(fileparts(fileparts(fileparts(scriptPath))));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "comparison"));

stemNames = ["bass", "vocals", "drums", "other"];

% A, D, E, F, G, I: four mutually orthogonal components.
orthogonal = struct();
for stemIndex = 1:4
    value = zeros(4, 2);
    value(stemIndex) = stemIndex;
    orthogonal.(char(stemNames(stemIndex))) = value;
end
orthogonalResult = compute_shapley_attribution(orthogonal, 10);
expected = ([1; 4; 9; 16] / 10);
assert(max(abs(orthogonalResult.shapley_nre - expected)) <= 1e-14); % A
assert(orthogonalResult.efficiency_error <= 1e-14); % D
assert(max(orthogonalResult.analytic_validation_error) <= 1e-14); % E
assert(max(abs(orthogonalResult.coalition_values([2, 3, 5, 9]) - expected)) <= 1e-14); % F
assert(numel(orthogonalResult.coalition_values) == 16); % G
assert(isequal(orthogonalResult.stem_names, stemNames)); % I

% B and C: cancellation produces a negative allocation and negative Shapley.
cancelling = struct();
cancelling.bass = [1, 0];
cancelling.vocals = [-2, 0];
cancelling.drums = [0, 0];
cancelling.other = [0, 0];
cancellingResult = compute_shapley_attribution(cancelling, 1);
assert(cancellingResult.assigned_interaction_nre(1) < 0); % B
assert(cancellingResult.shapley_nre(1) < 0); % C
assert(cancellingResult.efficiency_error <= 1e-14); % D repeated for cancellation
assert(max(cancellingResult.analytic_validation_error) <= 1e-14); % E repeated

% H: exact-silent vocals reference with a nonzero estimate remains defined
% relative to a positive whole-oracle energy.
gt = struct("bass", [1; 0], "vocals", [0; 0], ...
    "drums", [0; 1], "other", [0.5; -0.5]);
estimate = gt;
estimate.vocals = [0.25; -0.125];
silentCase = struct();
for stemIndex = 1:4
    fieldName = char(stemNames(stemIndex));
    errorMono = estimate.(fieldName) - gt.(fieldName);
    silentCase.(fieldName) = [errorMono, errorMono];
end
wholeOracleEnergy = sum((gt.bass + gt.drums + gt.other) .^ 2) * 2;
silentResult = compute_shapley_attribution(silentCase, wholeOracleEnergy);
assert(sum(gt.vocals .^ 2) == 0);
assert(sum(estimate.vocals .^ 2) > 0);
assert(isfinite(silentResult.single_stem_nre(2)) && silentResult.single_stem_nre(2) > 0);
assert(isfinite(silentResult.shapley_nre(2))); % H

fprintf("PHASE2_8_SYNTHETIC_PASS coalitions=%d max_analytic_error=%.17g\n", ...
    numel(orthogonalResult.coalition_values), max(orthogonalResult.analytic_validation_error));

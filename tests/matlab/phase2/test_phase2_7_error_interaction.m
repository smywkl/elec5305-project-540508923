%% Synthetic regression test for the Phase 2.7 error-interaction helper

oldPath = path;
cleanupPath = onCleanup(@() path(oldPath));
scriptPath = mfilename("fullpath");
repoRoot = fileparts(fileparts(fileparts(fileparts(scriptPath))));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "comparison"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "hrtf"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "spatial"));

subject = struct();
subject.hrir = zeros(1, 2, 3);
subject.hrir(1, 1, :) = [1, 0.25, -0.1];
subject.hrir(1, 2, :) = [0.8, -0.2, 0.05];
subject.source_positions = [0, 0, 1];
subject.receiver_order = ["left", "right"];

gt = struct( ...
    "bass", [1; 2; 0; -1], ...
    "vocals", [0; 1; -1; 0], ...
    "drums", [2; 0; 1; 0], ...
    "other", [-1; 0; 0; 1]);
stemNames = ["bass", "vocals", "drums", "other"];
estimate = struct();
errors = struct();
for stemIndex = 1:4
    stem = stemNames(stemIndex);
    estimate.(stem) = gt.(stem) + stemIndex * [0.1; -0.2; 0.05; 0.03];
    errors.(stem) = estimate.(stem) - gt.(stem);
end

result = compute_rendered_error_components( ...
    errors, subject, "synthetic", [0, 0, 0, 0], 0, 0);
oracle = render_stem_mix(gt, subject, "synthetic", [0, 0, 0, 0], 0, 0);
estimated = render_stem_mix(estimate, subject, "synthetic", [0, 0, 0, 0], 0, 0);
direct = estimated - oracle;
directRelerr = sqrt(sum((direct - result.decomposed_residual) .^ 2, "all") / ...
    sum(direct .^ 2, "all"));

assert(directRelerr <= 1e-10);
assert(result.energy_identity_relerr <= 1e-10);
assert(result.A_individual_error_energy > 0);
assert(result.T_total_error_energy > 0);
assert(isfinite(result.error_retention_ratio));
assert(isfinite(result.cancellation_gain_db));
assert(numel(result.pair_interaction_energy) == 6);
assert(all(result.pair_cosine_status == "DEFINED"));

fprintf("SYNTHETIC_DIRECT_RELERR=%.17g\n", directRelerr);
fprintf("SYNTHETIC_ENERGY_RELERR=%.17g\n", result.energy_identity_relerr);
fprintf("PHASE2_7_SYNTHETIC_PASS\n");

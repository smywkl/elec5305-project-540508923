%% Synthetic validation for Phase 2.10 component and assignment helpers

oldPath = path;
cleanupPath = onCleanup(@() path(oldPath));
scriptPath = mfilename("fullpath");
repoRoot = fileparts(fileparts(fileparts(fileparts(scriptPath))));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "comparison"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "hrtf"));

angles = [-80, -30, -10, 0, 10, 30, 80];
subject = struct();
subject.hrir = zeros(7, 2, 3);
subject.source_positions = zeros(7, 3);
for angleIndex = 1:7
    subject.source_positions(angleIndex, :) = [mod(-angles(angleIndex), 360), 0, 1];
    gain = 1 + 0.01 * angles(angleIndex);
    subject.hrir(angleIndex, 1, :) = [gain, 0.15, -0.03];
    subject.hrir(angleIndex, 2, :) = [0.8 * gain, -0.07, 0.02];
end
subject.receiver_order = ["left", "right"];

stemNames = ["bass", "vocals", "drums", "other"];
gt = struct();
errors = struct();
for stemIndex = 1:4
    fieldName = char(stemNames(stemIndex));
    gt.(fieldName) = stemIndex * [1; -0.5; 0.25; 0; -0.1];
    errors.(fieldName) = [1; -1; 0.5; 0.25; -0.2] .* [1; 1; stemIndex; 1; 1] / 10;
end
[gtComponents, errorComponents, audit] = precompute_stem_angle_components( ...
    gt, errors, subject, angles, 0, 0);
assert(audit.gt_case_count == 28 && audit.error_case_count == 28);
assert(audit.gt_pass_count == 28 && audit.error_pass_count == 28);
assert(numel(unique(angles)) == 7);

common = evaluate_error_component_assignment( ...
    gtComponents, errorComponents, angles, [0, 0, 0, 0]);
directError = render_static_binaural(sum_stems(errors), ...
    find_hrir_direction(subject, 0, 0).left_hrir, ...
    find_hrir_direction(subject, 0, 0).right_hrir);
assert(norm(common.decomposed_residual - directError, "fro") <= 1e-12);
assert(abs(common.cancellation_gain_db + 10 * log10(common.error_retention_ratio)) <= 1e-12);
assert(abs(common.normalized_total_error - ...
    common.T_total_error_energy / common.oracle_energy) <= 1e-15);

% Source-specific filters can change R even when source errors are fixed.
differential = evaluate_error_component_assignment( ...
    gtComponents, errorComponents, angles, [-80, -30, 30, 80]);
assert(abs(differential.error_retention_ratio - common.error_retention_ratio) > 1e-8);

moderate = sortrows(perms([-30, -10, 10, 30]));
wide = sortrows(perms([-80, -30, 30, 80]));
assert(size(unique(moderate, "rows"), 1) == 24);
assert(size(unique(wide, "rows"), 1) == 24);
for permutationIndex = 1:24
    assert(isequal(sort(moderate(permutationIndex, :)), [-30, -10, 10, 30]));
    assert(isequal(sort(wide(permutationIndex, :)), [-80, -30, 30, 80]));
end
assert(sum(all(moderate == [-30, -10, 10, 30], 2)) == 1);
assert(sum(all(wide == [-80, -30, 30, 80], 2)) == 1);

fprintf("PHASE2_10_MATLAB_SYNTHETIC_PASS\n");

function value = sum_stems(stems)
value = stems.bass + stems.vocals + stems.drums + stems.other;
end

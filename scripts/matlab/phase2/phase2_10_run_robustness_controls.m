%% Phase 2.10 - Common-HRTF controls and source-position robustness

oldPath = path;
cleanupPath = onCleanup(@() path(oldPath));
scriptPath = mfilename("fullpath");
repoRoot = fileparts(fileparts(fileparts(fileparts(scriptPath))));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "comparison"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "hrtf"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "oracle"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "spatial"));

overallStarted = tic;
mechanismProtocolPath = fullfile(repoRoot, "config", "phase2", "mechanism_analysis_protocol.json");
staticProtocolPath = fullfile(repoRoot, "config", "phase2", "static_experiment_protocol.json");
manifestPath = fullfile(repoRoot, "config", "phase2", "final_test_manifest.json");
sofaPath = fullfile(repoRoot, "data", "hrtf", "cipic", "subject_003.sofa");
expectedMechanismHash = "3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0";
expectedStaticHash = "3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3";
expectedManifestHash = "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc";
expectedSofaHash = "a9db5f938ed1113b118dcbeb43f5fe1b27b9e191d1bbdb63fbc4803b6959b220";

mechanismHash = compute_sha256(mechanismProtocolPath);
staticHash = compute_sha256(staticProtocolPath);
manifestHash = compute_sha256(manifestPath);
sofaHash = compute_sha256(sofaPath);
if mechanismHash ~= expectedMechanismHash || staticHash ~= expectedStaticHash || ...
        manifestHash ~= expectedManifestHash || sofaHash ~= expectedSofaHash
    error("ELEC5305:Robustness:FrozenHash", ...
        "Mechanism/static/manifest/SOFA frozen SHA-256 mismatch.");
end

mechanism = jsondecode(fileread(mechanismProtocolPath));
protocol = jsondecode(fileread(staticProtocolPath));
manifest = jsondecode(fileread(manifestPath));
selectedTracks = manifest.selected_tracks;
if string(mechanism.protocol_version) ~= "1.0" || ...
        string(protocol.protocol_version) ~= "1.1" || ...
        numel(selectedTracks) ~= 10 || manifest.selected_track_count ~= 10
    error("ELEC5305:Robustness:FrozenConfig", "Frozen protocol or manifest mismatch.");
end

sampleRate = double(protocol.excerpt.sample_rate_hz);
excerptStartSeconds = double(protocol.excerpt.start_seconds);
excerptDurationSeconds = double(protocol.excerpt.duration_seconds);
expectedInputFrames = double(protocol.excerpt.frames);
maximumDirectionMismatchDeg = double(protocol.hrtf.maximum_direction_mismatch_deg);
if sampleRate ~= 44100 || excerptStartSeconds ~= 30 || ...
        excerptDurationSeconds ~= 30 || expectedInputFrames ~= 1323000
    error("ELEC5305:Robustness:FrozenExcerpt", "Frozen excerpt mismatch.");
end

commonAngles = reshape(double(mechanism.robustness.common_hrtf_controls.angles_deg), 1, []);
moderateAngles = reshape(double(mechanism.robustness.position_assignments.moderate_angle_set_deg), 1, []);
wideAngles = reshape(double(mechanism.robustness.position_assignments.wide_angle_set_deg), 1, []);
stemNames = reshape(string(mechanism.robustness.position_assignments.source_order), 1, []);
if ~isequal(commonAngles, [-80, -30, -10, 0, 10, 30, 80]) || ...
        ~isequal(moderateAngles, [-30, -10, 10, 30]) || ...
        ~isequal(wideAngles, [-80, -30, 30, 80]) || ...
        ~isequal(stemNames, ["bass", "vocals", "drums", "other"])
    error("ELEC5305:Robustness:FrozenRobustness", "Frozen robustness design mismatch.");
end
canonicalModerate = get_canonical_angles(mechanism, "moderate");
canonicalWide = get_canonical_angles(mechanism, "wide");
if ~isequal(canonicalModerate, moderateAngles) || ~isequal(canonicalWide, wideAngles)
    error("ELEC5305:Robustness:Canonical", "Canonical assignment mismatch.");
end
moderatePermutations = sortrows(perms(moderateAngles));
widePermutations = sortrows(perms(wideAngles));
validate_permutations(moderatePermutations, moderateAngles, canonicalModerate);
validate_permutations(widePermutations, wideAngles, canonicalWide);

subject = load_cipic_subject(sofaPath);
if subject.fs ~= sampleRate || size(subject.hrir, 3) ~= 200 || ...
        ~isequal(string(subject.receiver_order), ["left", "right"])
    error("ELEC5305:Robustness:HRTF", "Frozen HRTF structure mismatch.");
end
for angle = commonAngles
    match = find_hrir_direction(subject, angle, 0);
    if ~match.exact_match || match.angular_mismatch_deg ~= 0 || ...
            match.actual_azimuth_deg ~= angle || match.actual_elevation_deg ~= 0
        error("ELEC5305:Robustness:HRTFGrid", ...
            "Angle %.17g is not an exact zero-elevation grid match.", angle);
    end
end

phase27Root = fullfile(repoRoot, "outputs", "phase2", "phase2_7_error_interaction");
phase27MetricsPath = fullfile(phase27Root, "metrics", "error_interaction_per_song_condition.csv");
phase27 = validate_prerequisites(repoRoot, expectedMechanismHash, expectedStaticHash, expectedManifestHash);
previousRoots = [ ...
    fullfile(repoRoot, "outputs", "phase2", "phase2_5_final"), ...
    phase27Root, ...
    fullfile(repoRoot, "outputs", "phase2", "phase2_8_stem_attribution"), ...
    fullfile(repoRoot, "outputs", "phase2", "phase2_9_spectrotemporal")];
previousSnapshots = cell(numel(previousRoots), 1);
for rootIndex = 1:numel(previousRoots)
    previousSnapshots{rootIndex} = snapshot_directory(previousRoots(rootIndex));
end

outputRoot = fullfile(repoRoot, "outputs", "phase2", "phase2_10_robustness");
metricsRoot = fullfile(outputRoot, "metrics");
tracksRoot = fullfile(outputRoot, "tracks");
logsRoot = fullfile(outputRoot, "logs");
mkdir_if_missing(metricsRoot);
mkdir_if_missing(tracksRoot);
mkdir_if_missing(logsRoot);
diaryPath = fullfile(logsRoot, "matlab_phase2_10.log");
diary(diaryPath);
cleanupDiary = onCleanup(@() diary("off"));

fprintf("PHASE2_10_START mechanism=%s static=%s manifest=%s\n", ...
    mechanismHash, staticHash, manifestHash);
perTrackRuntime = zeros(10, 1);
perTrackPrecomputeRuntime = zeros(10, 1);
cacheTrackCount = 0;
cacheStemCount = 0;
resumedCompleteTracks = 0;
for trackIndex = 1:10
    track = selectedTracks(trackIndex);
    rank = double(track.rank);
    trackName = string(track.track_name_original);
    if rank ~= trackIndex
        error("ELEC5305:Robustness:Rank", "Manifest rank/order mismatch.");
    end
    fprintf("[%d/10] %s\n", rank, trackName);
    trackStarted = tic;
    trackDirectory = fullfile(repoRoot, string(track.dataset_relative_path));
    cacheDirectory = fullfile(repoRoot, "outputs", "phase2", "phase2_5_final", ...
        "cache", "htdemucs_ft", trackName);
    cacheCompletionPath = fullfile(cacheDirectory, "completion.json");

    % Always load before resume so all 10 cache completions and 40 stem
    % hashes are revalidated on every invocation. This never runs inference.
    oracleExcerpt = load_musdb_gt_excerpt(trackDirectory, excerptStartSeconds, ...
        excerptDurationSeconds, sampleRate);
    estimatedExcerpt = load_final_cached_excerpt(cacheDirectory, cacheCompletionPath, ...
        trackName, excerptStartSeconds, excerptDurationSeconds, sampleRate);
    validate_excerpt_pair(oracleExcerpt, estimatedExcerpt, expectedInputFrames, rank, trackName);
    cacheTrackCount = cacheTrackCount + 1;
    cacheStemCount = cacheStemCount + 4;

    trackOutput = fullfile(tracksRoot, trackName);
    completionPath = fullfile(trackOutput, "completion.json");
    if validate_track_completion(completionPath, trackOutput, rank, trackName, ...
            mechanismHash, staticHash, manifestHash)
        completion = jsondecode(fileread(completionPath));
        perTrackRuntime(rank) = double(completion.runtime_seconds);
        perTrackPrecomputeRuntime(rank) = double(completion.precompute_runtime_seconds);
        resumedCompleteTracks = resumedCompleteTracks + 1;
        fprintf("  SKIPPED_COMPLETE (cache revalidated)\n");
        continue;
    end

    mkdir_if_missing(trackOutput);
    cleanup_partial_track(trackOutput);
    phase27Track = phase27(phase27.rank == rank, :);
    [commonTable, permutationTable, validation, precomputeRuntime] = process_track( ...
        rank, trackName, oracleExcerpt, estimatedExcerpt, subject, commonAngles, ...
        moderatePermutations, widePermutations, canonicalModerate, canonicalWide, ...
        phase27Track, sampleRate, expectedInputFrames, maximumDirectionMismatchDeg);

    commonPath = fullfile(trackOutput, "common_hrtf_controls.csv");
    permutationsPath = fullfile(trackOutput, "position_permutations.csv");
    validationPath = fullfile(trackOutput, "validation.json");
    atomic_writetable(commonTable, commonPath);
    atomic_writetable(permutationTable, permutationsPath);
    atomic_write_json(validationPath, validation);

    runtimeSeconds = toc(trackStarted);
    perTrackRuntime(rank) = runtimeSeconds;
    perTrackPrecomputeRuntime(rank) = precomputeRuntime;
    completion = struct( ...
        "schema", "phase2_10_robustness_completion_v1", ...
        "status", "COMPLETE", ...
        "rank", rank, ...
        "track", trackName, ...
        "mechanism_protocol_sha256", mechanismHash, ...
        "static_protocol_sha256", staticHash, ...
        "manifest_sha256", manifestHash, ...
        "cache_completion_sha256", compute_sha256(cacheCompletionPath), ...
        "common_rows", height(commonTable), ...
        "permutation_rows", height(permutationTable), ...
        "gt_precompute_pass_count", validation.gt_precompute_pass_count, ...
        "error_precompute_pass_count", validation.error_precompute_pass_count, ...
        "runtime_seconds", runtimeSeconds, ...
        "precompute_runtime_seconds", precomputeRuntime, ...
        "common_sha256", compute_sha256(commonPath), ...
        "permutations_sha256", compute_sha256(permutationsPath), ...
        "validation_sha256", compute_sha256(validationPath));
    atomic_write_json(completionPath, completion); % Must be last.
    fprintf("  COMPLETE precompute %.3f s total %.3f s\n", precomputeRuntime, runtimeSeconds);
end

commonAggregate = collect_track_tables(selectedTracks, tracksRoot, "common_hrtf_controls.csv");
permutationAggregate = collect_track_tables(selectedTracks, tracksRoot, "position_permutations.csv");
validationSummary = validate_aggregates(commonAggregate, permutationAggregate, ...
    selectedTracks, phase27, commonAngles, moderateAngles, wideAngles, ...
    canonicalModerate, canonicalWide, tracksRoot);

commonPath = fullfile(metricsRoot, "common_hrtf_controls.csv");
permutationsPath = fullfile(metricsRoot, "position_assignment_permutations.csv");
atomic_writetable(commonAggregate, commonPath);
atomic_writetable(permutationAggregate, permutationsPath);

for rootIndex = 1:numel(previousRoots)
    finalSnapshot = snapshot_directory(previousRoots(rootIndex));
    if ~isequal(previousSnapshots{rootIndex}, finalSnapshot)
        error("ELEC5305:Robustness:PreviousOutputMutation", ...
            "Previous output tree changed: %s", previousRoots(rootIndex));
    end
end
if compute_sha256(mechanismProtocolPath) ~= expectedMechanismHash || ...
        compute_sha256(staticProtocolPath) ~= expectedStaticHash || ...
        compute_sha256(manifestPath) ~= expectedManifestHash
    error("ELEC5305:Robustness:FinalFrozenHash", "A frozen file changed during Phase 2.10.");
end

summary = struct();
summary.schema = "phase2_10_matlab_robustness_summary_v1";
summary.status = "MATLAB_COMPLETE";
summary.mechanism_protocol_version = string(mechanism.protocol_version);
summary.mechanism_protocol_sha256 = mechanismHash;
summary.static_protocol_sha256 = staticHash;
summary.manifest_sha256 = manifestHash;
summary.sofa_sha256 = sofaHash;
summary.cache_valid_tracks = cacheTrackCount;
summary.cache_valid_stems = cacheStemCount;
summary.resumed_complete_tracks = resumedCompleteTracks;
summary.exact_unique_angles = commonAngles;
summary.gt_precompute_pass_count = validationSummary.gt_precompute_pass_count;
summary.gt_precompute_case_count = 280;
summary.gt_precompute_max_relative_error = validationSummary.gt_precompute_max_relative_error;
summary.gt_precompute_zero_denominator_count = validationSummary.gt_precompute_zero_denominator_count;
summary.gt_precompute_max_zero_denominator_absolute_error = validationSummary.gt_precompute_max_zero_denominator_absolute_error;
summary.error_precompute_pass_count = validationSummary.error_precompute_pass_count;
summary.error_precompute_case_count = 280;
summary.error_precompute_max_relative_error = validationSummary.error_precompute_max_relative_error;
summary.error_precompute_zero_denominator_count = validationSummary.error_precompute_zero_denominator_count;
summary.error_precompute_max_zero_denominator_absolute_error = validationSummary.error_precompute_max_zero_denominator_absolute_error;
summary.common_rows = height(commonAggregate);
summary.permutation_rows = height(permutationAggregate);
summary.common_direct_pass_count = validationSummary.common_direct_pass_count;
summary.common_direct_max_relerr = validationSummary.common_direct_max_relerr;
summary.common_energy_identity_pass_count = validationSummary.common_energy_identity_pass_count;
summary.common_energy_identity_max_relerr = validationSummary.common_energy_identity_max_relerr;
summary.colocated_regression_pass_count = validationSummary.colocated_regression_pass_count;
summary.colocated_regression_max_relerr = validationSummary.colocated_regression_max_relerr;
summary.permutation_direct_audit_pass_count = validationSummary.permutation_direct_audit_pass_count;
summary.permutation_direct_audit_max_relerr = validationSummary.permutation_direct_audit_max_relerr;
summary.canonical_regression_pass_count = validationSummary.canonical_regression_pass_count;
summary.canonical_regression_max_relerr = validationSummary.canonical_regression_max_relerr;
summary.rg_identity_pass_count = validationSummary.rg_identity_pass_count;
summary.oracle_sanity_pass_count = validationSummary.oracle_sanity_pass_count;
summary.moderate_unique_permutations = 24;
summary.wide_unique_permutations = 24;
summary.moderate_canonical_occurrences = 1;
summary.wide_canonical_occurrences = 1;
summary.previous_output_trees_unchanged = true;
summary.per_track_precompute_runtime_seconds = perTrackPrecomputeRuntime;
summary.sum_precompute_runtime_seconds = sum(perTrackPrecomputeRuntime);
summary.per_track_runtime_seconds = perTrackRuntime;
summary.sum_per_track_runtime_seconds = sum(perTrackRuntime);
summary.this_invocation_wall_seconds = toc(overallStarted);
summary.matlab_version = version;
summary.matlab_architecture = computer("arch");
toolboxInfo = ver;
summary.available_toolboxes = string({toolboxInfo.Name});
summary.phase_2_11_results_computed = false;
atomic_write_json(fullfile(metricsRoot, "matlab_robustness_summary.json"), summary);
fprintf("PHASE2_10_MATLAB_COMPLETE common=%d permutations=%d GT=%d error=%d\n", ...
    height(commonAggregate), height(permutationAggregate), ...
    validationSummary.gt_precompute_pass_count, validationSummary.error_precompute_pass_count);

function [commonTable, permutationTable, validation, precomputeRuntime] = process_track(rank, trackName, oracleExcerpt, estimatedExcerpt, subject, commonAngles, moderatePermutations, widePermutations, canonicalModerate, canonicalWide, phase27Track, sampleRate, expectedInputFrames, maxMismatch)
stemNames = ["bass", "vocals", "drums", "other"];
errors = struct();
for stemIndex = 1:4
    fieldName = char(stemNames(stemIndex));
    gt = double(oracleExcerpt.mono.(fieldName));
    estimate = double(estimatedExcerpt.mono.(fieldName));
    errors.(fieldName) = estimate - gt;
end
if rank == 4
    if trackName ~= "Skelpolu - Resurrection" || ...
            sum(double(oracleExcerpt.mono.vocals) .^ 2) ~= 0 || ...
            sum(double(estimatedExcerpt.mono.vocals) .^ 2) <= 0
        error("ELEC5305:Robustness:Rank4", "Rank 4 silent-reference vocals invariant failed.");
    end
end

precomputeStarted = tic;
[gtComponents, errorComponents, audit] = precompute_stem_angle_components( ...
    oracleExcerpt.mono, errors, subject, commonAngles, 0, maxMismatch);
precomputeRuntime = toc(precomputeStarted);
if audit.gt_pass_count ~= 28 || audit.error_pass_count ~= 28
    error("ELEC5305:Robustness:Precompute", "Per-track precomputation audit failed.");
end

commonRows = cell(7, 1);
commonDirectErrors = zeros(7, 1);
commonMetricErrors = zeros(7, 1);
commonIdentityErrors = zeros(7, 1);
colocatedRegressionErrors = [];
for angleIndex = 1:7
    angle = commonAngles(angleIndex);
    assignment = repmat(angle, 1, 4);
    result = evaluate_error_component_assignment( ...
        gtComponents, errorComponents, commonAngles, assignment);
    conditionName = "common_" + angle_label(angle);
    [oracleDirect, oracleLookups] = render_stem_mix(oracleExcerpt.mono, subject, ...
        conditionName, assignment, 0, maxMismatch);
    [estimatedDirect, estimatedLookups] = render_stem_mix(estimatedExcerpt.mono, subject, ...
        conditionName, assignment, 0, maxMismatch);
    validate_exact_lookups(oracleLookups, assignment);
    validate_exact_lookups(estimatedLookups, assignment);
    directResidual = estimatedDirect - oracleDirect;
    commonDirectErrors(angleIndex) = relative_l2(directResidual, result.decomposed_residual);
    if commonDirectErrors(angleIndex) > 1e-10
        error("ELEC5305:Robustness:CommonDirect", ...
            "Common direct residual failed for rank %d angle %.17g.", rank, angle);
    end
    commonMetricErrors(angleIndex) = max([ ...
        relative_scalar(sum(directResidual .^ 2, "all"), result.T_total_error_energy), ...
        relative_scalar(sum(oracleDirect .^ 2, "all"), result.oracle_energy)]);
    if commonMetricErrors(angleIndex) > 1e-10
        error("ELEC5305:Robustness:CommonMetric", "Common direct metric mismatch.");
    end
    commonIdentityErrors(angleIndex) = result.energy_identity_relerr;
    if angle == 0
        frozen = phase27Track(phase27Track.condition == "colocated", :);
        if height(frozen) ~= 1
            error("ELEC5305:Robustness:ColocatedKey", "Missing Phase 2.7 colocated row.");
        end
        colocatedRegressionErrors = metric_regression_errors(result, frozen);
        if max(colocatedRegressionErrors) > 1e-10
            error("ELEC5305:Robustness:ColocatedRegression", ...
                "Common 0-degree regression failed for rank %d.", rank);
        end
    end
    commonRows{angleIndex} = struct( ...
        "rank", rank, "track", trackName, "common_angle_deg", angle, ...
        "A_individual_error_energy", result.A_individual_error_energy, ...
        "T_total_error_energy", result.T_total_error_energy, ...
        "I_interaction_energy", result.I_interaction_energy, ...
        "error_retention_ratio", result.error_retention_ratio, ...
        "cancellation_gain_db", result.cancellation_gain_db, ...
        "oracle_energy", result.oracle_energy, ...
        "normalized_total_error", result.normalized_total_error, ...
        "direct_decomposition_relerr", commonDirectErrors(angleIndex), ...
        "energy_identity_relerr", result.energy_identity_relerr, ...
        "sample_rate_hz", sampleRate, "input_frames", expectedInputFrames, ...
        "rendered_frames", size(result.decomposed_residual, 1));
end
commonTable = struct2table(vertcat(commonRows{:}));

conditionNames = ["moderate", "wide"];
permutationSets = {moderatePermutations, widePermutations};
canonicalSets = {canonicalModerate, canonicalWide};
permutationRows = cell(48, 1);
rowIndex = 0;
auditIDs = [1, 12, 24];
permutationAuditErrors = [];
canonicalRegressionErrors = [];
for conditionIndex = 1:2
    conditionName = conditionNames(conditionIndex);
    assignments = permutationSets{conditionIndex};
    canonical = canonicalSets{conditionIndex};
    for permutationIndex = 1:24
        assignment = assignments(permutationIndex, :);
        result = evaluate_error_component_assignment( ...
            gtComponents, errorComponents, commonAngles, assignment);
        isCanonical = all(assignment == canonical);
        if any(permutationIndex == auditIDs)
            directError = validate_assignment_direct(oracleExcerpt.mono, estimatedExcerpt.mono, ...
                errors, subject, conditionName, assignment, maxMismatch, result);
            permutationAuditErrors(end + 1, 1) = directError; %#ok<AGROW>
        end
        if isCanonical
            frozen = phase27Track(phase27Track.condition == conditionName, :);
            if height(frozen) ~= 1
                error("ELEC5305:Robustness:CanonicalKey", "Missing Phase 2.7 canonical row.");
            end
            errorsNow = metric_regression_errors(result, frozen);
            canonicalRegressionErrors = [canonicalRegressionErrors; errorsNow(:)]; %#ok<AGROW>
            if max(errorsNow) > 1e-10
                error("ELEC5305:Robustness:CanonicalRegression", ...
                    "Canonical regression failed for rank %d/%s.", rank, conditionName);
            end
        end
        rowIndex = rowIndex + 1;
        permutationRows{rowIndex} = struct( ...
            "rank", rank, "track", trackName, "condition", conditionName, ...
            "permutation_id", permutationIndex, ...
            "bass_angle_deg", assignment(1), "vocals_angle_deg", assignment(2), ...
            "drums_angle_deg", assignment(3), "other_angle_deg", assignment(4), ...
            "is_canonical", isCanonical, ...
            "A_individual_error_energy", result.A_individual_error_energy, ...
            "T_total_error_energy", result.T_total_error_energy, ...
            "I_interaction_energy", result.I_interaction_energy, ...
            "error_retention_ratio", result.error_retention_ratio, ...
            "cancellation_gain_db", result.cancellation_gain_db, ...
            "oracle_energy", result.oracle_energy, ...
            "normalized_total_error", result.normalized_total_error);
    end
end
permutationTable = struct2table(vertcat(permutationRows{:}));
allR = [commonTable.error_retention_ratio; permutationTable.error_retention_ratio];
allG = [commonTable.cancellation_gain_db; permutationTable.cancellation_gain_db];
rgErrors = abs(allG - 10 * log10(1 ./ allR));
oracleValues = [commonTable.oracle_energy; permutationTable.oracle_energy];
normalizedValues = [commonTable.normalized_total_error; permutationTable.normalized_total_error];
if any(rgErrors > 1e-10) || any(~isfinite(oracleValues)) || any(oracleValues <= 0) || ...
        any(~isfinite(normalizedValues)) || any(normalizedValues < 0)
    error("ELEC5305:Robustness:TrackAggregate", "Per-track R/G or oracle sanity failed.");
end

validation = struct( ...
    "schema", "phase2_10_robustness_validation_v1", ...
    "status", "PASS", "rank", rank, "track", trackName, ...
    "gt_precompute_pass_count", audit.gt_pass_count, ...
    "gt_precompute_max_relative_error", audit.gt_max_relative_error, ...
    "gt_precompute_zero_denominator_count", audit.gt_zero_denominator_count, ...
    "gt_precompute_max_zero_denominator_absolute_error", audit.gt_max_zero_denominator_absolute_error, ...
    "error_precompute_pass_count", audit.error_pass_count, ...
    "error_precompute_max_relative_error", audit.error_max_relative_error, ...
    "error_precompute_zero_denominator_count", audit.error_zero_denominator_count, ...
    "error_precompute_max_zero_denominator_absolute_error", audit.error_max_zero_denominator_absolute_error, ...
    "common_direct_pass_count", 7, ...
    "common_direct_max_relerr", max(commonDirectErrors), ...
    "common_direct_metric_max_relerr", max(commonMetricErrors), ...
    "common_energy_identity_pass_count", 7, ...
    "common_energy_identity_max_relerr", max(commonIdentityErrors), ...
    "colocated_regression_pass_count", 1, ...
    "colocated_regression_max_relerr", max(colocatedRegressionErrors), ...
    "permutation_direct_audit_ids", auditIDs, ...
    "permutation_direct_audit_pass_count", numel(permutationAuditErrors), ...
    "permutation_direct_audit_max_relerr", max(permutationAuditErrors), ...
    "canonical_regression_pass_count", 2, ...
    "canonical_regression_max_relerr", max(canonicalRegressionErrors), ...
    "rg_identity_pass_count", 55, ...
    "rg_identity_max_abserr", max(rgErrors), ...
    "oracle_sanity_pass_count", 55, ...
    "rank4_silent_vocals_included", rank == 4, ...
    "common_rows", 7, "moderate_permutation_rows", 24, "wide_permutation_rows", 24);
end

function maximumError = validate_assignment_direct(gtStems, estimatedStems, errors, subject, conditionName, assignment, maxMismatch, precomputed)
direct = compute_rendered_error_components(errors, subject, conditionName, assignment, 0, maxMismatch);
[oracle, oracleLookups] = render_stem_mix(gtStems, subject, conditionName, assignment, 0, maxMismatch);
[estimated, estimatedLookups] = render_stem_mix(estimatedStems, subject, conditionName, assignment, 0, maxMismatch);
validate_exact_lookups(oracleLookups, assignment);
validate_exact_lookups(estimatedLookups, assignment);
directResidual = estimated - oracle;
errorsNow = [ ...
    relative_l2(directResidual, precomputed.decomposed_residual), ...
    relative_l2(direct.decomposed_residual, precomputed.decomposed_residual), ...
    relative_l2(oracle, precomputed.oracle), ...
    relative_scalar(direct.A_individual_error_energy, precomputed.A_individual_error_energy), ...
    relative_scalar(direct.T_total_error_energy, precomputed.T_total_error_energy), ...
    relative_scalar(direct.I_interaction_energy, precomputed.I_interaction_energy), ...
    relative_scalar(direct.error_retention_ratio, precomputed.error_retention_ratio), ...
    relative_scalar(direct.cancellation_gain_db, precomputed.cancellation_gain_db)];
maximumError = max(errorsNow);
if maximumError > 1e-10
    error("ELEC5305:Robustness:PermutationDirect", ...
        "Direct assignment validation failed for %s: %.17g.", conditionName, maximumError);
end
end

function errors = metric_regression_errors(result, frozen)
fields = ["A_individual_error_energy", "T_total_error_energy", ...
    "I_interaction_energy", "error_retention_ratio", "cancellation_gain_db"];
errors = zeros(1, numel(fields));
for fieldIndex = 1:numel(fields)
    fieldName = fields(fieldIndex);
    errors(fieldIndex) = relative_scalar(result.(fieldName), frozen.(fieldName));
end
end

function validate_exact_lookups(lookups, assignment)
for stemIndex = 1:4
    if lookups(stemIndex).requested_azimuth_deg ~= assignment(stemIndex) || ...
            lookups(stemIndex).matched_azimuth_deg ~= assignment(stemIndex) || ...
            lookups(stemIndex).requested_elevation_deg ~= 0 || ...
            lookups(stemIndex).matched_elevation_deg ~= 0 || ...
            lookups(stemIndex).angular_mismatch_deg ~= 0
        error("ELEC5305:Robustness:Lookup", "Nonexact direct-render lookup.");
    end
end
end

function value = relative_l2(reference, candidate)
if ~isequal(size(reference), size(candidate))
    error("ELEC5305:Robustness:RelativeShape", "Array size mismatch.");
end
denominator = sum(reference .^ 2, "all");
absoluteError = sqrt(sum((reference - candidate) .^ 2, "all"));
if denominator == 0
    value = absoluteError;
else
    value = absoluteError / sqrt(denominator);
end
end

function value = relative_scalar(reference, candidate)
denominator = max(abs(reference), abs(candidate));
if denominator == 0
    value = abs(reference - candidate);
else
    value = abs(reference - candidate) / denominator;
end
end

function label = angle_label(angle)
if angle < 0
    label = "minus_" + abs(angle);
elseif angle > 0
    label = "plus_" + angle;
else
    label = "zero";
end
end

function angles = get_canonical_angles(mechanism, requestedCondition)
conditions = mechanism.frozen_inputs.canonical_conditions;
angles = [];
for index = 1:numel(conditions)
    if string(conditions(index).condition) == requestedCondition
        angles = reshape(double(conditions(index).azimuths_deg), 1, []);
    end
end
if isempty(angles)
    error("ELEC5305:Robustness:MissingCanonical", ...
        "Missing canonical condition %s.", requestedCondition);
end
end

function validate_permutations(assignments, angleSet, canonical)
if size(assignments, 1) ~= 24 || size(assignments, 2) ~= 4 || ...
        size(unique(assignments, "rows"), 1) ~= 24 || ...
        ~isequal(assignments, sortrows(assignments)) || ...
        sum(all(assignments == canonical, 2)) ~= 1
    error("ELEC5305:Robustness:PermutationEnumeration", ...
        "Permutation enumeration or canonical occurrence gate failed.");
end
for index = 1:24
    if ~isequal(sort(assignments(index, :)), sort(angleSet))
        error("ELEC5305:Robustness:PermutationBijection", ...
            "Permutation %d is not a bijection.", index);
    end
end
end

function phase27 = validate_prerequisites(repoRoot, mechanismHash, staticHash, manifestHash)
phase27Root = fullfile(repoRoot, "outputs", "phase2", "phase2_7_error_interaction");
metricPaths = [ ...
    fullfile(phase27Root, "metrics", "error_interaction_per_song_condition.csv"), ...
    fullfile(phase27Root, "metrics", "rendered_error_energy_per_stem.csv"), ...
    fullfile(phase27Root, "metrics", "pairwise_error_interactions.csv"), ...
    fullfile(phase27Root, "metrics", "rq3_sign_tests_partial.csv")];
expectedRows = [30, 120, 180, 2];
for index = 1:numel(metricPaths)
    if ~isfile(metricPaths(index)) || height(readtable(metricPaths(index), "TextType", "string")) ~= expectedRows(index)
        error("ELEC5305:Robustness:Phase27", "Phase 2.7 prerequisite table failed.");
    end
end
summaryPaths = [ ...
    fullfile(phase27Root, "metrics", "matlab_error_interaction_summary.json"), ...
    fullfile(phase27Root, "metrics", "python_analysis_summary.json"), ...
    fullfile(repoRoot, "outputs", "phase2", "phase2_8_stem_attribution", "metrics", "matlab_stem_attribution_summary.json"), ...
    fullfile(repoRoot, "outputs", "phase2", "phase2_8_stem_attribution", "metrics", "python_analysis_summary.json"), ...
    fullfile(repoRoot, "outputs", "phase2", "phase2_9_spectrotemporal", "metrics", "matlab_spectrotemporal_summary.json"), ...
    fullfile(repoRoot, "outputs", "phase2", "phase2_9_spectrotemporal", "metrics", "python_analysis_summary.json")];
for index = 1:numel(summaryPaths)
    if ~isfile(summaryPaths(index))
        error("ELEC5305:Robustness:PrerequisiteSummary", "Missing prerequisite summary.");
    end
    value = jsondecode(fileread(summaryPaths(index)));
    if ~ismember(string(value.status), ["COMPLETE", "MATLAB_COMPLETE"])
        error("ELEC5305:Robustness:PrerequisiteStatus", "Prerequisite status is not COMPLETE.");
    end
end
for phase = ["phase2_7_error_interaction", "phase2_8_stem_attribution", "phase2_9_spectrotemporal"]
    completions = dir(fullfile(repoRoot, "outputs", "phase2", phase, "tracks", "**", "completion.json"));
    if numel(completions) ~= 10
        error("ELEC5305:Robustness:PrerequisiteTracks", "%s does not have 10 completions.", phase);
    end
end
phase27 = readtable(metricPaths(1), "TextType", "string");
if height(phase27) ~= 30 || any(phase27.direct_decomposition_relerr > 1e-10) || ...
        any(phase27.energy_identity_relerr > 1e-10)
    error("ELEC5305:Robustness:Phase27Metrics", "Phase 2.7 metric validation failed.");
end
signTests = readtable(metricPaths(4), "TextType", "string");
if height(signTests) ~= 2 || any(signTests.N_total ~= 10) || ...
        any(signTests.N_effective + signTests.tie_count ~= 10)
    error("ELEC5305:Robustness:Phase27Tests", "Phase 2.7 sign-test prerequisite failed.");
end
for summaryPath = summaryPaths
    textValue = fileread(summaryPath);
    if contains(textValue, "mechanism_protocol_sha256") && ~contains(textValue, mechanismHash)
        error("ELEC5305:Robustness:PrerequisiteHash", "Prerequisite mechanism hash mismatch.");
    end
    if contains(textValue, "static_protocol_sha256") && ~contains(textValue, staticHash)
        error("ELEC5305:Robustness:PrerequisiteHash", "Prerequisite static hash mismatch.");
    end
    if contains(textValue, "manifest_sha256") && ~contains(textValue, manifestHash)
        error("ELEC5305:Robustness:PrerequisiteHash", "Prerequisite manifest hash mismatch.");
    end
end
end

function validate_excerpt_pair(oracle, estimated, expectedFrames, rank, trackName)
if oracle.sample_rate_hz ~= estimated.sample_rate_hz || ...
        oracle.frame_count ~= expectedFrames || estimated.frame_count ~= expectedFrames || ...
        oracle.start_frame_matlab_1_based ~= estimated.start_frame_matlab_1_based || ...
        oracle.end_frame_matlab_1_based_inclusive ~= estimated.end_frame_matlab_1_based_inclusive
    error("ELEC5305:Robustness:Alignment", ...
        "GT/estimated excerpt mismatch for rank %d %s.", rank, trackName);
end
end

function valid = validate_track_completion(completionPath, trackOutput, rank, trackName, mechanismHash, staticHash, manifestHash)
valid = false;
try
    if ~isfile(completionPath), return; end
    completion = jsondecode(fileread(completionPath));
    commonPath = fullfile(trackOutput, "common_hrtf_controls.csv");
    permutationsPath = fullfile(trackOutput, "position_permutations.csv");
    validationPath = fullfile(trackOutput, "validation.json");
    if string(completion.status) ~= "COMPLETE" || completion.rank ~= rank || ...
            string(completion.track) ~= trackName || ...
            string(completion.mechanism_protocol_sha256) ~= mechanismHash || ...
            string(completion.static_protocol_sha256) ~= staticHash || ...
            string(completion.manifest_sha256) ~= manifestHash || ...
            completion.common_rows ~= 7 || completion.permutation_rows ~= 48 || ...
            completion.gt_precompute_pass_count ~= 28 || ...
            completion.error_precompute_pass_count ~= 28 || ...
            ~all(isfile([string(commonPath), string(permutationsPath), string(validationPath)])) || ...
            string(completion.common_sha256) ~= compute_sha256(commonPath) || ...
            string(completion.permutations_sha256) ~= compute_sha256(permutationsPath) || ...
            string(completion.validation_sha256) ~= compute_sha256(validationPath)
        return;
    end
    common = readtable(commonPath, "TextType", "string");
    permutations = readtable(permutationsPath, "TextType", "string");
    validation = jsondecode(fileread(validationPath));
    valid = height(common) == 7 && height(permutations) == 48 && ...
        string(validation.status) == "PASS" && validation.rg_identity_pass_count == 55 && ...
        all(common.direct_decomposition_relerr <= 1e-10) && ...
        all(common.energy_identity_relerr <= 1e-10);
catch
    valid = false;
end
end

function cleanup_partial_track(trackOutput)
names = ["common_hrtf_controls.csv", "position_permutations.csv", ...
    "validation.json", "completion.json"];
for name = names
    pathValue = fullfile(trackOutput, name);
    if isfile(pathValue), delete(pathValue); end
end
end

function aggregate = collect_track_tables(selectedTracks, tracksRoot, fileName)
tables = cell(10, 1);
for index = 1:10
    trackName = string(selectedTracks(index).track_name_original);
    pathValue = fullfile(tracksRoot, trackName, fileName);
    if ~isfile(pathValue)
        error("ELEC5305:Robustness:MissingTrackOutput", "Missing %s for %s.", fileName, trackName);
    end
    tables{index} = readtable(pathValue, "TextType", "string");
end
aggregate = vertcat(tables{:});
if ismember("common_angle_deg", string(aggregate.Properties.VariableNames))
    aggregate = sortrows(aggregate, ["rank", "common_angle_deg"]);
else
    conditionOrder = categorical(aggregate.condition, ["moderate", "wide"], "Ordinal", true);
    aggregate.condition_order_internal = conditionOrder;
    aggregate = sortrows(aggregate, ["rank", "condition_order_internal", "permutation_id"]);
    aggregate.condition_order_internal = [];
end
end

function summary = validate_aggregates(common, permutationsTable, selectedTracks, phase27, commonAngles, moderateAngles, wideAngles, canonicalModerate, canonicalWide, tracksRoot)
if height(common) ~= 70 || height(permutationsTable) ~= 480 || ...
        any(~isfinite(common{:, 4:end}), "all") || ...
        any(common.A_individual_error_energy <= 0) || any(common.T_total_error_energy <= 0) || ...
        any(common.oracle_energy <= 0) || any(common.normalized_total_error < 0) || ...
        any(common.direct_decomposition_relerr > 1e-10) || ...
        any(common.energy_identity_relerr > 1e-10) || ...
        any(~isfinite(permutationsTable.A_individual_error_energy)) || ...
        any(~isfinite(permutationsTable.T_total_error_energy)) || ...
        any(~isfinite(permutationsTable.I_interaction_energy)) || ...
        any(~isfinite(permutationsTable.error_retention_ratio)) || ...
        any(~isfinite(permutationsTable.cancellation_gain_db)) || ...
        any(~isfinite(permutationsTable.oracle_energy)) || ...
        any(~isfinite(permutationsTable.normalized_total_error)) || ...
        any(permutationsTable.A_individual_error_energy <= 0) || ...
        any(permutationsTable.T_total_error_energy <= 0) || ...
        any(permutationsTable.oracle_energy <= 0) || ...
        any(permutationsTable.normalized_total_error < 0)
    error("ELEC5305:Robustness:Aggregate", "Aggregate numerical gate failed.");
end
expectedCommonKeys = zeros(70, 2);
keyIndex = 0;
for rank = 1:10
    for angle = commonAngles
        keyIndex = keyIndex + 1;
        expectedCommonKeys(keyIndex, :) = [rank, angle];
    end
end
if ~isequal(sortrows([common.rank, common.common_angle_deg]), sortrows(expectedCommonKeys))
    error("ELEC5305:Robustness:CommonKeys", "Common-HRTF keys are incomplete or duplicated.");
end
for rank = 1:10
    expectedTrack = string(selectedTracks(rank).track_name_original);
    if any(common.track(common.rank == rank) ~= expectedTrack) || ...
            any(permutationsTable.track(permutationsTable.rank == rank) ~= expectedTrack)
        error("ELEC5305:Robustness:TrackKeys", "Track names do not match manifest.");
    end
    for conditionName = ["moderate", "wide"]
        rows = permutationsTable(permutationsTable.rank == rank & ...
            permutationsTable.condition == conditionName, :);
        canonicalMask = logical(rows.is_canonical);
        if height(rows) ~= 24 || numel(unique(rows.permutation_id)) ~= 24 || ...
                sum(canonicalMask) ~= 1
            error("ELEC5305:Robustness:PermutationKeys", "Permutation key gate failed.");
        end
        values = [rows.bass_angle_deg, rows.vocals_angle_deg, rows.drums_angle_deg, rows.other_angle_deg];
        expectedAngles = moderateAngles;
        expectedCanonical = canonicalModerate;
        if conditionName == "wide"
            expectedAngles = wideAngles;
            expectedCanonical = canonicalWide;
        end
        if size(unique(values, "rows"), 1) ~= 24 || ...
                any(sort(values, 2) ~= sort(expectedAngles), "all") || ...
                ~all(values(canonicalMask, :) == expectedCanonical, "all")
            error("ELEC5305:Robustness:PermutationValues", "Permutation bijection gate failed.");
        end
    end
end
zeroRows = common(common.common_angle_deg == 0, :);
for rank = 1:10
    current = zeroRows(zeroRows.rank == rank, :);
    frozen = phase27(phase27.rank == rank & phase27.condition == "colocated", :);
    if height(current) ~= 1 || height(frozen) ~= 1 || ...
            max(metric_table_regression_errors(current, frozen)) > 1e-10
        error("ELEC5305:Robustness:AggregateColocated", "Aggregate 0-degree regression failed.");
    end
end
allR = [common.error_retention_ratio; permutationsTable.error_retention_ratio];
allG = [common.cancellation_gain_db; permutationsTable.cancellation_gain_db];
if any(abs(allG - 10 * log10(1 ./ allR)) > 1e-10)
    error("ELEC5305:Robustness:AggregateRG", "Aggregate R/G identity failed.");
end

summary = struct( ...
    "gt_precompute_pass_count", 0, "gt_precompute_max_relative_error", 0, ...
    "gt_precompute_zero_denominator_count", 0, "gt_precompute_max_zero_denominator_absolute_error", 0, ...
    "error_precompute_pass_count", 0, "error_precompute_max_relative_error", 0, ...
    "error_precompute_zero_denominator_count", 0, "error_precompute_max_zero_denominator_absolute_error", 0, ...
    "common_direct_pass_count", 0, "common_direct_max_relerr", 0, ...
    "common_energy_identity_pass_count", 0, "common_energy_identity_max_relerr", 0, ...
    "colocated_regression_pass_count", 0, "colocated_regression_max_relerr", 0, ...
    "permutation_direct_audit_pass_count", 0, "permutation_direct_audit_max_relerr", 0, ...
    "canonical_regression_pass_count", 0, "canonical_regression_max_relerr", 0, ...
    "rg_identity_pass_count", 0, "oracle_sanity_pass_count", 0);
for rank = 1:10
    trackName = string(selectedTracks(rank).track_name_original);
    value = jsondecode(fileread(fullfile(tracksRoot, trackName, "validation.json")));
    summary.gt_precompute_pass_count = summary.gt_precompute_pass_count + value.gt_precompute_pass_count;
    summary.gt_precompute_max_relative_error = max(summary.gt_precompute_max_relative_error, value.gt_precompute_max_relative_error);
    summary.gt_precompute_zero_denominator_count = summary.gt_precompute_zero_denominator_count + value.gt_precompute_zero_denominator_count;
    summary.gt_precompute_max_zero_denominator_absolute_error = max(summary.gt_precompute_max_zero_denominator_absolute_error, value.gt_precompute_max_zero_denominator_absolute_error);
    summary.error_precompute_pass_count = summary.error_precompute_pass_count + value.error_precompute_pass_count;
    summary.error_precompute_max_relative_error = max(summary.error_precompute_max_relative_error, value.error_precompute_max_relative_error);
    summary.error_precompute_zero_denominator_count = summary.error_precompute_zero_denominator_count + value.error_precompute_zero_denominator_count;
    summary.error_precompute_max_zero_denominator_absolute_error = max(summary.error_precompute_max_zero_denominator_absolute_error, value.error_precompute_max_zero_denominator_absolute_error);
    summary.common_direct_pass_count = summary.common_direct_pass_count + value.common_direct_pass_count;
    summary.common_direct_max_relerr = max(summary.common_direct_max_relerr, value.common_direct_max_relerr);
    summary.common_energy_identity_pass_count = summary.common_energy_identity_pass_count + value.common_energy_identity_pass_count;
    summary.common_energy_identity_max_relerr = max(summary.common_energy_identity_max_relerr, value.common_energy_identity_max_relerr);
    summary.colocated_regression_pass_count = summary.colocated_regression_pass_count + value.colocated_regression_pass_count;
    summary.colocated_regression_max_relerr = max(summary.colocated_regression_max_relerr, value.colocated_regression_max_relerr);
    summary.permutation_direct_audit_pass_count = summary.permutation_direct_audit_pass_count + value.permutation_direct_audit_pass_count;
    summary.permutation_direct_audit_max_relerr = max(summary.permutation_direct_audit_max_relerr, value.permutation_direct_audit_max_relerr);
    summary.canonical_regression_pass_count = summary.canonical_regression_pass_count + value.canonical_regression_pass_count;
    summary.canonical_regression_max_relerr = max(summary.canonical_regression_max_relerr, value.canonical_regression_max_relerr);
    summary.rg_identity_pass_count = summary.rg_identity_pass_count + value.rg_identity_pass_count;
    summary.oracle_sanity_pass_count = summary.oracle_sanity_pass_count + value.oracle_sanity_pass_count;
end
expected = [summary.gt_precompute_pass_count, summary.error_precompute_pass_count, ...
    summary.common_direct_pass_count, summary.common_energy_identity_pass_count, ...
    summary.colocated_regression_pass_count, summary.permutation_direct_audit_pass_count, ...
    summary.canonical_regression_pass_count, summary.rg_identity_pass_count, ...
    summary.oracle_sanity_pass_count];
if ~isequal(expected, [280, 280, 70, 70, 10, 60, 20, 550, 550])
    error("ELEC5305:Robustness:ValidationCounts", "Aggregate validation counts failed.");
end
end

function errors = metric_table_regression_errors(current, frozen)
fields = ["A_individual_error_energy", "T_total_error_energy", ...
    "I_interaction_energy", "error_retention_ratio", "cancellation_gain_db"];
errors = zeros(1, numel(fields));
for index = 1:numel(fields)
    fieldName = fields(index);
    errors(index) = relative_scalar(current.(fieldName), frozen.(fieldName));
end
end

function snapshot = snapshot_directory(root)
if ~isfolder(root)
    error("ELEC5305:Robustness:SnapshotRoot", "Missing previous output root: %s", root);
end
entries = dir(fullfile(root, "**", "*"));
entries = entries(~[entries.isdir]);
paths = strings(numel(entries), 1);
bytes = zeros(numel(entries), 1);
hashes = strings(numel(entries), 1);
rootPrefixLength = strlength(string(root)) + 2;
for index = 1:numel(entries)
    fullPath = fullfile(entries(index).folder, entries(index).name);
    paths(index) = extractAfter(string(fullPath), rootPrefixLength - 1);
    bytes(index) = entries(index).bytes;
    hashes(index) = compute_sha256(fullPath);
end
snapshot = sortrows(table(paths, bytes, hashes), "paths");
end

function atomic_writetable(tableValue, outputPath)
temporary = outputPath + ".tmp.csv";
writetable(tableValue, temporary);
movefile(temporary, outputPath, "f");
end

function atomic_write_json(outputPath, value)
temporary = outputPath + ".tmp";
jsonText = jsonencode(value, "PrettyPrint", true);
fid = fopen(temporary, "w", "n", "UTF-8");
if fid < 0
    error("ELEC5305:Robustness:WriteJSON", "Cannot write %s.", temporary);
end
cleanupFile = onCleanup(@() fclose(fid));
fprintf(fid, "%s\n", jsonText);
clear cleanupFile;
movefile(temporary, outputPath, "f");
end

function sha256 = compute_sha256(filePath)
fid = fopen(filePath, "rb");
if fid < 0
    error("ELEC5305:Robustness:HashRead", "Cannot open %s.", filePath);
end
cleanupFile = onCleanup(@() fclose(fid));
digest = java.security.MessageDigest.getInstance("SHA-256");
while true
    bytes = fread(fid, 1024 * 1024, "*uint8");
    if isempty(bytes), break; end
    digest.update(bytes);
end
sha256 = string(lower(reshape(dec2hex(typecast(digest.digest(), "uint8"), 2).', 1, [])));
end

function mkdir_if_missing(pathValue)
if ~isfolder(pathValue), mkdir(pathValue); end
end

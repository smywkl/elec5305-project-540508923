%% Phase 2.8 - Stem-wise downstream error attribution

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
    error("ELEC5305:StemAttribution:FrozenHash", ...
        "Mechanism/static/manifest/SOFA frozen SHA-256 mismatch.");
end

mechanism = jsondecode(fileread(mechanismProtocolPath));
protocol = jsondecode(fileread(staticProtocolPath));
manifest = jsondecode(fileread(manifestPath));
selectedTracks = manifest.selected_tracks;
if string(mechanism.protocol_version) ~= "1.0" || ...
        string(protocol.protocol_version) ~= "1.1" || ...
        numel(selectedTracks) ~= 10 || manifest.selected_track_count ~= 10
    error("ELEC5305:StemAttribution:FrozenConfig", ...
        "Frozen protocol or manifest structure mismatch.");
end

sampleRate = double(protocol.excerpt.sample_rate_hz);
excerptStartSeconds = double(protocol.excerpt.start_seconds);
excerptDurationSeconds = double(protocol.excerpt.duration_seconds);
expectedInputFrames = double(protocol.excerpt.frames);
maximumDirectionMismatchDeg = double(protocol.hrtf.maximum_direction_mismatch_deg);
if sampleRate ~= 44100 || excerptStartSeconds ~= 30 || ...
        excerptDurationSeconds ~= 30 || expectedInputFrames ~= 1323000
    error("ELEC5305:StemAttribution:FrozenExcerpt", "Frozen excerpt mismatch.");
end
conditionConfigs = parse_spatial_conditions(protocol);
validate_mechanism_attribution(mechanism, conditionConfigs);

subject = load_cipic_subject(sofaPath);
if subject.fs ~= sampleRate || size(subject.hrir, 3) ~= 200 || ...
        ~isequal(string(subject.receiver_order), ["left", "right"])
    error("ELEC5305:StemAttribution:HRTF", ...
        "Frozen HRTF sample rate, length, or channel order mismatch.");
end

phase27Root = fullfile(repoRoot, "outputs", "phase2", "phase2_7_error_interaction", "metrics");
phase27ComponentPath = fullfile(phase27Root, "rendered_error_energy_per_stem.csv");
phase27MetricPath = fullfile(phase27Root, "error_interaction_per_song_condition.csv");
phase27PairPath = fullfile(phase27Root, "pairwise_error_interactions.csv");
if ~all(isfile([string(phase27ComponentPath), string(phase27MetricPath), string(phase27PairPath)]))
    error("ELEC5305:StemAttribution:Phase27", "Required Phase 2.7 outputs are missing.");
end
phase27HashesBefore = struct( ...
    "component", compute_sha256(phase27ComponentPath), ...
    "metric", compute_sha256(phase27MetricPath), ...
    "pairwise", compute_sha256(phase27PairPath));
phase27Components = readtable(phase27ComponentPath, "TextType", "string");
phase27Metrics = readtable(phase27MetricPath, "TextType", "string");
phase27Pairs = readtable(phase27PairPath, "TextType", "string");
if height(phase27Components) ~= 120 || height(phase27Metrics) ~= 30 || height(phase27Pairs) ~= 180
    error("ELEC5305:StemAttribution:Phase27", "Phase 2.7 row-count prerequisite failed.");
end

outputRoot = fullfile(repoRoot, "outputs", "phase2", "phase2_8_stem_attribution");
metricsRoot = fullfile(outputRoot, "metrics");
tracksRoot = fullfile(outputRoot, "tracks");
logsRoot = fullfile(outputRoot, "logs");
mkdir_if_missing(metricsRoot);
mkdir_if_missing(tracksRoot);
mkdir_if_missing(logsRoot);
diaryPath = fullfile(logsRoot, "matlab_phase2_8.log");
diary(diaryPath);
cleanupDiary = onCleanup(@() diary("off"));

% Frozen before any Phase 2.8 result aggregation.
displayPolicy = struct( ...
    "frozen_before_official_results_aggregation", true, ...
    "condition_order", ["colocated", "moderate", "wide"], ...
    "stem_order", ["bass", "vocals", "drums", "other"], ...
    "individual_song_points", 10, ...
    "paired_trajectories", true, ...
    "primary_aggregate_marker", "median across songs", ...
    "summary_statistics", ["mean", "median", "sample SD", "IQR", "min", "max"], ...
    "independent_primary_axis", "raw linear", ...
    "shapley_zero_line", true, ...
    "signed_shapley_preserved", true);

perTrackRuntime = zeros(10, 1);
cacheTrackCount = 0;
cacheStemCount = 0;
resumedTrackCount = 0;
for trackIndex = 1:10
    track = selectedTracks(trackIndex);
    rank = double(track.rank);
    trackName = string(track.track_name_original);
    if rank ~= trackIndex
        error("ELEC5305:StemAttribution:Rank", "Manifest rank/order mismatch.");
    end
    fprintf("[%d/10] %s\n", rank, trackName);
    trackStarted = tic;
    trackDirectory = fullfile(repoRoot, string(track.dataset_relative_path));
    cacheDirectory = fullfile(repoRoot, "outputs", "phase2", "phase2_5_final", ...
        "cache", "htdemucs_ft", trackName);
    cacheCompletionPath = fullfile(cacheDirectory, "completion.json");

    % Cache integrity is revalidated before resume; HTDemucs is never rerun.
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
        resumedTrackCount = resumedTrackCount + 1;
        fprintf("  SKIPPED_COMPLETE (cache revalidated)\n");
        continue;
    end

    mkdir_if_missing(trackOutput);
    cleanup_partial_track(trackOutput);
    [independentTable, coalitionTable, shapleyTable, validation] = process_track( ...
        rank, trackName, oracleExcerpt, estimatedExcerpt, subject, conditionConfigs, ...
        sampleRate, expectedInputFrames, maximumDirectionMismatchDeg, ...
        phase27Components, phase27Metrics);

    independentPath = fullfile(trackOutput, "independent_attribution.csv");
    coalitionPath = fullfile(trackOutput, "coalition_values.csv");
    shapleyPath = fullfile(trackOutput, "shapley_attribution.csv");
    validationPath = fullfile(trackOutput, "validation.json");
    atomic_writetable(independentTable, independentPath);
    atomic_writetable(coalitionTable, coalitionPath);
    atomic_writetable(shapleyTable, shapleyPath);
    atomic_write_json(validationPath, validation);

    runtimeSeconds = toc(trackStarted);
    perTrackRuntime(rank) = runtimeSeconds;
    completion = struct( ...
        "schema", "phase2_8_stem_attribution_completion_v1", ...
        "status", "COMPLETE", ...
        "rank", rank, ...
        "track", trackName, ...
        "mechanism_protocol_sha256", mechanismHash, ...
        "static_protocol_sha256", staticHash, ...
        "manifest_sha256", manifestHash, ...
        "cache_completion_sha256", compute_sha256(cacheCompletionPath), ...
        "independent_rows", height(independentTable), ...
        "coalition_rows", height(coalitionTable), ...
        "shapley_rows", height(shapleyTable), ...
        "runtime_seconds", runtimeSeconds, ...
        "independent_sha256", compute_sha256(independentPath), ...
        "coalition_sha256", compute_sha256(coalitionPath), ...
        "shapley_sha256", compute_sha256(shapleyPath), ...
        "validation_sha256", compute_sha256(validationPath));
    atomic_write_json(completionPath, completion); % Must be last.
    fprintf("  COMPLETE runtime %.3f s\n", runtimeSeconds);
end

independentAggregate = collect_track_tables(selectedTracks, tracksRoot, "independent_attribution.csv");
coalitionAggregate = collect_track_tables(selectedTracks, tracksRoot, "coalition_values.csv");
shapleyAggregate = collect_track_tables(selectedTracks, tracksRoot, "shapley_attribution.csv");
validate_aggregates(independentAggregate, coalitionAggregate, shapleyAggregate);

independentPath = fullfile(metricsRoot, "stem_independent_attribution.csv");
coalitionPath = fullfile(metricsRoot, "shapley_coalition_values.csv");
shapleyPath = fullfile(metricsRoot, "stem_shapley_attribution.csv");
atomic_writetable(independentAggregate, independentPath);
atomic_writetable(coalitionAggregate, coalitionPath);
atomic_writetable(shapleyAggregate, shapleyPath);

phase27HashesAfter = struct( ...
    "component", compute_sha256(phase27ComponentPath), ...
    "metric", compute_sha256(phase27MetricPath), ...
    "pairwise", compute_sha256(phase27PairPath));
if ~isequal(phase27HashesBefore, phase27HashesAfter)
    error("ELEC5305:StemAttribution:Phase27Mutation", "Phase 2.7 outputs changed.");
end

summary = struct();
summary.schema = "phase2_8_matlab_stem_attribution_summary_v1";
summary.status = "MATLAB_COMPLETE";
summary.mechanism_protocol_version = string(mechanism.protocol_version);
summary.mechanism_protocol_sha256 = mechanismHash;
summary.static_protocol_sha256 = staticHash;
summary.manifest_sha256 = manifestHash;
summary.sofa_sha256 = sofaHash;
summary.phase2_7_hashes_unchanged = true;
summary.phase2_7_hashes = phase27HashesAfter;
summary.cache_valid_tracks = cacheTrackCount;
summary.cache_valid_stems = cacheStemCount;
summary.resumed_complete_tracks = resumedTrackCount;
summary.independent_rows = height(independentAggregate);
summary.coalition_rows = height(coalitionAggregate);
summary.shapley_rows = height(shapleyAggregate);
summary.hybrid_validation_pass_count = sum(independentAggregate.hybrid_validation_error <= 1e-10);
summary.hybrid_validation_max_error = max(independentAggregate.hybrid_validation_error);
summary.phase2_7_energy_validation_pass_count = sum(independentAggregate.phase2_7_energy_validation_error <= 1e-10);
summary.phase2_7_energy_validation_max_error = max(independentAggregate.phase2_7_energy_validation_error);
summary.coalition_direct_validation_pass_count = sum(coalitionAggregate.direct_reconstruction_error <= 1e-10);
summary.coalition_direct_validation_max_error = max(coalitionAggregate.direct_reconstruction_error);
summary.empty_endpoint_pass_count = sum(coalitionAggregate.coalition_id == 0 & ...
    coalitionAggregate.empty_coalition_abs_value <= 1e-14);
summary.full_endpoint_pass_count = sum(coalitionAggregate.coalition_id == 15 & ...
    coalitionAggregate.full_endpoint_validation_error <= 1e-10);
summary.shapley_efficiency_pass_count = sum(shapleyAggregate.stem == "bass" & ...
    shapleyAggregate.shapley_efficiency_error <= 1e-10);
summary.shapley_efficiency_max_error = max(shapleyAggregate.shapley_efficiency_error);
summary.analytic_validation_pass_count = sum(shapleyAggregate.shapley_validation_error <= 1e-10);
summary.analytic_validation_max_error = max(shapleyAggregate.shapley_validation_error);
summary.interaction_identity_pass_count = sum(shapleyAggregate.interaction_identity_error <= 1e-10);
summary.interaction_identity_max_error = max(shapleyAggregate.interaction_identity_error);
summary.rank4_silent_vocals_rows = sum(independentAggregate.rank == 4 & ...
    independentAggregate.stem == "vocals" & ...
    independentAggregate.reference_status == "INACTIVE_REFERENCE");
summary.per_track_runtime_seconds = perTrackRuntime;
summary.sum_per_track_runtime_seconds = sum(perTrackRuntime);
summary.this_invocation_wall_seconds = toc(overallStarted);
summary.display_policy = displayPolicy;
summary.matlab_version = version;
summary.matlab_architecture = computer("arch");
toolboxInfo = ver;
summary.available_toolboxes = string({toolboxInfo.Name});
summary.phase_2_9_results_computed = false;
summary.phase_2_10_results_computed = false;
atomic_write_json(fullfile(metricsRoot, "matlab_stem_attribution_summary.json"), summary);
fprintf("PHASE2_8_MATLAB_COMPLETE independent=%d coalitions=%d shapley=%d\n", ...
    height(independentAggregate), height(coalitionAggregate), height(shapleyAggregate));

function [independentTable, coalitionTable, shapleyTable, validation] = process_track(rank, trackName, oracleExcerpt, estimatedExcerpt, subject, configs, sampleRate, expectedInputFrames, maxMismatch, phase27Components, phase27Metrics)
stemNames = ["bass", "vocals", "drums", "other"];
errors = struct();
referenceStatus = strings(4, 1);
for stemIndex = 1:4
    fieldName = char(stemNames(stemIndex));
    gt = double(oracleExcerpt.mono.(fieldName));
    estimate = double(estimatedExcerpt.mono.(fieldName));
    errors.(fieldName) = estimate - gt;
    if sum(gt .^ 2) == 0
        referenceStatus(stemIndex) = "INACTIVE_REFERENCE";
    else
        referenceStatus(stemIndex) = "ACTIVE";
    end
end
if rank == 4
    if trackName ~= "Skelpolu - Resurrection" || ...
            referenceStatus(2) ~= "INACTIVE_REFERENCE" || ...
            sum(estimatedExcerpt.mono.vocals .^ 2) <= 0
        error("ELEC5305:StemAttribution:Rank4", "Rank 4 silent-vocals invariant failed.");
    end
elseif any(referenceStatus ~= "ACTIVE")
    error("ELEC5305:StemAttribution:ReferenceStatus", ...
        "Unexpected inactive GT reference for rank %d.", rank);
end

independentRows = cell(12, 1);
coalitionRows = cell(48, 1);
shapleyRows = cell(12, 1);
validationRows = cell(3, 1);
independentRowIndex = 0;
coalitionRowIndex = 0;
shapleyRowIndex = 0;
for conditionIndex = 1:3
    config = configs(conditionIndex);
    errorResult = compute_rendered_error_components(errors, subject, ...
        config.condition, config.azimuths_deg, config.elevation_deg, maxMismatch);
    [oracleRaw, oracleLookups, oracleDiagnostics, oracleRendered] = render_stem_mix( ...
        oracleExcerpt.mono, subject, config.condition, config.azimuths_deg, ...
        config.elevation_deg, maxMismatch);
    [estimatedRaw, estimatedLookups, estimatedDiagnostics, estimatedRendered] = render_stem_mix( ...
        estimatedExcerpt.mono, subject, config.condition, config.azimuths_deg, ...
        config.elevation_deg, maxMismatch);
    validate_matching_renders(errorResult, oracleRaw, estimatedRaw, oracleLookups, ...
        estimatedLookups, oracleDiagnostics, estimatedDiagnostics);
    oracleEnergy = sum(oracleRaw .^ 2, "all");
    if ~isfinite(oracleEnergy) || oracleEnergy <= 0
        error("ELEC5305:StemAttribution:OracleEnergy", ...
            "Oracle energy must be positive for rank %d/%s.", rank, config.condition);
    end

    attribution = compute_shapley_attribution(errorResult.rendered_components, oracleEnergy);
    previousMetric = phase27Metrics(phase27Metrics.rank == rank & ...
        phase27Metrics.condition == config.condition, :);
    if height(previousMetric) ~= 1
        error("ELEC5305:StemAttribution:Phase27Key", "Phase 2.7 metric key mismatch.");
    end
    phase27FullValue = previousMetric.T_total_error_energy / oracleEnergy;
    fullEndpointError = scalar_comparison_error(attribution.full_coalition_value, phase27FullValue);
    if attribution.empty_coalition_value > 1e-14 || fullEndpointError > 1e-10
        error("ELEC5305:StemAttribution:Endpoint", ...
            "Coalition endpoint failed for rank %d/%s.", rank, config.condition);
    end
    if attribution.efficiency_error > 1e-10 || ...
            any(attribution.analytic_validation_error > 1e-10) || ...
            any(attribution.interaction_identity_error > 1e-10)
        error("ELEC5305:StemAttribution:Shapley", ...
            "Shapley validation failed for rank %d/%s.", rank, config.condition);
    end

    coalitionDirectErrors = zeros(16, 1);
    coalitionDirectValues = zeros(16, 1);
    for coalitionRow = 1:16
        hybrid = zeros(size(oracleRaw), "double");
        for stemIndex = 1:4
            fieldName = char(stemNames(stemIndex));
            if attribution.coalition_memberships(coalitionRow, stemIndex)
                hybrid = hybrid + estimatedRendered.(fieldName);
            else
                hybrid = hybrid + oracleRendered.(fieldName);
            end
        end
        directResidual = hybrid - oracleRaw;
        reconstructed = attribution.coalition_residuals{coalitionRow};
        coalitionDirectErrors(coalitionRow) = vector_comparison_error(directResidual, reconstructed);
        coalitionDirectValues(coalitionRow) = sum(directResidual .^ 2, "all") / oracleEnergy;
        if coalitionDirectErrors(coalitionRow) > 1e-10
            error("ELEC5305:StemAttribution:CoalitionDirect", ...
                "Direct coalition validation failed for rank %d/%s/id %d.", ...
                rank, config.condition, attribution.coalition_ids(coalitionRow));
        end
        coalitionRowIndex = coalitionRowIndex + 1;
        coalitionRows{coalitionRowIndex} = struct( ...
            "rank", rank, "track", trackName, "condition", config.condition, ...
            "coalition_id", attribution.coalition_ids(coalitionRow), ...
            "coalition_size", attribution.coalition_sizes(coalitionRow), ...
            "estimated_stems", attribution.estimated_stem_labels(coalitionRow), ...
            "use_bass_estimated", attribution.coalition_memberships(coalitionRow, 1), ...
            "use_vocals_estimated", attribution.coalition_memberships(coalitionRow, 2), ...
            "use_drums_estimated", attribution.coalition_memberships(coalitionRow, 3), ...
            "use_other_estimated", attribution.coalition_memberships(coalitionRow, 4), ...
            "normalized_error_value", attribution.coalition_values(coalitionRow), ...
            "direct_hybrid_value", coalitionDirectValues(coalitionRow), ...
            "direct_reconstruction_error", coalitionDirectErrors(coalitionRow), ...
            "empty_coalition_abs_value", abs(attribution.empty_coalition_value), ...
            "phase2_7_full_value", phase27FullValue, ...
            "full_endpoint_validation_error", fullEndpointError, ...
            "oracle_energy", oracleEnergy);
    end

    for stemIndex = 1:4
        stem = stemNames(stemIndex);
        previousComponent = phase27Components(phase27Components.rank == rank & ...
            phase27Components.condition == config.condition & ...
            phase27Components.stem == stem, :);
        if height(previousComponent) ~= 1
            error("ELEC5305:StemAttribution:Phase27Key", "Phase 2.7 component key mismatch.");
        end
        phase27Error = scalar_comparison_error(attribution.component_energy(stemIndex), ...
            previousComponent.rendered_error_energy);
        singletonRow = 2^(stemIndex - 1) + 1;
        hybridError = coalitionDirectErrors(singletonRow);
        if phase27Error > 1e-10 || hybridError > 1e-10
            error("ELEC5305:StemAttribution:Independent", ...
                "Independent validation failed for rank %d/%s/%s.", rank, config.condition, stem);
        end
        independentRowIndex = independentRowIndex + 1;
        independentRows{independentRowIndex} = struct( ...
            "rank", rank, "track", trackName, "condition", config.condition, ...
            "stem", stem, "reference_status", referenceStatus(stemIndex), ...
            "rendered_error_energy", attribution.component_energy(stemIndex), ...
            "oracle_energy", oracleEnergy, ...
            "single_stem_nre", attribution.single_stem_nre(stemIndex), ...
            "hybrid_validation_error", hybridError, ...
            "phase2_7_energy_validation_error", phase27Error);

        shapleyRowIndex = shapleyRowIndex + 1;
        shapleyRows{shapleyRowIndex} = struct( ...
            "rank", rank, "track", trackName, "condition", config.condition, ...
            "stem", stem, "reference_status", referenceStatus(stemIndex), ...
            "single_stem_nre", attribution.single_stem_nre(stemIndex), ...
            "shapley_nre", attribution.shapley_nre(stemIndex), ...
            "analytic_shapley_nre", attribution.analytic_shapley_nre(stemIndex), ...
            "shapley_validation_error", attribution.analytic_validation_error(stemIndex), ...
            "assigned_interaction_nre", attribution.assigned_interaction_nre(stemIndex), ...
            "interaction_identity_error", attribution.interaction_identity_error(stemIndex), ...
            "shapley_efficiency_error", attribution.efficiency_error, ...
            "oracle_energy", oracleEnergy, ...
            "full_coalition_value", attribution.full_coalition_value);
    end
    validationRows{conditionIndex} = struct( ...
        "condition", config.condition, ...
        "oracle_energy", oracleEnergy, ...
        "empty_coalition_value", attribution.empty_coalition_value, ...
        "empty_endpoint_status", "PASS", ...
        "full_endpoint_validation_error", fullEndpointError, ...
        "full_endpoint_status", "PASS", ...
        "coalition_direct_pass_count", sum(coalitionDirectErrors <= 1e-10), ...
        "coalition_direct_max_error", max(coalitionDirectErrors), ...
        "single_stem_hybrid_pass_count", sum(coalitionDirectErrors([2, 3, 5, 9]) <= 1e-10), ...
        "shapley_efficiency_error", attribution.efficiency_error, ...
        "shapley_efficiency_status", "PASS", ...
        "analytic_shapley_max_error", max(attribution.analytic_validation_error), ...
        "interaction_identity_max_error", max(attribution.interaction_identity_error), ...
        "input_frames", expectedInputFrames, ...
        "rendered_frames", size(oracleRaw, 1), ...
        "sample_rate_hz", sampleRate, ...
        "binaural_channel_order", ["left", "right"], ...
        "oracle_peak", max(abs(oracleRaw), [], "all"), ...
        "estimated_peak", max(abs(estimatedRaw), [], "all"), ...
        "all_arrays_finite", true);
end
independentTable = struct2table(vertcat(independentRows{:}));
coalitionTable = struct2table(vertcat(coalitionRows{:}));
shapleyTable = struct2table(vertcat(shapleyRows{:}));
validation = struct( ...
    "schema", "phase2_8_stem_attribution_validation_v1", ...
    "status", "PASS", "rank", rank, "track", trackName, ...
    "conditions", vertcat(validationRows{:}), ...
    "rank4_silent_vocals_included", rank == 4, ...
    "all_16_coalitions_directly_validated_per_condition", true, ...
    "phase_2_9_results_computed", false, ...
    "phase_2_10_results_computed", false);
end

function validate_excerpt_pair(oracle, estimated, expectedFrames, rank, trackName)
if oracle.sample_rate_hz ~= estimated.sample_rate_hz || ...
        oracle.frame_count ~= expectedFrames || estimated.frame_count ~= expectedFrames || ...
        oracle.start_frame_matlab_1_based ~= estimated.start_frame_matlab_1_based || ...
        oracle.end_frame_matlab_1_based_inclusive ~= estimated.end_frame_matlab_1_based_inclusive
    error("ELEC5305:StemAttribution:Alignment", ...
        "GT/estimated excerpt mismatch for rank %d %s.", rank, trackName);
end
end

function validate_matching_renders(errorResult, oracleRaw, estimatedRaw, oracleLookups, estimatedLookups, oracleDiagnostics, estimatedDiagnostics)
if ~isa(oracleRaw, "double") || ~isa(estimatedRaw, "double") || ...
        ~isequal(size(oracleRaw), size(estimatedRaw), size(errorResult.decomposed_residual)) || ...
        size(oracleRaw, 2) ~= 2 || any(~isfinite(oracleRaw), "all") || ...
        any(~isfinite(estimatedRaw), "all") || ...
        oracleDiagnostics.actual_output_frames ~= estimatedDiagnostics.actual_output_frames
    error("ELEC5305:StemAttribution:RendererAlignment", ...
        "Oracle/estimate/error render shape or integrity mismatch.");
end
fields = ["stem", "requested_azimuth_deg", "requested_elevation_deg", ...
    "matched_azimuth_deg", "matched_elevation_deg", "measurement_index", "angular_mismatch_deg"];
for row = 1:4
    for field = fields
        name = char(field);
        if ~isequal(errorResult.lookups(row).(name), oracleLookups(row).(name), estimatedLookups(row).(name))
            error("ELEC5305:StemAttribution:RendererLookup", ...
                "Oracle/estimate/error HRTF lookup mismatch.");
        end
    end
end
end

function configs = parse_spatial_conditions(protocol)
expectedNames = ["colocated", "moderate", "wide"];
expectedAzimuths = [0, 0, 0, 0; -30, -10, 10, 30; -80, -30, 30, 80];
conditions = protocol.spatial_conditions;
if numel(conditions) ~= 3
    error("ELEC5305:StemAttribution:Spatial", "Expected three conditions.");
end
configs = repmat(struct(), 3, 1);
for index = 1:3
    name = string(conditions(index).condition);
    azimuths = double(conditions(index).azimuths_deg(:)).';
    order = string(conditions(index).source_order(:)).';
    if name ~= expectedNames(index) || ~isequal(azimuths, expectedAzimuths(index, :)) || ...
            ~isequal(order, ["bass", "vocals", "drums", "other"])
        error("ELEC5305:StemAttribution:Spatial", "Frozen condition mismatch.");
    end
    configs(index).condition = name;
    configs(index).stem_order = order;
    configs(index).azimuths_deg = azimuths;
    configs(index).elevation_deg = double(protocol.hrtf.elevation_deg);
end
end

function validate_mechanism_attribution(mechanism, configs)
conditions = mechanism.frozen_inputs.canonical_conditions;
players = string(mechanism.rq4_attribution.exact_shapley.players(:)).';
if numel(conditions) ~= 3 || ~isequal(players, ["bass", "vocals", "drums", "other"]) || ...
        mechanism.rq4_attribution.exact_shapley.coalition_count ~= 16 || ...
        logical(mechanism.rq4_attribution.exact_shapley.monte_carlo)
    error("ELEC5305:StemAttribution:MechanismConfig", "Frozen RQ4 definition mismatch.");
end
for index = 1:3
    if string(conditions(index).condition) ~= configs(index).condition || ...
            ~isequal(double(conditions(index).azimuths_deg(:)).', configs(index).azimuths_deg)
        error("ELEC5305:StemAttribution:MechanismConfig", ...
            "Mechanism/static canonical conditions differ.");
    end
end
caseStudy = mechanism.rq4_attribution.rank4_silent_reference;
if caseStudy.rank ~= 4 || string(caseStudy.track) ~= "Skelpolu - Resurrection" || ...
        string(caseStudy.stem) ~= "vocals" || ~logical(caseStudy.pre_registered_case_study)
    error("ELEC5305:StemAttribution:MechanismConfig", "Frozen rank-4 case mismatch.");
end
end

function valid = validate_track_completion(completionPath, trackOutput, rank, trackName, mechanismHash, staticHash, manifestHash)
valid = false;
try
    if ~isfile(completionPath), return; end
    completion = jsondecode(fileread(completionPath));
    independentPath = fullfile(trackOutput, "independent_attribution.csv");
    coalitionPath = fullfile(trackOutput, "coalition_values.csv");
    shapleyPath = fullfile(trackOutput, "shapley_attribution.csv");
    validationPath = fullfile(trackOutput, "validation.json");
    if string(completion.status) ~= "COMPLETE" || completion.rank ~= rank || ...
            string(completion.track) ~= trackName || ...
            string(completion.mechanism_protocol_sha256) ~= mechanismHash || ...
            string(completion.static_protocol_sha256) ~= staticHash || ...
            string(completion.manifest_sha256) ~= manifestHash || ...
            completion.independent_rows ~= 12 || completion.coalition_rows ~= 48 || ...
            completion.shapley_rows ~= 12 || ...
            ~all(isfile([string(independentPath), string(coalitionPath), string(shapleyPath), string(validationPath)])) || ...
            string(completion.independent_sha256) ~= compute_sha256(independentPath) || ...
            string(completion.coalition_sha256) ~= compute_sha256(coalitionPath) || ...
            string(completion.shapley_sha256) ~= compute_sha256(shapleyPath) || ...
            string(completion.validation_sha256) ~= compute_sha256(validationPath)
        return;
    end
    independent = readtable(independentPath, "TextType", "string");
    coalitions = readtable(coalitionPath, "TextType", "string");
    shapley = readtable(shapleyPath, "TextType", "string");
    valid = height(independent) == 12 && height(coalitions) == 48 && height(shapley) == 12 && ...
        all(independent.hybrid_validation_error <= 1e-10) && ...
        all(independent.phase2_7_energy_validation_error <= 1e-10) && ...
        all(coalitions.direct_reconstruction_error <= 1e-10) && ...
        all(shapley.shapley_validation_error <= 1e-10) && ...
        all(shapley.interaction_identity_error <= 1e-10) && ...
        all(shapley.shapley_efficiency_error <= 1e-10);
catch
    valid = false;
end
end

function cleanup_partial_track(trackOutput)
names = ["independent_attribution.csv", "coalition_values.csv", ...
    "shapley_attribution.csv", "validation.json", "completion.json"];
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
        error("ELEC5305:StemAttribution:MissingTrackOutput", ...
            "Missing %s for %s.", fileName, trackName);
    end
    tables{index} = readtable(pathValue, "TextType", "string");
end
aggregate = vertcat(tables{:});
aggregate.condition_order_internal = categorical(aggregate.condition, ...
    ["colocated", "moderate", "wide"], "Ordinal", true);
sortVariables = ["rank", "condition_order_internal"];
if ismember("stem", string(aggregate.Properties.VariableNames))
    aggregate.stem_order_internal = categorical(aggregate.stem, ...
        ["bass", "vocals", "drums", "other"], "Ordinal", true);
    sortVariables(end + 1) = "stem_order_internal";
elseif ismember("coalition_id", string(aggregate.Properties.VariableNames))
    sortVariables(end + 1) = "coalition_id";
end
aggregate = sortrows(aggregate, sortVariables);
if ismember("stem_order_internal", string(aggregate.Properties.VariableNames))
    aggregate.stem_order_internal = [];
end
aggregate.condition_order_internal = [];
end

function validate_aggregates(independent, coalitions, shapley)
if height(independent) ~= 120 || height(coalitions) ~= 480 || height(shapley) ~= 120 || ...
        any(~isfinite(independent.rendered_error_energy)) || ...
        any(~isfinite(independent.oracle_energy)) || any(independent.oracle_energy <= 0) || ...
        any(~isfinite(independent.single_stem_nre)) || any(independent.single_stem_nre < 0) || ...
        any(independent.hybrid_validation_error > 1e-10) || ...
        any(independent.phase2_7_energy_validation_error > 1e-10) || ...
        any(~isfinite(coalitions.normalized_error_value)) || ...
        any(coalitions.normalized_error_value < 0) || ...
        any(coalitions.direct_reconstruction_error > 1e-10) || ...
        any(~isfinite(shapley.shapley_nre)) || ...
        any(~isfinite(shapley.analytic_shapley_nre)) || ...
        any(shapley.shapley_validation_error > 1e-10) || ...
        any(shapley.interaction_identity_error > 1e-10) || ...
        any(shapley.shapley_efficiency_error > 1e-10)
    error("ELEC5305:StemAttribution:Aggregate", ...
        "Aggregate row-count, finite-value, or numerical gate failed.");
end
independentKeys = unique(independent(:, ["rank", "condition", "stem"]), "rows");
shapleyKeys = unique(shapley(:, ["rank", "condition", "stem"]), "rows");
coalitionKeys = unique(coalitions(:, ["rank", "condition", "coalition_id"]), "rows");
if height(independentKeys) ~= 120 || height(shapleyKeys) ~= 120 || height(coalitionKeys) ~= 480
    error("ELEC5305:StemAttribution:Duplicate", "Duplicate attribution keys detected.");
end
inactiveIndependent = independent(independent.reference_status == "INACTIVE_REFERENCE", :);
inactiveShapley = shapley(shapley.reference_status == "INACTIVE_REFERENCE", :);
if height(inactiveIndependent) ~= 3 || height(inactiveShapley) ~= 3 || ...
        any(inactiveIndependent.rank ~= 4) || any(inactiveIndependent.stem ~= "vocals") || ...
        any(~isfinite(inactiveIndependent.single_stem_nre)) || ...
        any(~isfinite(inactiveShapley.shapley_nre))
    error("ELEC5305:StemAttribution:Rank4", "Rank 4 silent-vocals aggregate gate failed.");
end
end

function value = scalar_comparison_error(actual, expected)
scale = max(abs(actual), abs(expected));
if scale == 0
    value = abs(actual - expected);
else
    value = abs(actual - expected) / scale;
end
end

function value = vector_comparison_error(actual, expected)
differenceNorm = sqrt(sum((actual - expected) .^ 2, "all"));
expectedNorm = sqrt(sum(expected .^ 2, "all"));
if expectedNorm == 0
    value = differenceNorm;
else
    value = differenceNorm / expectedNorm;
end
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
    error("ELEC5305:StemAttribution:WriteJSON", "Cannot write %s.", temporary);
end
cleanupFile = onCleanup(@() fclose(fid));
fprintf(fid, "%s\n", jsonText);
clear cleanupFile;
movefile(temporary, outputPath, "f");
end

function sha256 = compute_sha256(filePath)
fid = fopen(filePath, "rb");
if fid < 0
    error("ELEC5305:StemAttribution:HashRead", "Cannot open %s.", filePath);
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

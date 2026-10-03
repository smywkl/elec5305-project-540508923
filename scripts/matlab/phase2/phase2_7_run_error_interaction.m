%% Phase 2.7 - Cross-stem error interaction and cancellation mechanism

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
    error("ELEC5305:ErrorInteraction:FrozenHash", ...
        "Mechanism/static/manifest/SOFA frozen SHA-256 mismatch.");
end

mechanism = jsondecode(fileread(mechanismProtocolPath));
protocol = jsondecode(fileread(staticProtocolPath));
manifest = jsondecode(fileread(manifestPath));
selectedTracks = manifest.selected_tracks;
if string(mechanism.protocol_version) ~= "1.0" || ...
        string(protocol.protocol_version) ~= "1.1" || ...
        numel(selectedTracks) ~= 10 || manifest.selected_track_count ~= 10
    error("ELEC5305:ErrorInteraction:FrozenConfig", ...
        "Frozen protocol or manifest structure mismatch.");
end

sampleRate = double(protocol.excerpt.sample_rate_hz);
excerptStartSeconds = double(protocol.excerpt.start_seconds);
excerptDurationSeconds = double(protocol.excerpt.duration_seconds);
expectedInputFrames = double(protocol.excerpt.frames);
maximumDirectionMismatchDeg = double(protocol.hrtf.maximum_direction_mismatch_deg);
if sampleRate ~= 44100 || excerptStartSeconds ~= 30 || ...
        excerptDurationSeconds ~= 30 || expectedInputFrames ~= 1323000
    error("ELEC5305:ErrorInteraction:FrozenExcerpt", "Frozen excerpt mismatch.");
end
conditionConfigs = parse_spatial_conditions(protocol);
validate_mechanism_conditions(mechanism, conditionConfigs);

subject = load_cipic_subject(sofaPath);
if subject.fs ~= sampleRate || size(subject.hrir, 3) ~= 200 || ...
        ~isequal(string(subject.receiver_order), ["left", "right"])
    error("ELEC5305:ErrorInteraction:HRTF", ...
        "Frozen HRTF sample rate, length, or channel order mismatch.");
end

outputRoot = fullfile(repoRoot, "outputs", "phase2", "phase2_7_error_interaction");
metricsRoot = fullfile(outputRoot, "metrics");
tracksRoot = fullfile(outputRoot, "tracks");
logsRoot = fullfile(outputRoot, "logs");
mkdir_if_missing(metricsRoot);
mkdir_if_missing(tracksRoot);
mkdir_if_missing(logsRoot);
diaryPath = fullfile(logsRoot, "matlab_phase2_7.log");
diary(diaryPath);
cleanupDiary = onCleanup(@() diary("off"));

displayPolicy = struct( ...
    "frozen_before_official_results_aggregation", true, ...
    "paired_trajectory_individual_n", 10, ...
    "aggregate_marker", "median across songs", ...
    "summary_statistics", ["mean", "median", "sample SD", "IQR", "min", "max"], ...
    "pairwise_heatmap_cell", "median normalized J_ij across 10 songs", ...
    "pairwise_colour_scale", "shared symmetric zero-centered [-M,+M]");

phase25Path = fullfile(repoRoot, "outputs", "phase2", "phase2_5_final", ...
    "metrics", "downstream_metrics_per_condition.csv");
if ~isfile(phase25Path)
    error("ELEC5305:ErrorInteraction:Phase25", ...
        "Phase 2.5 downstream aggregate is missing.");
end
phase25 = readtable(phase25Path, "TextType", "string");
if height(phase25) ~= 30
    error("ELEC5305:ErrorInteraction:Phase25", ...
        "Phase 2.5 downstream aggregate must contain 30 rows.");
end

perTrackRuntime = zeros(10, 1);
cacheTrackCount = 0;
cacheStemCount = 0;
for trackIndex = 1:10
    track = selectedTracks(trackIndex);
    rank = double(track.rank);
    trackName = string(track.track_name_original);
    if rank ~= trackIndex
        error("ELEC5305:ErrorInteraction:Rank", "Manifest rank/order mismatch.");
    end
    fprintf("[%d/10] %s\n", rank, trackName);
    trackStarted = tic;
    trackDirectory = fullfile(repoRoot, string(track.dataset_relative_path));
    cacheDirectory = fullfile(repoRoot, "outputs", "phase2", "phase2_5_final", ...
        "cache", "htdemucs_ft", trackName);
    cacheCompletionPath = fullfile(cacheDirectory, "completion.json");

    % Loading before the resume decision revalidates all 10 caches and all
    % 40 cached stem hashes on every invocation without rerunning HTDemucs.
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
        fprintf("  SKIPPED_COMPLETE (cache revalidated)\n");
        continue;
    end

    mkdir_if_missing(trackOutput);
    cleanup_partial_track(trackOutput);
    [metricsTable, componentTable, pairwiseTable, validation] = process_track( ...
        rank, trackName, oracleExcerpt, estimatedExcerpt, subject, conditionConfigs, ...
        sampleRate, expectedInputFrames, maximumDirectionMismatchDeg);

    metricsPath = fullfile(trackOutput, "error_interaction_metrics.csv");
    componentPath = fullfile(trackOutput, "rendered_error_energy_per_stem.csv");
    pairwisePath = fullfile(trackOutput, "pairwise_interactions.csv");
    validationPath = fullfile(trackOutput, "validation.json");
    atomic_writetable(metricsTable, metricsPath);
    atomic_writetable(componentTable, componentPath);
    atomic_writetable(pairwiseTable, pairwisePath);
    atomic_write_json(validationPath, validation);

    runtimeSeconds = toc(trackStarted);
    perTrackRuntime(rank) = runtimeSeconds;
    completion = struct( ...
        "schema", "phase2_7_error_interaction_completion_v1", ...
        "status", "COMPLETE", ...
        "rank", rank, ...
        "track", trackName, ...
        "mechanism_protocol_sha256", mechanismHash, ...
        "static_protocol_sha256", staticHash, ...
        "manifest_sha256", manifestHash, ...
        "cache_completion_sha256", compute_sha256(cacheCompletionPath), ...
        "metrics_rows", height(metricsTable), ...
        "component_rows", height(componentTable), ...
        "pairwise_rows", height(pairwiseTable), ...
        "runtime_seconds", runtimeSeconds, ...
        "metrics_sha256", compute_sha256(metricsPath), ...
        "component_sha256", compute_sha256(componentPath), ...
        "pairwise_sha256", compute_sha256(pairwisePath), ...
        "validation_sha256", compute_sha256(validationPath));
    atomic_write_json(completionPath, completion); % Must be last.
    fprintf("  COMPLETE runtime %.3f s\n", runtimeSeconds);
end

metricsAggregate = collect_track_tables(selectedTracks, tracksRoot, ...
    "error_interaction_metrics.csv");
componentAggregate = collect_track_tables(selectedTracks, tracksRoot, ...
    "rendered_error_energy_per_stem.csv");
pairwiseAggregate = collect_track_tables(selectedTracks, tracksRoot, ...
    "pairwise_interactions.csv");
validate_aggregates(metricsAggregate, componentAggregate, pairwiseAggregate, phase25);

metricsPath = fullfile(metricsRoot, "error_interaction_per_song_condition.csv");
componentPath = fullfile(metricsRoot, "rendered_error_energy_per_stem.csv");
pairwisePath = fullfile(metricsRoot, "pairwise_error_interactions.csv");
atomic_writetable(metricsAggregate, metricsPath);
atomic_writetable(componentAggregate, componentPath);
atomic_writetable(pairwiseAggregate, pairwisePath);

summary = struct();
summary.schema = "phase2_7_matlab_error_interaction_summary_v1";
summary.status = "MATLAB_COMPLETE";
summary.mechanism_protocol_version = string(mechanism.protocol_version);
summary.mechanism_protocol_sha256 = mechanismHash;
summary.static_protocol_sha256 = staticHash;
summary.manifest_sha256 = manifestHash;
summary.sofa_sha256 = sofaHash;
summary.cache_valid_tracks = cacheTrackCount;
summary.cache_valid_stems = cacheStemCount;
summary.song_condition_rows = height(metricsAggregate);
summary.component_rows = height(componentAggregate);
summary.pairwise_rows = height(pairwiseAggregate);
summary.direct_decomposition_pass_count = sum(metricsAggregate.direct_decomposition_relerr <= 1e-10);
summary.direct_decomposition_max_relerr = max(metricsAggregate.direct_decomposition_relerr);
summary.energy_identity_pass_count = sum(metricsAggregate.energy_identity_relerr <= 1e-10);
summary.energy_identity_max_relerr = max(metricsAggregate.energy_identity_relerr);
summary.phase25_key_match_count = 30;
summary.per_track_runtime_seconds = perTrackRuntime;
summary.sum_per_track_runtime_seconds = sum(perTrackRuntime);
summary.this_invocation_wall_seconds = toc(overallStarted);
summary.display_policy = displayPolicy;
summary.matlab_version = version;
summary.matlab_architecture = computer("arch");
toolboxInfo = ver;
summary.available_toolboxes = string({toolboxInfo.Name});
summary.phase_2_8_results_computed = false;
summary.phase_2_9_results_computed = false;
summary.phase_2_10_results_computed = false;
atomic_write_json(fullfile(metricsRoot, "matlab_error_interaction_summary.json"), summary);
fprintf("PHASE2_7_MATLAB_COMPLETE tracks=%d metrics=%d components=%d pairs=%d\n", ...
    cacheTrackCount, height(metricsAggregate), height(componentAggregate), height(pairwiseAggregate));

function [metricsTable, componentTable, pairwiseTable, validation] = process_track(rank, trackName, oracleExcerpt, estimatedExcerpt, subject, configs, sampleRate, expectedInputFrames, maxMismatch)
stemNames = ["bass", "vocals", "drums", "other"];
errors = struct();
referenceStatus = strings(4, 1);
for stemIndex = 1:4
    fieldName = char(stemNames(stemIndex));
    gt = double(oracleExcerpt.mono.(fieldName));
    estimate = double(estimatedExcerpt.mono.(fieldName));
    errors.(fieldName) = estimate - gt;
    gtEnergy = sum(gt .^ 2);
    if gtEnergy == 0
        referenceStatus(stemIndex) = "INACTIVE_REFERENCE";
    else
        referenceStatus(stemIndex) = "ACTIVE";
    end
end
if rank == 4
    vocalsIndex = find(stemNames == "vocals", 1);
    if trackName ~= "Skelpolu - Resurrection" || ...
            referenceStatus(vocalsIndex) ~= "INACTIVE_REFERENCE" || ...
            sum(estimatedExcerpt.mono.vocals .^ 2) <= 0
        error("ELEC5305:ErrorInteraction:Rank4", ...
            "Rank 4 silent-reference vocals invariant failed.");
    end
elseif any(referenceStatus ~= "ACTIVE")
    error("ELEC5305:ErrorInteraction:ReferenceStatus", ...
        "Unexpected inactive GT reference for rank %d.", rank);
end

metricRows = cell(3, 1);
componentRows = cell(12, 1);
pairRows = cell(18, 1);
validationRows = cell(3, 1);
componentRowIndex = 0;
pairRowIndex = 0;
for conditionIndex = 1:3
    config = configs(conditionIndex);
    errorResult = compute_rendered_error_components(errors, subject, ...
        config.condition, config.azimuths_deg, config.elevation_deg, maxMismatch);
    [oracleRaw, oracleLookups, oracleDiagnostics] = render_stem_mix( ...
        oracleExcerpt.mono, subject, config.condition, config.azimuths_deg, ...
        config.elevation_deg, maxMismatch);
    [estimatedRaw, estimatedLookups, estimatedDiagnostics] = render_stem_mix( ...
        estimatedExcerpt.mono, subject, config.condition, config.azimuths_deg, ...
        config.elevation_deg, maxMismatch);
    validate_matching_renders(errorResult, oracleRaw, estimatedRaw, ...
        oracleLookups, estimatedLookups, oracleDiagnostics, estimatedDiagnostics);

    directResidual = estimatedRaw - oracleRaw;
    directEnergy = sum(directResidual .^ 2, "all");
    if directEnergy == 0
        error("ELEC5305:ErrorInteraction:ZeroDirectResidual", ...
            "Direct residual is exactly zero for rank %d/%s.", rank, config.condition);
    end
    directRelerr = sqrt(sum((directResidual - errorResult.decomposed_residual) .^ 2, "all") / directEnergy);
    if directRelerr > 1e-10
        error("ELEC5305:ErrorInteraction:DirectIdentity", ...
            "Direct/decomposed identity failed for rank %d/%s: %.17g.", ...
            rank, config.condition, directRelerr);
    end
    values = [errorResult.A_individual_error_energy, ...
        errorResult.T_total_error_energy, errorResult.I_interaction_energy, ...
        errorResult.error_retention_ratio, errorResult.cancellation_gain_db, ...
        directRelerr, errorResult.energy_identity_relerr];
    if any(~isfinite(values)) || any(values([1, 2, 4]) <= 0)
        error("ELEC5305:ErrorInteraction:Finite", ...
            "Nonfinite or nonpositive primary value for rank %d/%s.", rank, config.condition);
    end

    metricRows{conditionIndex} = struct( ...
        "rank", rank, "track", trackName, "condition", config.condition, ...
        "A_individual_error_energy", errorResult.A_individual_error_energy, ...
        "T_total_error_energy", errorResult.T_total_error_energy, ...
        "I_interaction_energy", errorResult.I_interaction_energy, ...
        "error_retention_ratio", errorResult.error_retention_ratio, ...
        "cancellation_gain_db", errorResult.cancellation_gain_db, ...
        "direct_decomposition_relerr", directRelerr, ...
        "energy_identity_relerr", errorResult.energy_identity_relerr, ...
        "sample_rate_hz", sampleRate, ...
        "input_frames", expectedInputFrames, ...
        "rendered_frames", size(directResidual, 1));

    for stemIndex = 1:4
        componentRowIndex = componentRowIndex + 1;
        componentRows{componentRowIndex} = struct( ...
            "rank", rank, "track", trackName, "condition", config.condition, ...
            "stem", stemNames(stemIndex), ...
            "reference_status", referenceStatus(stemIndex), ...
            "rendered_error_energy", errorResult.component_energy(stemIndex));
    end
    for pairIndex = 1:6
        pairRowIndex = pairRowIndex + 1;
        pairRows{pairRowIndex} = struct( ...
            "rank", rank, "track", trackName, "condition", config.condition, ...
            "stem_i", errorResult.pair_stem_i(pairIndex), ...
            "stem_j", errorResult.pair_stem_j(pairIndex), ...
            "interaction_energy", errorResult.pair_interaction_energy(pairIndex), ...
            "normalized_interaction", errorResult.pair_normalized_interaction(pairIndex), ...
            "cosine_alignment", errorResult.pair_cosine_alignment(pairIndex), ...
            "cosine_status", errorResult.pair_cosine_status(pairIndex));
    end
    validationRows{conditionIndex} = struct( ...
        "condition", config.condition, ...
        "direct_decomposition_relerr", directRelerr, ...
        "direct_decomposition_status", "PASS", ...
        "energy_identity_relerr", errorResult.energy_identity_relerr, ...
        "energy_identity_status", "PASS", ...
        "input_frames", expectedInputFrames, ...
        "rendered_frames", size(directResidual, 1), ...
        "sample_rate_hz", sampleRate, ...
        "binaural_channel_order", ["left", "right"], ...
        "oracle_peak", max(abs(oracleRaw), [], "all"), ...
        "estimated_peak", max(abs(estimatedRaw), [], "all"), ...
        "direct_residual_peak", max(abs(directResidual), [], "all"), ...
        "all_arrays_finite", true);
end
metricsTable = struct2table(vertcat(metricRows{:}));
componentTable = struct2table(vertcat(componentRows{:}));
pairwiseTable = struct2table(vertcat(pairRows{:}));
validation = struct( ...
    "schema", "phase2_7_error_interaction_validation_v1", ...
    "status", "PASS", "rank", rank, "track", trackName, ...
    "conditions", vertcat(validationRows{:}), ...
    "rank4_silent_vocals_included", rank == 4, ...
    "phase_2_8_results_computed", false, ...
    "phase_2_9_results_computed", false, ...
    "phase_2_10_results_computed", false);
end

function validate_excerpt_pair(oracle, estimated, expectedFrames, rank, trackName)
if oracle.sample_rate_hz ~= estimated.sample_rate_hz || ...
        oracle.frame_count ~= expectedFrames || estimated.frame_count ~= expectedFrames || ...
        oracle.start_frame_matlab_1_based ~= estimated.start_frame_matlab_1_based || ...
        oracle.end_frame_matlab_1_based_inclusive ~= estimated.end_frame_matlab_1_based_inclusive
    error("ELEC5305:ErrorInteraction:Alignment", ...
        "GT/estimated excerpt mismatch for rank %d %s.", rank, trackName);
end
end

function validate_matching_renders(errorResult, oracleRaw, estimatedRaw, oracleLookups, estimatedLookups, oracleDiagnostics, estimatedDiagnostics)
if ~isa(oracleRaw, "double") || ~isa(estimatedRaw, "double") || ...
        ~isequal(size(oracleRaw), size(estimatedRaw), size(errorResult.decomposed_residual)) || ...
        size(oracleRaw, 2) ~= 2 || any(~isfinite(oracleRaw), "all") || ...
        any(~isfinite(estimatedRaw), "all") || ...
        oracleDiagnostics.actual_output_frames ~= estimatedDiagnostics.actual_output_frames
    error("ELEC5305:ErrorInteraction:RendererAlignment", ...
        "Oracle/estimate/error render shape or integrity mismatch.");
end
fields = ["stem", "requested_azimuth_deg", "requested_elevation_deg", ...
    "matched_azimuth_deg", "matched_elevation_deg", "measurement_index", "angular_mismatch_deg"];
for row = 1:4
    for field = fields
        name = char(field);
        if ~isequal(errorResult.lookups(row).(name), oracleLookups(row).(name), estimatedLookups(row).(name))
            error("ELEC5305:ErrorInteraction:RendererLookup", ...
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
    error("ELEC5305:ErrorInteraction:Spatial", "Expected three conditions.");
end
configs = repmat(struct(), 3, 1);
for index = 1:3
    name = string(conditions(index).condition);
    azimuths = double(conditions(index).azimuths_deg(:)).';
    order = string(conditions(index).source_order(:)).';
    if name ~= expectedNames(index) || ~isequal(azimuths, expectedAzimuths(index, :)) || ...
            ~isequal(order, ["bass", "vocals", "drums", "other"])
        error("ELEC5305:ErrorInteraction:Spatial", "Frozen condition mismatch.");
    end
    configs(index).condition = name;
    configs(index).stem_order = order;
    configs(index).azimuths_deg = azimuths;
    configs(index).elevation_deg = double(protocol.hrtf.elevation_deg);
end
end

function validate_mechanism_conditions(mechanism, configs)
conditions = mechanism.frozen_inputs.canonical_conditions;
if numel(conditions) ~= 3 || ...
        ~isequal(string(mechanism.frozen_inputs.source_order(:)).', ["bass", "vocals", "drums", "other"])
    error("ELEC5305:ErrorInteraction:MechanismConfig", ...
        "Mechanism source order or condition count mismatch.");
end
for index = 1:3
    if string(conditions(index).condition) ~= configs(index).condition || ...
            ~isequal(double(conditions(index).azimuths_deg(:)).', configs(index).azimuths_deg)
        error("ELEC5305:ErrorInteraction:MechanismConfig", ...
            "Mechanism/static canonical conditions differ.");
    end
end
end

function valid = validate_track_completion(completionPath, trackOutput, rank, trackName, mechanismHash, staticHash, manifestHash)
valid = false;
try
    if ~isfile(completionPath), return; end
    completion = jsondecode(fileread(completionPath));
    metricsPath = fullfile(trackOutput, "error_interaction_metrics.csv");
    componentPath = fullfile(trackOutput, "rendered_error_energy_per_stem.csv");
    pairwisePath = fullfile(trackOutput, "pairwise_interactions.csv");
    validationPath = fullfile(trackOutput, "validation.json");
    if string(completion.status) ~= "COMPLETE" || completion.rank ~= rank || ...
            string(completion.track) ~= trackName || ...
            string(completion.mechanism_protocol_sha256) ~= mechanismHash || ...
            string(completion.static_protocol_sha256) ~= staticHash || ...
            string(completion.manifest_sha256) ~= manifestHash || ...
            completion.metrics_rows ~= 3 || completion.component_rows ~= 12 || ...
            completion.pairwise_rows ~= 18 || ...
            ~all(isfile([string(metricsPath), string(componentPath), string(pairwisePath), string(validationPath)])) || ...
            string(completion.metrics_sha256) ~= compute_sha256(metricsPath) || ...
            string(completion.component_sha256) ~= compute_sha256(componentPath) || ...
            string(completion.pairwise_sha256) ~= compute_sha256(pairwisePath) || ...
            string(completion.validation_sha256) ~= compute_sha256(validationPath)
        return;
    end
    metrics = readtable(metricsPath, "TextType", "string");
    components = readtable(componentPath, "TextType", "string");
    pairs = readtable(pairwisePath, "TextType", "string");
    valid = height(metrics) == 3 && height(components) == 12 && height(pairs) == 18 && ...
        isequal(string(metrics.condition).', ["colocated", "moderate", "wide"]) && ...
        all(metrics.direct_decomposition_relerr <= 1e-10) && ...
        all(metrics.energy_identity_relerr <= 1e-10);
catch
    valid = false;
end
end

function cleanup_partial_track(trackOutput)
names = ["error_interaction_metrics.csv", "rendered_error_energy_per_stem.csv", ...
    "pairwise_interactions.csv", "validation.json", "completion.json"];
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
        error("ELEC5305:ErrorInteraction:MissingTrackOutput", ...
            "Missing %s for %s.", fileName, trackName);
    end
    tables{index} = readtable(pathValue, "TextType", "string");
end
aggregate = vertcat(tables{:});
conditionOrder = categorical(aggregate.condition, ["colocated", "moderate", "wide"], "Ordinal", true);
aggregate.condition_order_internal = conditionOrder;
aggregate = sortrows(aggregate, ["rank", "condition_order_internal"]);
aggregate.condition_order_internal = [];
end

function validate_aggregates(metrics, components, pairs, phase25)
if height(metrics) ~= 30 || height(components) ~= 120 || height(pairs) ~= 180 || ...
        numel(unique(metrics.rank)) ~= 10 || ...
        any(~isfinite(metrics.A_individual_error_energy)) || ...
        any(~isfinite(metrics.T_total_error_energy)) || ...
        any(~isfinite(metrics.I_interaction_energy)) || ...
        any(~isfinite(metrics.error_retention_ratio)) || ...
        any(~isfinite(metrics.cancellation_gain_db)) || ...
        any(metrics.A_individual_error_energy <= 0) || ...
        any(metrics.T_total_error_energy <= 0) || ...
        any(metrics.error_retention_ratio <= 0) || ...
        any(metrics.direct_decomposition_relerr > 1e-10) || ...
        any(metrics.energy_identity_relerr > 1e-10) || ...
        any(~isfinite(components.rendered_error_energy)) || ...
        any(components.rendered_error_energy < 0) || ...
        any(~isfinite(pairs.interaction_energy)) || ...
        any(~isfinite(pairs.normalized_interaction))
    error("ELEC5305:ErrorInteraction:Aggregate", ...
        "Aggregate row-count, finite-value, or numerical gate failed.");
end
metricKeys = sortrows(metrics(:, ["rank", "track", "condition"]), ["rank", "condition"]);
phase25Keys = sortrows(phase25(:, ["rank", "track", "condition"]), ["rank", "condition"]);
if ~isequal(metricKeys, phase25Keys)
    error("ELEC5305:ErrorInteraction:Phase25Keys", ...
        "Phase 2.7 keys do not exactly match Phase 2.5 keys.");
end
inactive = components(components.reference_status == "INACTIVE_REFERENCE", :);
if height(inactive) ~= 3 || any(inactive.rank ~= 4) || ...
        any(inactive.track ~= "Skelpolu - Resurrection") || any(inactive.stem ~= "vocals")
    error("ELEC5305:ErrorInteraction:InactiveReference", ...
        "Rank 4 silent-vocals component audit mismatch.");
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
    error("ELEC5305:ErrorInteraction:WriteJSON", "Cannot write %s.", temporary);
end
cleanupFile = onCleanup(@() fclose(fid));
fprintf(fid, "%s\n", jsonText);
clear cleanupFile;
movefile(temporary, outputPath, "f");
end

function sha256 = compute_sha256(filePath)
fid = fopen(filePath, "rb");
if fid < 0
    error("ELEC5305:ErrorInteraction:HashRead", "Cannot open %s.", filePath);
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

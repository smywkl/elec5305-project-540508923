%% Phase 2.11b - Source-position assignment sensitivity decomposition

oldPath = path;
cleanupPath = onCleanup(@() path(oldPath));
scriptPath = mfilename("fullpath");
repoRoot = fileparts(fileparts(fileparts(fileparts(scriptPath))));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "comparison"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "hrtf"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "oracle"));

overallStarted = tic;
assignmentProtocolPath = fullfile(repoRoot, "config", "phase2", "assignment_sensitivity_protocol.json");
mechanismProtocolPath = fullfile(repoRoot, "config", "phase2", "mechanism_analysis_protocol.json");
staticProtocolPath = fullfile(repoRoot, "config", "phase2", "static_experiment_protocol.json");
manifestPath = fullfile(repoRoot, "config", "phase2", "final_test_manifest.json");
sofaPath = fullfile(repoRoot, "data", "hrtf", "cipic", "subject_003.sofa");
phase210MetricsRoot = fullfile(repoRoot, "outputs", "phase2", "phase2_10_robustness", "metrics");
phase210AssignmentsPath = fullfile(phase210MetricsRoot, "position_assignment_permutations.csv");
phase210SummaryPath = fullfile(phase210MetricsRoot, "position_assignment_summary.csv");

expectedAssignmentHash = "af00574148d767e57d3e096a53e9800f47c0fe3a53b7029c603cf2bdca81866f";
expectedMechanismHash = "3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0";
expectedStaticHash = "3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3";
expectedManifestHash = "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc";
expectedSofaHash = "a9db5f938ed1113b118dcbeb43f5fe1b27b9e191d1bbdb63fbc4803b6959b220";
expectedPhase210AssignmentHash = "5540793b7d41b2c4652c545c2ded4e0f9787c0e070912d69302bdf9387c76ad9";
expectedPhase210InputPaths = [ ...
    fullfile(phase210MetricsRoot, "position_assignment_permutations.csv"), ...
    fullfile(phase210MetricsRoot, "common_hrtf_controls.csv"), ...
    fullfile(phase210MetricsRoot, "common_hrtf_per_song_summary.csv"), ...
    fullfile(phase210MetricsRoot, "position_assignment_summary.csv"), ...
    fullfile(phase210MetricsRoot, "assignment_robustness_summary.csv")];
expectedPhase210InputHashes = [ ...
    "5540793b7d41b2c4652c545c2ded4e0f9787c0e070912d69302bdf9387c76ad9", ...
    "a425ead00a89289c831e7a22f66b0b1a98315b7512d35cf1dcac40083ae98ce7", ...
    "b7261fdeaab10fc2afc17de525fff62bdbb92165bd523f71f1a073cefaaadbaf", ...
    "e5dac6103da6a7ea0540b67b012394fcaa43bb4d373f137bc3a470e5a758d588", ...
    "31746ff5e2916e73a3fbca6f84158888c4a2555c3f6c9d274d53120a20700a57"];

outputRoot = fullfile(repoRoot, "outputs", "phase2", "phase2_11_assignment_sensitivity");
metricsRoot = fullfile(outputRoot, "metrics");
tracksRoot = fullfile(outputRoot, "tracks");
logsRoot = fullfile(outputRoot, "logs");
figuresRoot = fullfile(outputRoot, "figures");
mkdir_if_missing(metricsRoot);
mkdir_if_missing(tracksRoot);
mkdir_if_missing(logsRoot);
mkdir_if_missing(figuresRoot);
diaryPath = fullfile(logsRoot, "matlab_phase2_11b.log");
diary(diaryPath);
cleanupDiary = onCleanup(@() diary("off"));

fprintf("PHASE2_11B_START\n");
assignmentHash = compute_sha256(assignmentProtocolPath);
mechanismHash = compute_sha256(mechanismProtocolPath);
staticHash = compute_sha256(staticProtocolPath);
manifestHash = compute_sha256(manifestPath);
sofaHash = compute_sha256(sofaPath);
if assignmentHash ~= expectedAssignmentHash || mechanismHash ~= expectedMechanismHash || ...
        staticHash ~= expectedStaticHash || manifestHash ~= expectedManifestHash || ...
        sofaHash ~= expectedSofaHash
    error("ELEC5305:AssignmentSensitivity:FrozenHash", ...
        "Assignment/mechanism/static/manifest/SOFA frozen SHA-256 mismatch.");
end
for inputIndex = 1:numel(expectedPhase210InputPaths)
    if compute_sha256(expectedPhase210InputPaths(inputIndex)) ~= expectedPhase210InputHashes(inputIndex)
        error("ELEC5305:AssignmentSensitivity:Phase210Hash", ...
            "Frozen Phase 2.10 input hash mismatch: %s", expectedPhase210InputPaths(inputIndex));
    end
end

assignmentProtocol = jsondecode(fileread(assignmentProtocolPath));
staticProtocol = jsondecode(fileread(staticProtocolPath));
manifest = jsondecode(fileread(manifestPath));
if string(assignmentProtocol.protocol_version) ~= "1.0" || ...
        string(assignmentProtocol.status) ~= "exploratory_frozen_after_phase2_10_before_assignment_decomposition" || ...
        string(staticProtocol.protocol_version) ~= "1.1" || ...
        string(manifest.manifest_version) ~= "1.0" || manifest.selected_track_count ~= 10
    error("ELEC5305:AssignmentSensitivity:FrozenConfig", "Frozen protocol metadata mismatch.");
end
provenanceCounts = validate_component_provenance(repoRoot, assignmentProtocol, expectedSofaHash);

sampleRate = double(staticProtocol.excerpt.sample_rate_hz);
excerptStartSeconds = double(staticProtocol.excerpt.start_seconds);
excerptDurationSeconds = double(staticProtocol.excerpt.duration_seconds);
expectedInputFrames = double(staticProtocol.excerpt.frames);
maximumDirectionMismatchDeg = double(staticProtocol.hrtf.maximum_direction_mismatch_deg);
if sampleRate ~= 44100 || excerptStartSeconds ~= 30 || excerptDurationSeconds ~= 30 || ...
        expectedInputFrames ~= 1323000 || maximumDirectionMismatchDeg ~= 1
    error("ELEC5305:AssignmentSensitivity:Excerpt", "Frozen excerpt/lookup configuration mismatch.");
end

commonAngles = [-80, -30, -10, 0, 10, 30, 80];
moderateAngles = [-30, -10, 10, 30];
wideAngles = [-80, -30, 30, 80];
stemNames = ["bass", "vocals", "drums", "other"];
conditionNames = ["moderate", "wide"];
if ~isequal(reshape(string(assignmentProtocol.frozen_design.source_order), 1, []), stemNames) || ...
        ~isequal(reshape(double(assignmentProtocol.frozen_design.angle_sets_deg.moderate), 1, []), moderateAngles) || ...
        ~isequal(reshape(double(assignmentProtocol.frozen_design.angle_sets_deg.wide), 1, []), wideAngles)
    error("ELEC5305:AssignmentSensitivity:Design", "Frozen source order or angle sets mismatch.");
end

subject = load_cipic_subject(sofaPath);
if subject.fs ~= sampleRate || size(subject.hrir, 3) ~= 200 || ...
        ~isequal(string(subject.receiver_order), ["left", "right"])
    error("ELEC5305:AssignmentSensitivity:HRTF", "Frozen HRTF structure mismatch.");
end
for angle = commonAngles
    match = find_hrir_direction(subject, angle, 0);
    if ~match.exact_match || match.angular_mismatch_deg ~= 0 || ...
            match.actual_azimuth_deg ~= angle || match.actual_elevation_deg ~= 0
        error("ELEC5305:AssignmentSensitivity:HRTFGrid", ...
            "Angle %.17g is not an exact zero-elevation grid match.", angle);
    end
end

frozenAssignments = readtable(phase210AssignmentsPath, "TextType", "string");
frozenPositionSummary = readtable(phase210SummaryPath, "TextType", "string");
if height(frozenAssignments) ~= 480 || height(frozenPositionSummary) ~= 20
    error("ELEC5305:AssignmentSensitivity:Phase210Rows", "Frozen Phase 2.10 row count mismatch.");
end

selectedTracks = manifest.selected_tracks;
assignmentTables = cell(10, 1);
componentTables = cell(10, 1);
pairTables = cell(10, 1);
canonicalPairTables = cell(10, 1);
canonicalStemTables = cell(10, 1);
validationValues = cell(10, 1);
trackRuntimes = zeros(10, 1);
precomputeRuntimes = zeros(10, 1);
cacheTrackCount = 0;
cacheStemCount = 0;

for trackIndex = 1:10
    trackStarted = tic;
    track = selectedTracks(trackIndex);
    rank = double(track.rank);
    trackName = string(track.track_name_original);
    if rank ~= trackIndex
        error("ELEC5305:AssignmentSensitivity:Rank", "Manifest rank/order mismatch.");
    end
    fprintf("[%d/10] %s\n", rank, trackName);
    trackDirectory = fullfile(repoRoot, string(track.dataset_relative_path));
    cacheDirectory = fullfile(repoRoot, "outputs", "phase2", "phase2_5_final", ...
        "cache", "htdemucs_ft", trackName);
    cacheCompletionPath = fullfile(cacheDirectory, "completion.json");

    oracleExcerpt = load_musdb_gt_excerpt(trackDirectory, excerptStartSeconds, ...
        excerptDurationSeconds, sampleRate);
    estimatedExcerpt = load_final_cached_excerpt(cacheDirectory, cacheCompletionPath, ...
        trackName, excerptStartSeconds, excerptDurationSeconds, sampleRate);
    validate_excerpt_pair(oracleExcerpt, estimatedExcerpt, expectedInputFrames, rank, trackName);
    cacheTrackCount = cacheTrackCount + 1;
    cacheStemCount = cacheStemCount + 4;

    errors = struct();
    for stemIndex = 1:4
        fieldName = char(stemNames(stemIndex));
        errors.(fieldName) = double(estimatedExcerpt.mono.(fieldName)) - ...
            double(oracleExcerpt.mono.(fieldName));
    end

    precomputeStarted = tic;
    [gtComponents, errorComponents, componentAudit] = precompute_stem_angle_components( ...
        oracleExcerpt.mono, errors, subject, commonAngles, 0, maximumDirectionMismatchDeg);
    precomputeRuntimes(rank) = toc(precomputeStarted);
    if componentAudit.gt_pass_count ~= 28 || componentAudit.error_pass_count ~= 28
        error("ELEC5305:AssignmentSensitivity:ComponentAudit", ...
            "Component reconstruction audit failed for rank %d.", rank);
    end

    frozenTrack = frozenAssignments(frozenAssignments.rank == rank, :);
    frozenTrackSummary = frozenPositionSummary(frozenPositionSummary.rank == rank, :);
    if height(frozenTrack) ~= 48 || height(frozenTrackSummary) ~= 2
        error("ELEC5305:AssignmentSensitivity:TrackRows", "Frozen track rows mismatch.");
    end
    [assignmentTables{rank}, componentTables{rank}, pairTables{rank}, ...
        canonicalPairTables{rank}, canonicalStemTables{rank}, validationValues{rank}] = ...
        analyze_track(rank, trackName, gtComponents, errorComponents, commonAngles, ...
        conditionNames, {moderateAngles, wideAngles}, stemNames, frozenTrack, frozenTrackSummary);
    validationValues{rank}.gt_precompute_pass_count = componentAudit.gt_pass_count;
    validationValues{rank}.error_precompute_pass_count = componentAudit.error_pass_count;
    validationValues{rank}.rank4_error_component_included = rank ~= 4 || ...
        all(componentTables{rank}.rendered_error_energy( ...
        componentTables{rank}.stem == "vocals") > 0);
    if ~validationValues{rank}.rank4_error_component_included
        error("ELEC5305:AssignmentSensitivity:Rank4", ...
            "Rank-4 nonzero vocals error components were not retained.");
    end

    trackOutput = fullfile(tracksRoot, trackName);
    mkdir_if_missing(trackOutput);
    atomic_writetable(assignmentTables{rank}, fullfile(trackOutput, "assignment_decomposition.csv"));
    atomic_writetable(componentTables{rank}, fullfile(trackOutput, "rebuilt_component_energy.csv"));
    atomic_writetable(pairTables{rank}, fullfile(trackOutput, "pair_angle_retention.csv"));
    atomic_writetable(canonicalPairTables{rank}, fullfile(trackOutput, "canonical_pair_decomposition.csv"));
    atomic_writetable(canonicalStemTables{rank}, fullfile(trackOutput, "canonical_stem_energy_decomposition.csv"));
    atomic_write_json(fullfile(trackOutput, "validation.json"), validationValues{rank});
    trackRuntimes(rank) = toc(trackStarted);
    completion = struct( ...
        "schema", "phase2_11b_track_completion_v1", ...
        "status", "COMPLETE", "rank", rank, "track", trackName, ...
        "assignment_protocol_sha256", assignmentHash, ...
        "phase2_10_assignment_sha256", expectedPhase210AssignmentHash, ...
        "phase2_5_cache_completion_sha256", compute_sha256(cacheCompletionPath), ...
        "assignment_rows", height(assignmentTables{rank}), ...
        "component_rows", height(componentTables{rank}), ...
        "pair_rows", height(pairTables{rank}), ...
        "canonical_pair_rows", height(canonicalPairTables{rank}), ...
        "canonical_stem_rows", height(canonicalStemTables{rank}), ...
        "runtime_seconds", trackRuntimes(rank), ...
        "precompute_runtime_seconds", precomputeRuntimes(rank), ...
        "assignment_sha256", compute_sha256(fullfile(trackOutput, "assignment_decomposition.csv")), ...
        "component_sha256", compute_sha256(fullfile(trackOutput, "rebuilt_component_energy.csv")), ...
        "pair_sha256", compute_sha256(fullfile(trackOutput, "pair_angle_retention.csv")), ...
        "canonical_pair_sha256", compute_sha256(fullfile(trackOutput, "canonical_pair_decomposition.csv")), ...
        "canonical_stem_sha256", compute_sha256(fullfile(trackOutput, "canonical_stem_energy_decomposition.csv")), ...
        "validation_sha256", compute_sha256(fullfile(trackOutput, "validation.json")));
    atomic_write_json(fullfile(trackOutput, "completion.json"), completion);
    fprintf("  COMPLETE precompute %.3f s total %.3f s\n", ...
        precomputeRuntimes(rank), trackRuntimes(rank));
    clear gtComponents errorComponents oracleExcerpt estimatedExcerpt errors;
end

assignmentAggregate = vertcat(assignmentTables{:});
componentAggregate = vertcat(componentTables{:});
pairAggregate = vertcat(pairTables{:});
canonicalPairAggregate = vertcat(canonicalPairTables{:});
canonicalStemAggregate = vertcat(canonicalStemTables{:});
if height(assignmentAggregate) ~= 480 || height(componentAggregate) ~= 280 || ...
        height(pairAggregate) ~= 1440 || height(canonicalPairAggregate) ~= 120 || ...
        height(canonicalStemAggregate) ~= 80
    error("ELEC5305:AssignmentSensitivity:AggregateRows", "Aggregate row counts mismatch.");
end
assignmentAggregate = sortrows(assignmentAggregate, ["rank", "condition_order_internal", "permutation_id"]);
assignmentAggregate.condition_order_internal = [];
componentAggregate = sortrows(componentAggregate, ["rank", "stem_order_internal", "angle_deg"]);
componentAggregate.stem_order_internal = [];
pairAggregate = sortrows(pairAggregate, ["rank", "condition_order_internal", ...
    "pair_order_internal", "angle_i_deg", "angle_j_deg"]);
pairAggregate.condition_order_internal = [];
pairAggregate.pair_order_internal = [];
canonicalPairAggregate = sortrows(canonicalPairAggregate, ["rank", ...
    "condition_order_internal", "pair_order_internal"]);
canonicalPairAggregate.condition_order_internal = [];
canonicalPairAggregate.pair_order_internal = [];
canonicalStemAggregate = sortrows(canonicalStemAggregate, ["rank", ...
    "condition_order_internal", "stem_order_internal"]);
canonicalStemAggregate.condition_order_internal = [];
canonicalStemAggregate.stem_order_internal = [];

assignmentOutputPath = fullfile(metricsRoot, "rq6_assignment_decomposition.csv");
componentOutputPath = fullfile(metricsRoot, "rq6_rebuilt_component_energy.csv");
pairOutputPath = fullfile(metricsRoot, "rq6_pair_angle_retention.csv");
canonicalPairOutputPath = fullfile(metricsRoot, "rq6_canonical_pair_decomposition.csv");
canonicalStemOutputPath = fullfile(metricsRoot, "rq6_canonical_stem_energy_decomposition.csv");
atomic_writetable(assignmentAggregate, assignmentOutputPath);
atomic_writetable(componentAggregate, componentOutputPath);
atomic_writetable(pairAggregate, pairOutputPath);
atomic_writetable(canonicalPairAggregate, canonicalPairOutputPath);
atomic_writetable(canonicalStemAggregate, canonicalStemOutputPath);

validationSummary = aggregate_validation(validationValues);
summary = struct();
summary.schema = "phase2_11b_matlab_assignment_sensitivity_summary_v1";
summary.status = "MATLAB_COMPLETE";
summary.analysis_status = "EXPLORATORY_FOLLOW_UP";
summary.assignment_protocol_sha256 = assignmentHash;
summary.mechanism_protocol_sha256 = mechanismHash;
summary.static_protocol_sha256 = staticHash;
summary.manifest_sha256 = manifestHash;
summary.sofa_sha256 = sofaHash;
summary.phase2_10_assignment_sha256 = expectedPhase210AssignmentHash;
summary.renderer_source_hash_count = provenanceCounts.source_file_count;
summary.phase2_5_completion_hash_count = provenanceCounts.cache_completion_count;
summary.cache_track_count = cacheTrackCount;
summary.cache_stem_count = cacheStemCount;
summary.component_reconstruction_cases = 10 * 4 * 7 * 2;
summary.assignment_rows = height(assignmentAggregate);
summary.component_rows = height(componentAggregate);
summary.pair_rows = height(pairAggregate);
summary.canonical_pair_rows = height(canonicalPairAggregate);
summary.canonical_stem_rows = height(canonicalStemAggregate);
summary.validation = validationSummary;
summary.per_track_runtime_seconds = trackRuntimes;
summary.per_track_precompute_runtime_seconds = precomputeRuntimes;
summary.sum_track_runtime_seconds = sum(trackRuntimes);
summary.sum_precompute_runtime_seconds = sum(precomputeRuntimes);
summary.wall_runtime_seconds = toc(overallStarted);
summary.matlab_version = version;
summary.matlab_architecture = computer("arch");
toolboxes = ver;
summary.signal_processing_toolbox_available = any(strcmp({toolboxes.Name}, "Signal Processing Toolbox"));
summary.audio_toolbox_available = any(strcmp({toolboxes.Name}, "Audio Toolbox"));
summary.dsp_system_toolbox_available = any(strcmp({toolboxes.Name}, "DSP System Toolbox"));
summary.statistics_toolbox_available = any(strcmp({toolboxes.Name}, "Statistics and Machine Learning Toolbox"));
summary.htdemucs_rerun = false;
summary.real_rq6_results_computed = true;
summary.no_p_values = true;
summary.output_hashes = struct( ...
    "assignment_decomposition", compute_sha256(assignmentOutputPath), ...
    "rebuilt_component_energy", compute_sha256(componentOutputPath), ...
    "pair_angle_retention", compute_sha256(pairOutputPath), ...
    "canonical_pair_decomposition", compute_sha256(canonicalPairOutputPath), ...
    "canonical_stem_energy_decomposition", compute_sha256(canonicalStemOutputPath));
atomic_write_json(fullfile(metricsRoot, "matlab_assignment_sensitivity_summary.json"), summary);

fprintf("PHASE2_11B_MATLAB_COMPLETE assignments=%d pairs=%d canonical_pairs=%d canonical_stems=%d\n", ...
    height(assignmentAggregate), height(pairAggregate), height(canonicalPairAggregate), ...
    height(canonicalStemAggregate));

function [assignmentTable, componentTable, pairTable, canonicalPairTable, canonicalStemTable, validation] = analyze_track(rank, trackName, gtComponents, errorComponents, commonAngles, conditionNames, conditionAngleSets, stemNames, frozenTrack, frozenTrackSummary)
pairIndices = [1, 2; 1, 3; 1, 4; 2, 3; 2, 4; 3, 4];
pairNames = ["bass-vocals", "bass-drums", "bass-other", ...
    "vocals-drums", "vocals-other", "drums-other"];

componentRows = cell(28, 1);
componentRow = 0;
for stemIndex = 1:4
    for angleIndex = 1:numel(commonAngles)
        componentRow = componentRow + 1;
        value = errorComponents{stemIndex, angleIndex};
        componentRows{componentRow} = struct( ...
            "rank", rank, "track", trackName, "stem", stemNames(stemIndex), ...
            "angle_deg", commonAngles(angleIndex), ...
            "rendered_error_energy", sum(value .^ 2, "all"), ...
            "stem_order_internal", stemIndex);
    end
end
componentTable = struct2table(vertcat(componentRows{:}));

assignmentRows = cell(48, 1);
pairRows = cell(144, 1);
canonicalPairRows = cell(12, 1);
canonicalStemRows = cell(8, 1);
assignmentRow = 0;
pairRow = 0;
canonicalPairRow = 0;
canonicalStemRow = 0;
regressionMax = zeros(1, 6);
rIdentityMax = 0;
vIdentityMax = 0;
jIdentityMax = 0;
pairAlgebraMax = 0;
pairMinimum = Inf;
deltaJMax = 0;
deltaEMax = 0;
percentileMax = 0;
stemAngleCountError = 0;
orderedPairCountError = 0;

for conditionIndex = 1:2
    conditionName = conditionNames(conditionIndex);
    conditionAngles = conditionAngleSets{conditionIndex};
    frozenCondition = frozenTrack(frozenTrack.condition == conditionName, :);
    frozenCondition = sortrows(frozenCondition, "permutation_id");
    if height(frozenCondition) ~= 24 || ...
            ~isequal(frozenCondition.permutation_id(:), (1:24)') || ...
            sum(frozenCondition.is_canonical) ~= 1
        error("ELEC5305:AssignmentSensitivity:PermutationRows", ...
            "Frozen permutation structure mismatch for rank %d/%s.", rank, conditionName);
    end
    assignments = [frozenCondition.bass_angle_deg, frozenCondition.vocals_angle_deg, ...
        frozenCondition.drums_angle_deg, frozenCondition.other_angle_deg];
    if size(unique(assignments, "rows"), 1) ~= 24
        error("ELEC5305:AssignmentSensitivity:PermutationUnique", "Assignments are not unique.");
    end
    for stemIndex = 1:4
        for angle = conditionAngles
            count = sum(assignments(:, stemIndex) == angle);
            stemAngleCountError = max(stemAngleCountError, abs(count - 6));
            if count ~= 6
                error("ELEC5305:AssignmentSensitivity:StemAngleBalance", ...
                    "Stem-angle balance mismatch.");
            end
        end
    end
    for pairIndex = 1:6
        i = pairIndices(pairIndex, 1);
        j = pairIndices(pairIndex, 2);
        for angleI = conditionAngles
            for angleJ = conditionAngles
                if angleI == angleJ, continue; end
                count = sum(assignments(:, i) == angleI & assignments(:, j) == angleJ);
                orderedPairCountError = max(orderedPairCountError, abs(count - 2));
                if count ~= 2
                    error("ELEC5305:AssignmentSensitivity:PairAngleBalance", ...
                        "Ordered pair-angle balance mismatch.");
                end
            end
        end
    end

    AValues = zeros(24, 1);
    RValues = zeros(24, 1);
    JValues = zeros(24, 6);
    for permutationIndex = 1:24
        assignment = assignments(permutationIndex, :);
        result = evaluate_error_component_assignment( ...
            gtComponents, errorComponents, commonAngles, assignment);
        frozen = frozenCondition(permutationIndex, :);
        regressionErrors = [ ...
            relative_scalar(result.A_individual_error_energy, frozen.A_individual_error_energy), ...
            relative_scalar(result.T_total_error_energy, frozen.T_total_error_energy), ...
            relative_scalar(result.I_interaction_energy, frozen.I_interaction_energy), ...
            relative_scalar(result.error_retention_ratio, frozen.error_retention_ratio), ...
            relative_scalar(result.oracle_energy, frozen.oracle_energy), ...
            relative_scalar(result.normalized_total_error, frozen.normalized_total_error)];
        regressionMax = max(regressionMax, regressionErrors);
        if any(regressionErrors > 1e-10)
            error("ELEC5305:AssignmentSensitivity:Phase210Regression", ...
                "Rebuilt assignment mismatch rank %d/%s/permutation %d.", ...
                rank, conditionName, permutationIndex);
        end
        A = result.A_individual_error_energy;
        I = result.I_interaction_energy;
        T = result.T_total_error_energy;
        R = result.error_retention_ratio;
        oracleEnergy = result.oracle_energy;
        K = I / A;
        U = A / oracleEnergy;
        W = I / oracleEnergy;
        V = T / oracleEnergy;
        rError = abs(R - (1 + K)) / max(1, abs(R));
        vError = abs(V - (U + W)) / max(1, abs(V));
        rIdentityMax = max(rIdentityMax, rError);
        vIdentityMax = max(vIdentityMax, vError);
        if rError > 1e-10 || vError > 1e-10
            error("ELEC5305:AssignmentSensitivity:AssignmentIdentity", ...
                "R/K or V/U/W identity failed.");
        end
        selected = result.selected_error_components;
        for pairIndex = 1:6
            i = pairIndices(pairIndex, 1);
            j = pairIndices(pairIndex, 2);
            JValues(permutationIndex, pairIndex) = ...
                2 * sum(selected{i} .* selected{j}, "all") / A;
        end
        jError = abs(sum(JValues(permutationIndex, :)) - (R - 1));
        jIdentityMax = max(jIdentityMax, jError);
        if jError > 1e-10
            error("ELEC5305:AssignmentSensitivity:JIdentity", "sum J != R - 1.");
        end
        AValues(permutationIndex) = A;
        RValues(permutationIndex) = R;
        assignmentRow = assignmentRow + 1;
        assignmentRows{assignmentRow} = struct( ...
            "rank", rank, "track", trackName, "condition", conditionName, ...
            "permutation_id", permutationIndex, "angles", format_angles(assignment), ...
            "A", A, "I", I, "T", T, "R", R, ...
            "oracle_energy", oracleEnergy, "V", V, "K", K, "U", U, "W", W, ...
            "condition_order_internal", conditionIndex);
    end

    for pairIndex = 1:6
        i = pairIndices(pairIndex, 1);
        j = pairIndices(pairIndex, 2);
        for angleI = conditionAngles
            for angleJ = conditionAngles
                if angleI == angleJ, continue; end
                componentI = select_component(errorComponents, commonAngles, i, angleI);
                componentJ = select_component(errorComponents, commonAngles, j, angleJ);
                differential = compute_pair_retention_metrics(componentI, componentJ);
                commonA = compute_pair_retention_metrics( ...
                    select_component(errorComponents, commonAngles, i, angleI), ...
                    select_component(errorComponents, commonAngles, j, angleI));
                commonB = compute_pair_retention_metrics( ...
                    select_component(errorComponents, commonAngles, i, angleJ), ...
                    select_component(errorComponents, commonAngles, j, angleJ));
                if differential.metric_status ~= "DEFINED" || ...
                        commonA.metric_status ~= "DEFINED" || commonB.metric_status ~= "DEFINED"
                    error("ELEC5305:AssignmentSensitivity:UndefinedPair", ...
                        "Official-test pair metric is undefined for rank %d/%s/%s.", ...
                        rank, conditionName, pairNames(pairIndex));
                end
                matched = 0.5 * (commonA.pair_retention_ratio + commonB.pair_retention_ratio);
                differentialChange = differential.pair_retention_ratio - matched;
                pairAlgebraMax = max(pairAlgebraMax, differential.algebra_relative_error);
                pairMinimum = min(pairMinimum, differential.pair_retention_ratio);
                if differential.algebra_relative_error > 1e-10 || ...
                        differential.pair_retention_ratio < -1e-12
                    error("ELEC5305:AssignmentSensitivity:PairAlgebra", ...
                        "Pair algebra/nonnegative gate failed.");
                end
                pairRow = pairRow + 1;
                pairRows{pairRow} = struct( ...
                    "rank", rank, "track", trackName, "condition", conditionName, ...
                    "stem_i", stemNames(i), "stem_j", stemNames(j), ...
                    "angle_i_deg", angleI, "angle_j_deg", angleJ, ...
                    "angular_separation_deg", abs(angleI - angleJ), ...
                    "energy_i", differential.energy_i, "energy_j", differential.energy_j, ...
                    "inner_product", differential.inner_product, ...
                    "pair_retention_ratio", differential.pair_retention_ratio, ...
                    "cosine_alignment", differential.cosine_alignment, ...
                    "matched_common_pair_retention", matched, ...
                    "differential_pair_retention_change", differentialChange, ...
                    "common_pair_retention_at_angle_i", commonA.pair_retention_ratio, ...
                    "common_pair_retention_at_angle_j", commonB.pair_retention_ratio, ...
                    "metric_status", differential.metric_status, ...
                    "condition_order_internal", conditionIndex, ...
                    "pair_order_internal", pairIndex);
            end
        end
    end

    canonicalIndex = find(frozenCondition.is_canonical, 1);
    canonicalAssignment = assignments(canonicalIndex, :);
    meanJ = mean(JValues, 1);
    deltaJ = JValues(canonicalIndex, :) - meanJ;
    totalDeviation = RValues(canonicalIndex) - mean(RValues);
    deltaJError = abs(sum(deltaJ) - totalDeviation);
    deltaJMax = max(deltaJMax, deltaJError);
    if deltaJError > 1e-10
        error("ELEC5305:AssignmentSensitivity:DeltaJ", "Canonical DeltaJ gate failed.");
    end
    summaryRow = frozenTrackSummary(frozenTrackSummary.condition == conditionName, :);
    if height(summaryRow) ~= 1
        error("ELEC5305:AssignmentSensitivity:CanonicalSummary", "Missing canonical summary row.");
    end
    recomputedPercentile = midrank_percentile(RValues(canonicalIndex), RValues);
    percentileError = abs(recomputedPercentile - summaryRow.canonical_R_percentile);
    percentileMax = max(percentileMax, percentileError);
    if percentileError > 1e-10
        error("ELEC5305:AssignmentSensitivity:CanonicalPercentile", ...
            "Canonical percentile regression failed.");
    end
    for pairIndex = 1:6
        i = pairIndices(pairIndex, 1);
        j = pairIndices(pairIndex, 2);
        canonicalPairRow = canonicalPairRow + 1;
        canonicalPairRows{canonicalPairRow} = struct( ...
            "rank", rank, "track", trackName, "condition", conditionName, ...
            "stem_i", stemNames(i), "stem_j", stemNames(j), ...
            "canonical_angle_i", canonicalAssignment(i), ...
            "canonical_angle_j", canonicalAssignment(j), ...
            "J_canonical", JValues(canonicalIndex, pairIndex), ...
            "mean_J_all24", meanJ(pairIndex), ...
            "delta_J_canonical", deltaJ(pairIndex), ...
            "canonical_R", RValues(canonicalIndex), "mean_R_all24", mean(RValues), ...
            "canonical_R_percentile", recomputedPercentile, ...
            "condition_order_internal", conditionIndex, ...
            "pair_order_internal", pairIndex);
    end

    canonicalStemEnergies = zeros(4, 1);
    meanStemEnergies = zeros(4, 1);
    for stemIndex = 1:4
        canonicalStemEnergies(stemIndex) = component_energy( ...
            errorComponents, commonAngles, stemIndex, canonicalAssignment(stemIndex));
        angleEnergies = zeros(4, 1);
        for angleIndex = 1:4
            angleEnergies(angleIndex) = component_energy( ...
                errorComponents, commonAngles, stemIndex, conditionAngles(angleIndex));
        end
        meanStemEnergies(stemIndex) = mean(angleEnergies);
    end
    deltaE = canonicalStemEnergies - meanStemEnergies;
    energyDeviation = AValues(canonicalIndex) - mean(AValues);
    deltaEError = abs(sum(deltaE) - energyDeviation) / max(1, abs(energyDeviation));
    deltaEMax = max(deltaEMax, deltaEError);
    if deltaEError > 1e-10
        error("ELEC5305:AssignmentSensitivity:DeltaE", "Canonical delta_E gate failed.");
    end
    for stemIndex = 1:4
        canonicalStemRow = canonicalStemRow + 1;
        canonicalStemRows{canonicalStemRow} = struct( ...
            "rank", rank, "track", trackName, "condition", conditionName, ...
            "stem", stemNames(stemIndex), ...
            "canonical_angle_deg", canonicalAssignment(stemIndex), ...
            "E_j_canonical", canonicalStemEnergies(stemIndex), ...
            "mean_E_j_all_angles", meanStemEnergies(stemIndex), ...
            "delta_E_j_canonical", deltaE(stemIndex), ...
            "A_canonical", AValues(canonicalIndex), "mean_A_all24", mean(AValues), ...
            "condition_order_internal", conditionIndex, ...
            "stem_order_internal", stemIndex);
    end
end

assignmentTable = struct2table(vertcat(assignmentRows{:}));
pairTable = struct2table(vertcat(pairRows{:}));
canonicalPairTable = struct2table(vertcat(canonicalPairRows{:}));
canonicalStemTable = struct2table(vertcat(canonicalStemRows{:}));
expectedSeparations = { [20, 40, 60], [50, 60, 110, 160] };
for conditionIndex = 1:2
    actual = unique(pairTable.angular_separation_deg( ...
        pairTable.condition == conditionNames(conditionIndex)))';
    if ~isequal(actual, expectedSeparations{conditionIndex})
        error("ELEC5305:AssignmentSensitivity:Separation", "Angular separation set mismatch.");
    end
end
validation = struct( ...
    "schema", "phase2_11b_track_validation_v1", "status", "PASS", ...
    "rank", rank, "track", trackName, ...
    "assignment_regression_pass_count", 48, ...
    "assignment_regression_max_relative_error", max(regressionMax), ...
    "assignment_regression_max_A", regressionMax(1), ...
    "assignment_regression_max_T", regressionMax(2), ...
    "assignment_regression_max_I", regressionMax(3), ...
    "assignment_regression_max_R", regressionMax(4), ...
    "assignment_regression_max_oracle_energy", regressionMax(5), ...
    "assignment_regression_max_V", regressionMax(6), ...
    "R_K_identity_pass_count", 48, "R_K_identity_max_error", rIdentityMax, ...
    "V_U_W_identity_pass_count", 48, "V_U_W_identity_max_error", vIdentityMax, ...
    "J_identity_pass_count", 48, "J_identity_max_error", jIdentityMax, ...
    "stem_angle_balance_max_count_error", stemAngleCountError, ...
    "ordered_pair_balance_max_count_error", orderedPairCountError, ...
    "pair_algebra_pass_count", 144, "pair_algebra_max_error", pairAlgebraMax, ...
    "pair_minimum_retention", pairMinimum, "undefined_pair_count", 0, ...
    "canonical_delta_J_pass_count", 2, "canonical_delta_J_max_error", deltaJMax, ...
    "canonical_delta_E_pass_count", 2, "canonical_delta_E_max_error", deltaEMax, ...
    "canonical_percentile_pass_count", 2, "canonical_percentile_max_error", percentileMax);
end

function value = select_component(components, angleGrid, stemIndex, angle)
angleIndex = find(angleGrid == angle);
if numel(angleIndex) ~= 1
    error("ELEC5305:AssignmentSensitivity:ComponentAngle", "Component angle not found exactly once.");
end
value = components{stemIndex, angleIndex};
end

function value = component_energy(components, angleGrid, stemIndex, angle)
component = select_component(components, angleGrid, stemIndex, angle);
value = sum(component .^ 2, "all");
end

function value = format_angles(angles)
value = string(sprintf("[%g,%g,%g,%g]", angles(1), angles(2), angles(3), angles(4)));
end

function value = midrank_percentile(score, population)
less = sum(population < score);
equal = sum(population == score);
if equal < 1
    error("ELEC5305:AssignmentSensitivity:Midrank", "Canonical score absent from population.");
end
value = 100 * (less + 0.5 * equal) / numel(population);
end

function value = relative_scalar(actual, expected)
scale = max(abs(actual), abs(expected));
if scale == 0
    value = abs(actual - expected);
else
    value = abs(actual - expected) / scale;
end
end

function validate_excerpt_pair(oracle, estimated, expectedFrames, rank, trackName)
if oracle.sample_rate_hz ~= estimated.sample_rate_hz || ...
        oracle.frame_count ~= expectedFrames || estimated.frame_count ~= expectedFrames || ...
        oracle.start_frame_matlab_1_based ~= estimated.start_frame_matlab_1_based || ...
        oracle.end_frame_matlab_1_based_inclusive ~= estimated.end_frame_matlab_1_based_inclusive
    error("ELEC5305:AssignmentSensitivity:Alignment", ...
        "GT/estimated excerpt mismatch for rank %d %s.", rank, trackName);
end
end

function counts = validate_component_provenance(repoRoot, protocol, expectedSofaHash)
provenance = protocol.component_source_provenance;
if logical(provenance.phase2_10_persisted_component_cache.exists) || ...
        provenance.phase2_10_persisted_component_cache.mat_file_count ~= 0
    error("ELEC5305:AssignmentSensitivity:ComponentCache", ...
        "Protocol must record no persisted Phase 2.10 component cache.");
end
sourceFiles = provenance.only_allowed_phase2_11b_reconstruction_path.source_files;
if numel(sourceFiles) ~= 9
    error("ELEC5305:AssignmentSensitivity:SourceCount", "Expected nine frozen source files.");
end
for index = 1:numel(sourceFiles)
    pathValue = fullfile(repoRoot, string(sourceFiles(index).path));
    if compute_sha256(pathValue) ~= string(sourceFiles(index).sha256)
        error("ELEC5305:AssignmentSensitivity:SourceHash", ...
            "Frozen renderer/source hash mismatch: %s", pathValue);
    end
end
completionFiles = provenance.only_allowed_phase2_11b_reconstruction_path.estimated_source.completion_files;
if numel(completionFiles) ~= 10
    error("ELEC5305:AssignmentSensitivity:CompletionCount", ...
        "Expected ten Phase 2.5 cache completion files.");
end
for index = 1:numel(completionFiles)
    pathValue = fullfile(repoRoot, string(completionFiles(index).path));
    if compute_sha256(pathValue) ~= string(completionFiles(index).sha256)
        error("ELEC5305:AssignmentSensitivity:CompletionHash", ...
            "Frozen cache completion hash mismatch: %s", pathValue);
    end
end
hrtf = provenance.only_allowed_phase2_11b_reconstruction_path.hrtf;
if string(hrtf.sha256) ~= expectedSofaHash
    error("ELEC5305:AssignmentSensitivity:ProtocolSofa", "Protocol SOFA hash mismatch.");
end
counts = struct("source_file_count", numel(sourceFiles), ...
    "cache_completion_count", numel(completionFiles));
end

function summary = aggregate_validation(values)
summary = struct();
summary.status = "PASS";
summary.assignment_regression_pass_count = 0;
summary.assignment_regression_max_relative_error = 0;
summary.assignment_regression_max_A = 0;
summary.assignment_regression_max_T = 0;
summary.assignment_regression_max_I = 0;
summary.assignment_regression_max_R = 0;
summary.assignment_regression_max_oracle_energy = 0;
summary.assignment_regression_max_V = 0;
summary.R_K_identity_pass_count = 0;
summary.R_K_identity_max_error = 0;
summary.V_U_W_identity_pass_count = 0;
summary.V_U_W_identity_max_error = 0;
summary.J_identity_pass_count = 0;
summary.J_identity_max_error = 0;
summary.pair_algebra_pass_count = 0;
summary.pair_algebra_max_error = 0;
summary.pair_minimum_retention = Inf;
summary.undefined_pair_count = 0;
summary.canonical_delta_J_pass_count = 0;
summary.canonical_delta_J_max_error = 0;
summary.canonical_delta_E_pass_count = 0;
summary.canonical_delta_E_max_error = 0;
summary.canonical_percentile_pass_count = 0;
summary.canonical_percentile_max_error = 0;
summary.rank4_error_component_included = false;
for index = 1:numel(values)
    value = values{index};
    summary.assignment_regression_pass_count = summary.assignment_regression_pass_count + value.assignment_regression_pass_count;
    summary.assignment_regression_max_relative_error = max(summary.assignment_regression_max_relative_error, value.assignment_regression_max_relative_error);
    summary.assignment_regression_max_A = max(summary.assignment_regression_max_A, value.assignment_regression_max_A);
    summary.assignment_regression_max_T = max(summary.assignment_regression_max_T, value.assignment_regression_max_T);
    summary.assignment_regression_max_I = max(summary.assignment_regression_max_I, value.assignment_regression_max_I);
    summary.assignment_regression_max_R = max(summary.assignment_regression_max_R, value.assignment_regression_max_R);
    summary.assignment_regression_max_oracle_energy = max(summary.assignment_regression_max_oracle_energy, value.assignment_regression_max_oracle_energy);
    summary.assignment_regression_max_V = max(summary.assignment_regression_max_V, value.assignment_regression_max_V);
    summary.R_K_identity_pass_count = summary.R_K_identity_pass_count + value.R_K_identity_pass_count;
    summary.R_K_identity_max_error = max(summary.R_K_identity_max_error, value.R_K_identity_max_error);
    summary.V_U_W_identity_pass_count = summary.V_U_W_identity_pass_count + value.V_U_W_identity_pass_count;
    summary.V_U_W_identity_max_error = max(summary.V_U_W_identity_max_error, value.V_U_W_identity_max_error);
    summary.J_identity_pass_count = summary.J_identity_pass_count + value.J_identity_pass_count;
    summary.J_identity_max_error = max(summary.J_identity_max_error, value.J_identity_max_error);
    summary.pair_algebra_pass_count = summary.pair_algebra_pass_count + value.pair_algebra_pass_count;
    summary.pair_algebra_max_error = max(summary.pair_algebra_max_error, value.pair_algebra_max_error);
    summary.pair_minimum_retention = min(summary.pair_minimum_retention, value.pair_minimum_retention);
    summary.undefined_pair_count = summary.undefined_pair_count + value.undefined_pair_count;
    summary.canonical_delta_J_pass_count = summary.canonical_delta_J_pass_count + value.canonical_delta_J_pass_count;
    summary.canonical_delta_J_max_error = max(summary.canonical_delta_J_max_error, value.canonical_delta_J_max_error);
    summary.canonical_delta_E_pass_count = summary.canonical_delta_E_pass_count + value.canonical_delta_E_pass_count;
    summary.canonical_delta_E_max_error = max(summary.canonical_delta_E_max_error, value.canonical_delta_E_max_error);
    summary.canonical_percentile_pass_count = summary.canonical_percentile_pass_count + value.canonical_percentile_pass_count;
    summary.canonical_percentile_max_error = max(summary.canonical_percentile_max_error, value.canonical_percentile_max_error);
    if value.rank == 4
        summary.rank4_error_component_included = logical(value.rank4_error_component_included);
    end
end
if summary.assignment_regression_pass_count ~= 480 || ...
        summary.R_K_identity_pass_count ~= 480 || summary.V_U_W_identity_pass_count ~= 480 || ...
        summary.J_identity_pass_count ~= 480 || summary.pair_algebra_pass_count ~= 1440 || ...
        summary.undefined_pair_count ~= 0 || summary.canonical_delta_J_pass_count ~= 20 || ...
        summary.canonical_delta_E_pass_count ~= 20 || summary.canonical_percentile_pass_count ~= 20 || ...
        ~summary.rank4_error_component_included
    error("ELEC5305:AssignmentSensitivity:ValidationAggregate", ...
        "Aggregate validation pass counts mismatch.");
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
    error("ELEC5305:AssignmentSensitivity:WriteJSON", "Cannot write %s.", temporary);
end
cleanupFile = onCleanup(@() fclose(fid));
fprintf(fid, "%s\n", jsonText);
clear cleanupFile;
movefile(temporary, outputPath, "f");
end

function sha256 = compute_sha256(filePath)
fid = fopen(filePath, "rb");
if fid < 0
    error("ELEC5305:AssignmentSensitivity:HashRead", "Cannot open %s.", filePath);
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

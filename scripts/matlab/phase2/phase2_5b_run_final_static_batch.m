%% Phase 2.5b - Final 10-song static spatialisation and downstream metrics
% First pass writes per-song/aggregate downstream metrics and the RQ1 figure.
% After Python final analysis creates final_analysis_summary.json, rerunning
% this same script resumes and creates predetermined demonstration artifacts.

oldPath = path;
cleanupPath = onCleanup(@() path(oldPath));
scriptPath = mfilename("fullpath");
repoRoot = fileparts(fileparts(fileparts(fileparts(scriptPath))));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "comparison"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "hrtf"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "oracle"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "spatial"));

overallStarted = tic;
protocolPath = fullfile(repoRoot, "config", "phase2", "static_experiment_protocol.json");
manifestPath = fullfile(repoRoot, "config", "phase2", "final_test_manifest.json");
expectedProtocolHash = "3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3";
expectedParentProtocolHash = "54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0";
expectedManifestHash = "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc";
expectedSofaHash = "a9db5f938ed1113b118dcbeb43f5fe1b27b9e191d1bbdb63fbc4803b6959b220";
sofaPath = fullfile(repoRoot, "data", "hrtf", "cipic", "subject_003.sofa");
outputRoot = fullfile(repoRoot, "outputs", "phase2", "phase2_5_final");
metricsRoot = fullfile(outputRoot, "metrics");
figuresRoot = fullfile(outputRoot, "figures");
tracksRoot = fullfile(outputRoot, "tracks");
audioRoot = fullfile(outputRoot, "audio");
cacheRoot = fullfile(outputRoot, "cache", "htdemucs_ft");

protocolHash = compute_sha256(protocolPath);
manifestHash = compute_sha256(manifestPath);
if protocolHash ~= expectedProtocolHash || manifestHash ~= expectedManifestHash
    error("ELEC5305:FinalStatic:FrozenHash", "Frozen protocol or manifest SHA-256 mismatch.");
end
protocol = jsondecode(fileread(protocolPath));
manifest = jsondecode(fileread(manifestPath));
selectedTracks = manifest.selected_tracks;
if string(protocol.protocol_version) ~= "1.1" || ...
        string(protocol.parent_protocol_sha256) ~= expectedParentProtocolHash || ...
        string(protocol.status) ~= "amended_for_exact_silent_reference_before_final_downstream_analysis" || ...
        numel(selectedTracks) ~= 10 || ...
        manifest.selected_track_count ~= 10 || ...
        string(manifest.separation_execution_rule) ~= "full_track_htdemucs_ft_then_extract_30_60s"
    error("ELEC5305:FinalStatic:FrozenConfig", "Frozen protocol/manifest structure mismatch.");
end

sampleRate = double(protocol.excerpt.sample_rate_hz);
excerptStartSeconds = double(protocol.excerpt.start_seconds);
excerptDurationSeconds = double(protocol.excerpt.duration_seconds);
expectedInputFrames = double(protocol.excerpt.frames);
maximumDirectionMismatchDeg = double(protocol.hrtf.maximum_direction_mismatch_deg);
listeningGain = double(protocol.gain.listening_gain);
wavBitsPerSample = 24;
conditionConfigs = parse_spatial_conditions(protocol);
stftConfig = struct( ...
    "window_length_samples", double(protocol.stft.window_length_samples), ...
    "hop_size_samples", double(protocol.stft.hop_size_samples), ...
    "fft_size", double(protocol.stft.fft_size), ...
    "window_type", string(protocol.stft.window_type));
if sampleRate ~= 44100 || expectedInputFrames ~= 1323000 || ...
        excerptStartSeconds ~= 30 || excerptDurationSeconds ~= 30 || ...
        stftConfig.window_length_samples ~= 1024 || stftConfig.hop_size_samples ~= 256 || ...
        stftConfig.fft_size ~= 1024 || stftConfig.window_type ~= "periodic Hann"
    error("ELEC5305:FinalStatic:FrozenDSP", "Frozen excerpt/STFT configuration mismatch.");
end
if compute_sha256(sofaPath) ~= expectedSofaHash
    error("ELEC5305:FinalStatic:SOFAHash", "CIPIC subject_003 SOFA SHA-256 mismatch.");
end
subject = load_cipic_subject(sofaPath);
if subject.fs ~= sampleRate || size(subject.hrir, 3) ~= 200
    error("ELEC5305:FinalStatic:HRTF", "Frozen HRTF sample rate or HRIR length mismatch.");
end

sourceMetricsPath = fullfile(metricsRoot, "source_metrics_per_song.csv");
if ~isfile(sourceMetricsPath)
    error("ELEC5305:FinalStatic:SourceMetrics", "Complete Python source metrics are required first.");
end
sourceMetrics = readtable(sourceMetricsPath, "TextType", "string");
if height(sourceMetrics) ~= 10 || ...
        ~isequal(sourceMetrics.rank.', 1:10) || ...
        any(~isfinite(sourceMetrics.macro_si_sdr_db)) || ...
        any(~isfinite(sourceMetrics.macro_sir_db)) || ...
        ~isequal(sourceMetrics.active_stem_count.', [4, 4, 4, 3, 4, 4, 4, 4, 4, 4]) || ...
        ~isequal(sourceMetrics.inactive_stem_count.', [0, 0, 0, 1, 0, 0, 0, 0, 0, 0])
    error("ELEC5305:FinalStatic:SourceMetrics", "Source metric aggregate is incomplete or nonfinite.");
end

mkdir_if_missing(metricsRoot);
mkdir_if_missing(figuresRoot);
mkdir_if_missing(tracksRoot);
perTrackRuntime = zeros(10, 1);
for trackIndex = 1:10
    track = selectedTracks(trackIndex);
    trackName = string(track.track_name_original);
    rank = double(track.rank);
    if rank ~= trackIndex
        error("ELEC5305:FinalStatic:Rank", "Manifest rank/order mismatch.");
    end
    metadataDir = fullfile(tracksRoot, trackName, "metadata");
    completionPath = fullfile(metadataDir, "downstream_metrics_completion.json");
    fprintf("[%d/10] %s\n", rank, trackName);
    if validate_downstream_completion(completionPath, metadataDir, trackName, rank, ...
            protocolHash, manifestHash)
        fprintf("  SKIPPED_COMPLETE\n");
        completion = jsondecode(fileread(completionPath));
        perTrackRuntime(rank) = double(completion.runtime_seconds);
        continue;
    end
    mkdir_if_missing(metadataDir);
    trackStarted = tic;
    [resultsTable, spatialTable, runConfig] = process_track(repoRoot, cacheRoot, ...
        track, subject, conditionConfigs, sampleRate, excerptStartSeconds, ...
        excerptDurationSeconds, expectedInputFrames, maximumDirectionMismatchDeg, ...
        stftConfig, protocolHash, manifestHash, sofaPath, expectedSofaHash);
    downstreamPath = fullfile(metadataDir, "downstream_metrics.csv");
    spatialPath = fullfile(metadataDir, "spatial_configurations.csv");
    runConfigPath = fullfile(metadataDir, "run_config.json");
    atomic_writetable(resultsTable, downstreamPath);
    atomic_writetable(spatialTable, spatialPath);
    atomic_write_json(runConfigPath, runConfig);
    runtimeSeconds = toc(trackStarted);
    perTrackRuntime(rank) = runtimeSeconds;
    completion = struct( ...
        "schema", "phase2_5b_downstream_completion_v1", ...
        "status", "COMPLETE", ...
        "rank", rank, ...
        "track", trackName, ...
        "protocol_sha256", protocolHash, ...
        "manifest_sha256", manifestHash, ...
        "row_count", height(resultsTable), ...
        "runtime_seconds", runtimeSeconds, ...
        "downstream_metrics_sha256", compute_sha256(downstreamPath), ...
        "spatial_configurations_sha256", compute_sha256(spatialPath), ...
        "run_config_sha256", compute_sha256(runConfigPath));
    atomic_write_json(completionPath, completion); % Must be last.
    fprintf("  COMPLETE runtime %.3f s\n", runtimeSeconds);
end

aggregate = collect_downstream_aggregate(selectedTracks, tracksRoot);
if height(aggregate) ~= 30 || numel(unique(aggregate.rank)) ~= 10 || ...
        any(~isfinite(aggregate{:, metric_numeric_columns()}), "all")
    error("ELEC5305:FinalStatic:Aggregate", "Downstream aggregate failed 30-row finite gate.");
end
aggregatePath = fullfile(metricsRoot, "downstream_metrics_per_condition.csv");
atomic_writetable(aggregate, aggregatePath);
rq1FigurePath = fullfile(figuresRoot, "rq1_downstream_vs_spatial_condition.png");
create_rq1_figure(aggregate, rq1FigurePath);

analysisSummaryPath = fullfile(metricsRoot, "final_analysis_summary.json");
representativeStatus = "WAITING_FOR_RQ2";
if isfile(analysisSummaryPath)
    analysisSummary = jsondecode(fileread(analysisSummaryPath));
    rq2Path = fullfile(metricsRoot, "rq2_spearman_correlations.csv");
    sensitivityPath = fullfile(metricsRoot, "rq2_spearman_sensitivity_complete4.csv");
    rq1SummaryPath = fullfile(metricsRoot, "rq1_condition_summary.csv");
    rq2SiSdrFigurePath = fullfile(figuresRoot, "rq2_si_sdr_correlations.png");
    rq2SirFigurePath = fullfile(figuresRoot, "rq2_sir_correlations.png");
    if string(analysisSummary.status) ~= "COMPLETE" || ...
            analysisSummary.rq2_row_count ~= 12 || ...
            analysisSummary.sensitivity_row_count ~= 12 || ...
            analysisSummary.final_song_row_count ~= 10 || ...
            ~isfile(rq2Path) || height(readtable(rq2Path)) ~= 12 || ...
            ~isfile(sensitivityPath) || height(readtable(sensitivityPath)) ~= 12 || ...
            ~isfile(rq1SummaryPath) || height(readtable(rq1SummaryPath)) ~= 9 || ...
            ~isfile(rq2SiSdrFigurePath) || ~isfile(rq2SirFigurePath)
        error("ELEC5305:FinalStatic:AnalysisMarker", "Python final analysis marker is invalid.");
    end
    representativeStatus = generate_representative_artifacts(repoRoot, cacheRoot, ...
        audioRoot, figuresRoot, selectedTracks, subject, conditionConfigs, ...
        sampleRate, excerptStartSeconds, excerptDurationSeconds, expectedInputFrames, ...
        maximumDirectionMismatchDeg, stftConfig, listeningGain, wavBitsPerSample);
else
    fprintf("ANALYSIS_REQUIRED_FOR_REPRESENTATIVE_OUTPUTS\n");
end

summary = struct();
summary.schema = "phase2_5b_matlab_static_summary_v1";
summary.status = "DOWNSTREAM_COMPLETE";
summary.protocol_sha256 = protocolHash;
summary.manifest_sha256 = manifestHash;
summary.track_count = 10;
summary.downstream_row_count = height(aggregate);
summary.per_track_runtime_seconds = perTrackRuntime;
summary.sum_per_track_runtime_seconds = sum(perTrackRuntime);
summary.this_invocation_wall_seconds = toc(overallStarted);
summary.rq1_figure = relative_path(repoRoot, rq1FigurePath);
summary.representative_status = representativeStatus;
summary.matlab_version = version;
summary.matlab_architecture = computer("arch");
atomic_write_json(fullfile(metricsRoot, "matlab_static_summary.json"), summary);
fprintf("DOWNSTREAM_METRICS_COMPLETE tracks=10 rows=30\n");
fprintf("Representative status: %s\n", representativeStatus);

function [resultsTable, spatialTable, runConfig] = process_track(repoRoot, cacheRoot, track, subject, configs, sampleRate, startSeconds, durationSeconds, expectedFrames, maxMismatch, stftConfig, protocolHash, manifestHash, sofaPath, sofaHash)
trackName = string(track.track_name_original);
rank = double(track.rank);
trackDirectory = fullfile(repoRoot, string(track.dataset_relative_path));
cacheDirectory = fullfile(cacheRoot, trackName);
completionPath = fullfile(cacheDirectory, "completion.json");
oracleExcerpt = load_musdb_gt_excerpt(trackDirectory, startSeconds, durationSeconds, sampleRate);
estimatedExcerpt = load_final_cached_excerpt(cacheDirectory, completionPath, ...
    trackName, startSeconds, durationSeconds, sampleRate);
if oracleExcerpt.frame_count ~= expectedFrames || estimatedExcerpt.frame_count ~= expectedFrames || ...
        oracleExcerpt.start_frame_matlab_1_based ~= estimatedExcerpt.start_frame_matlab_1_based || ...
        oracleExcerpt.end_frame_matlab_1_based_inclusive ~= estimatedExcerpt.end_frame_matlab_1_based_inclusive
    error("ELEC5305:FinalStatic:Alignment", "GT/estimated excerpt mismatch for %s.", trackName);
end

resultCells = cell(3, 1);
lookupCells = cell(3, 1);
for conditionIndex = 1:3
    config = configs(conditionIndex);
    [oracleRaw, oracleLookups, oracleDiagnostics] = render_stem_mix( ...
        oracleExcerpt.mono, subject, config.condition, config.azimuths_deg, ...
        config.elevation_deg, maxMismatch);
    [estimatedRaw, estimatedLookups, estimatedDiagnostics] = render_stem_mix( ...
        estimatedExcerpt.mono, subject, config.condition, config.azimuths_deg, ...
        config.elevation_deg, maxMismatch);
    validate_matching_renderers(oracleRaw, estimatedRaw, oracleLookups, ...
        estimatedLookups, oracleDiagnostics, estimatedDiagnostics);
    values = compute_binaural_comparison_metrics(oracleRaw, estimatedRaw, sampleRate, stftConfig);
    result = struct();
    result.rank = rank;
    result.track = trackName;
    result.condition = config.condition;
    result.si_sdr_L_db = values.si_sdr_L_db;
    result.si_sdr_R_db = values.si_sdr_R_db;
    result.binaural_si_sdr_db = values.binaural_si_sdr_db;
    result.relative_rmse_L = values.relative_rmse_L;
    result.relative_rmse_R = values.relative_rmse_R;
    result.relative_rmse_mean = values.relative_rmse_mean;
    result.stft_logmag_mae_L_db = values.stft_logmag_mae_L_db;
    result.stft_logmag_mae_R_db = values.stft_logmag_mae_R_db;
    result.stft_logmag_mae_mean_db = values.stft_logmag_mae_mean_db;
    result.oracle_raw_peak = oracleDiagnostics.raw_peak;
    result.estimated_raw_peak = estimatedDiagnostics.raw_peak;
    result.frames = size(oracleRaw, 1);
    result.sample_rate_hz = sampleRate;
    resultCells{conditionIndex} = result;
    lookupCells{conditionIndex} = oracleLookups;
end
resultsTable = struct2table(vertcat(resultCells{:}));
spatialTable = struct2table(vertcat(lookupCells{:}));
spatialTable = addvars(spatialTable, repmat(rank, height(spatialTable), 1), ...
    repmat(trackName, height(spatialTable), 1), 'Before', 1, ...
    'NewVariableNames', {'rank', 'track'});

runConfig = struct();
runConfig.schema = "phase2_5b_downstream_run_config_v1";
runConfig.rank = rank;
runConfig.track = trackName;
runConfig.protocol_sha256 = protocolHash;
runConfig.manifest_sha256 = manifestHash;
runConfig.selection_sha256 = string(track.selection_sha256);
runConfig.cache_completion_sha256 = compute_sha256(completionPath);
runConfig.gt_directory = relative_path(repoRoot, trackDirectory);
runConfig.estimated_directory = relative_path(repoRoot, cacheDirectory);
runConfig.excerpt = struct("interval", "[30 s, 60 s)", ...
    "start_seconds", startSeconds, "duration_seconds", durationSeconds, ...
    "frames", expectedFrames, "sample_rate_hz", sampleRate);
runConfig.source_order = ["bass", "vocals", "drums", "other"];
runConfig.mono_formula = "x_mono = 0.5 * (x_L + x_R)";
runConfig.preprocessing = "none; exact aligned samples; no normalization, resampling, trimming, loudness matching, peak matching, or alignment";
runConfig.hrtf = struct("dataset", "CIPIC", "subject", "subject_003", ...
    "sofa_path", relative_path(repoRoot, sofaPath), "sofa_sha256", sofaHash, ...
    "elevation_deg", 0, "hrir_length_samples", size(subject.hrir, 3), ...
    "interpolation", "none", "convolution", "full linear convolution");
runConfig.spatial_configurations = configs;
runConfig.stft = stftConfig;
runConfig.scientific_signal_policy = "raw floating-point oracle and estimate; listening gain excluded";
runConfig.matlab_version = version;
runConfig.matlab_architecture = computer("arch");
end

function configs = parse_spatial_conditions(protocol)
expectedNames = ["colocated", "moderate", "wide"];
expectedAzimuths = [0, 0, 0, 0; -30, -10, 10, 30; -80, -30, 30, 80];
conditions = protocol.spatial_conditions;
if numel(conditions) ~= 3
    error("ELEC5305:FinalStatic:Spatial", "Expected three frozen spatial conditions.");
end
configs = repmat(struct(), 3, 1);
for index = 1:3
    name = string(conditions(index).condition);
    azimuths = double(conditions(index).azimuths_deg(:)).';
    order = string(conditions(index).source_order(:)).';
    if name ~= expectedNames(index) || ~isequal(azimuths, expectedAzimuths(index, :)) || ...
            ~isequal(order, ["bass", "vocals", "drums", "other"])
        error("ELEC5305:FinalStatic:Spatial", "Frozen spatial condition mismatch.");
    end
    configs(index).condition = name;
    configs(index).stem_order = order;
    configs(index).azimuths_deg = azimuths;
    configs(index).elevation_deg = double(protocol.hrtf.elevation_deg);
end
end

function valid = validate_downstream_completion(completionPath, metadataDir, trackName, rank, protocolHash, manifestHash)
valid = false;
try
    if ~isfile(completionPath)
        return;
    end
    completion = jsondecode(fileread(completionPath));
    downstreamPath = fullfile(metadataDir, "downstream_metrics.csv");
    spatialPath = fullfile(metadataDir, "spatial_configurations.csv");
    configPath = fullfile(metadataDir, "run_config.json");
    if string(completion.status) ~= "COMPLETE" || string(completion.track) ~= trackName || ...
            completion.rank ~= rank || string(completion.protocol_sha256) ~= protocolHash || ...
            string(completion.manifest_sha256) ~= manifestHash || completion.row_count ~= 3 || ...
            ~all(isfile([string(downstreamPath), string(spatialPath), string(configPath)])) || ...
            string(completion.downstream_metrics_sha256) ~= compute_sha256(downstreamPath) || ...
            string(completion.spatial_configurations_sha256) ~= compute_sha256(spatialPath) || ...
            string(completion.run_config_sha256) ~= compute_sha256(configPath)
        return;
    end
    tableValue = readtable(downstreamPath, "TextType", "string");
    numericColumns = metric_numeric_columns();
    valid = height(tableValue) == 3 && ...
        isequal(string(tableValue.condition).', ["colocated", "moderate", "wide"]) && ...
        all(isfinite(tableValue{:, numericColumns}), "all");
catch
    valid = false;
end
end

function aggregate = collect_downstream_aggregate(selectedTracks, tracksRoot)
tables = cell(10, 1);
for index = 1:10
    trackName = string(selectedTracks(index).track_name_original);
    pathValue = fullfile(tracksRoot, trackName, "metadata", "downstream_metrics.csv");
    if ~isfile(pathValue)
        error("ELEC5305:FinalStatic:MissingPerSong", "Missing downstream metrics for %s.", trackName);
    end
    tables{index} = readtable(pathValue, "TextType", "string");
end
aggregate = vertcat(tables{:});
aggregate = sortrows(aggregate, ["rank", "condition"], ["ascend", "ascend"]);
conditionOrder = categorical(aggregate.condition, ["colocated", "moderate", "wide"], 'Ordinal', true);
aggregate.condition_order_internal = conditionOrder;
aggregate = sortrows(aggregate, ["rank", "condition_order_internal"]);
aggregate.condition_order_internal = [];
end

function columns = metric_numeric_columns()
columns = ["si_sdr_L_db", "si_sdr_R_db", "binaural_si_sdr_db", ...
    "relative_rmse_L", "relative_rmse_R", "relative_rmse_mean", ...
    "stft_logmag_mae_L_db", "stft_logmag_mae_R_db", ...
    "stft_logmag_mae_mean_db", "oracle_raw_peak", ...
    "estimated_raw_peak", "frames", "sample_rate_hz"];
end

function validate_matching_renderers(oracleRaw, estimatedRaw, oracleLookups, estimatedLookups, oracleDiagnostics, estimatedDiagnostics)
if ~isequal(size(oracleRaw), size(estimatedRaw)) || ...
        oracleDiagnostics.input_frames ~= estimatedDiagnostics.input_frames || ...
        oracleDiagnostics.hrir_length ~= estimatedDiagnostics.hrir_length || ...
        oracleDiagnostics.actual_output_frames ~= estimatedDiagnostics.actual_output_frames
    error("ELEC5305:FinalStatic:RendererAlignment", "Oracle/estimated renderer shapes differ.");
end
fields = ["stem", "requested_azimuth_deg", "requested_elevation_deg", ...
    "matched_azimuth_deg", "matched_elevation_deg", "measurement_index", "angular_mismatch_deg"];
for row = 1:numel(oracleLookups)
    for field = fields
        fieldName = char(field);
        if ~isequal(oracleLookups(row).(fieldName), estimatedLookups(row).(fieldName))
            error("ELEC5305:FinalStatic:RendererLookup", "Oracle/estimated HRTF lookups differ.");
        end
    end
end
end

function create_rq1_figure(tableValue, outputPath)
conditions = ["colocated", "moderate", "wide"];
metricNames = ["binaural_si_sdr_db", "relative_rmse_mean", "stft_logmag_mae_mean_db"];
yLabels = ["Binaural SI-SDR (dB)", "Relative waveform RMSE", "STFT log-magnitude MAE (dB)"];
panelTitles = ["A. Binaural SI-SDR (higher is better)", ...
    "B. Relative RMSE (lower is better)", "C. STFT log-mag MAE (lower is better)"];
fig = figure("Visible", "off", "Color", "white", "Position", [100, 100, 1150, 920]);
cleanupFigure = onCleanup(@() close(fig));
layout = tiledlayout(fig, 3, 1, "TileSpacing", "compact", "Padding", "compact");
colors = lines(10);
for panel = 1:3
    ax = nexttile(layout);
    hold(ax, "on");
    values = zeros(10, 3);
    for rank = 1:10
        for conditionIndex = 1:3
            row = tableValue(tableValue.rank == rank & tableValue.condition == conditions(conditionIndex), :);
            values(rank, conditionIndex) = row.(metricNames(panel));
        end
        plot(ax, 1:3, values(rank, :), '-o', "Color", 0.55 * colors(rank, :) + 0.45, ...
            "MarkerSize", 4, "LineWidth", 0.8);
    end
    plot(ax, 1:3, mean(values, 1), '-kd', "MarkerFaceColor", "k", ...
        "MarkerSize", 7, "LineWidth", 2, "DisplayName", "Mean");
    xlim(ax, [0.75, 3.25]);
    xticks(ax, 1:3);
    xticklabels(ax, conditions);
    grid(ax, "on");
    xlabel(ax, "Spatial condition");
    ylabel(ax, yLabels(panel));
    title(ax, panelTitles(panel));
end
title(layout, "Final official-test downstream fidelity: paired song trajectories (N=10)");
exportgraphics(fig, outputPath, "Resolution", 300);
end

function status = generate_representative_artifacts(repoRoot, cacheRoot, audioRoot, figuresRoot, selectedTracks, subject, configs, sampleRate, startSeconds, durationSeconds, expectedFrames, maxMismatch, stftConfig, listeningGain, bitsPerSample)
ranks = [1, 5, 10];
records = struct([]);
recordIndex = 0;
mkdir_if_missing(audioRoot);
for rank = ranks
    track = selectedTracks(rank);
    trackName = string(track.track_name_original);
    trackDirectory = fullfile(repoRoot, string(track.dataset_relative_path));
    cacheDirectory = fullfile(cacheRoot, trackName);
    oracleExcerpt = load_musdb_gt_excerpt(trackDirectory, startSeconds, durationSeconds, sampleRate);
    estimatedExcerpt = load_final_cached_excerpt(cacheDirectory, ...
        fullfile(cacheDirectory, "completion.json"), trackName, startSeconds, durationSeconds, sampleRate);
    if oracleExcerpt.frame_count ~= expectedFrames || estimatedExcerpt.frame_count ~= expectedFrames
        error("ELEC5305:FinalStatic:RepresentativeExcerpt", "Representative excerpt mismatch.");
    end
    trackAudioDir = fullfile(audioRoot, sprintf("rank_%02d", rank), trackName);
    mkdir_if_missing(trackAudioDir);
    for conditionIndex = 1:3
        config = configs(conditionIndex);
        [oracleRaw, oracleLookups, oracleDiagnostics] = render_stem_mix(oracleExcerpt.mono, ...
            subject, config.condition, config.azimuths_deg, config.elevation_deg, maxMismatch);
        [estimatedRaw, estimatedLookups, estimatedDiagnostics] = render_stem_mix(estimatedExcerpt.mono, ...
            subject, config.condition, config.azimuths_deg, config.elevation_deg, maxMismatch);
        validate_matching_renderers(oracleRaw, estimatedRaw, oracleLookups, estimatedLookups, ...
            oracleDiagnostics, estimatedDiagnostics);
        signals = {oracleRaw, estimatedRaw};
        prefixes = ["oracle", "estimated"];
        for signalIndex = 1:2
            signal = listeningGain * signals{signalIndex};
            prewritePeak = max(abs(signal), [], "all");
            if prewritePeak >= 1 || any(~isfinite(signal), "all")
                blocker = struct("status", "CLIPPING_BLOCKER", "rank", rank, ...
                    "track", trackName, "condition", config.condition, ...
                    "signal", prefixes(signalIndex), "fixed_gain", listeningGain, ...
                    "prewrite_peak", prewritePeak, "normalization_applied", false);
                atomic_write_json(fullfile(audioRoot, "representative_audio_summary.json"), blocker);
                error("ELEC5305:FinalStatic:ListeningClipping", ...
                    "Fixed-gain representative audio clips: rank %d %s %s.", ...
                    rank, config.condition, prefixes(signalIndex));
            end
            filename = prefixes(signalIndex) + "_" + config.condition + ".wav";
            pathValue = fullfile(trackAudioDir, filename);
            audiowrite(pathValue, signal, sampleRate, "BitsPerSample", bitsPerSample);
            info = audioinfo(pathValue);
            [decoded, decodedRate] = audioread(pathValue, "double");
            if decodedRate ~= sampleRate || info.NumChannels ~= 2 || ...
                    info.BitsPerSample ~= bitsPerSample || info.TotalSamples ~= size(signal, 1) || ...
                    any(~isfinite(decoded), "all") || max(abs(decoded), [], "all") >= 1
                error("ELEC5305:FinalStatic:ListeningIntegrity", "Written representative WAV invalid.");
            end
            recordIndex = recordIndex + 1;
            records(recordIndex).rank = rank;
            records(recordIndex).track = trackName;
            records(recordIndex).condition = config.condition;
            records(recordIndex).signal = prefixes(signalIndex);
            records(recordIndex).relative_path = relative_path(repoRoot, pathValue);
            records(recordIndex).sample_rate_hz = sampleRate;
            records(recordIndex).channels = 2;
            records(recordIndex).bits_per_sample = bitsPerSample;
            records(recordIndex).frames = info.TotalSamples;
            records(recordIndex).fixed_listening_gain = listeningGain;
            records(recordIndex).raw_peak = max(abs(signals{signalIndex}), [], "all");
            records(recordIndex).prewrite_peak = prewritePeak;
            records(recordIndex).written_peak = max(abs(decoded), [], "all");
            records(recordIndex).clipping = false;
            records(recordIndex).sha256 = compute_sha256(pathValue);
        end
        if rank == 5 && config.condition == "wide"
            create_error_spectrogram(oracleRaw, estimatedRaw, sampleRate, stftConfig, ...
                fullfile(figuresRoot, "representative_rank5_wide_error_spectrogram.png"), trackName);
        end
    end
end
if numel(records) ~= 18
    error("ELEC5305:FinalStatic:RepresentativeCount", "Expected 18 representative WAV records.");
end
summary = struct("schema", "phase2_5b_representative_audio_v1", ...
    "status", "COMPLETE", "selection_rule", "fixed manifest ranks 1, 5, 10", ...
    "demonstration_only", true, "formal_listening_test", false, ...
    "fixed_listening_gain", listeningGain, "output_count", numel(records), ...
    "outputs", records);
atomic_write_json(fullfile(audioRoot, "representative_audio_summary.json"), summary);
status = "COMPLETE";
end

function create_error_spectrogram(oracleRaw, estimatedRaw, sampleRate, config, outputPath, trackName)
window = hann(config.window_length_samples, "periodic");
overlapLength = config.window_length_samples - config.hop_size_samples;
[oracleStft, frequencyHz, timeSeconds] = spectrogram(oracleRaw(:, 1), window, ...
    overlapLength, config.fft_size, sampleRate);
estimatedStft = spectrogram(estimatedRaw(:, 1), window, overlapLength, config.fft_size, sampleRate);
oracleDb = 20 * log10(abs(oracleStft) + eps);
estimatedDb = 20 * log10(abs(estimatedStft) + eps);
differenceDb = abs(estimatedDb - oracleDb);
displayFloor = -100;
displayCeiling = max([oracleDb(:); estimatedDb(:)]);
fig = figure("Visible", "off", "Color", "white", "Position", [100, 100, 1200, 980]);
cleanupFigure = onCleanup(@() close(fig));
layout = tiledlayout(fig, 3, 1, "TileSpacing", "compact", "Padding", "compact");
data = {max(oracleDb, displayFloor), max(estimatedDb, displayFloor), min(differenceDb, 60)};
titles = ["Oracle - left ear", "HTDemucs-FT estimate - left ear", ...
    "Absolute log-magnitude difference - left ear (display capped at 60 dB)"];
for panel = 1:3
    ax = nexttile(layout);
    imagesc(ax, timeSeconds, frequencyHz / 1000, data{panel});
    axis(ax, "xy"); ylim(ax, [0, 20]);
    xlabel(ax, "Time within rendered excerpt (s)"); ylabel(ax, "Frequency (kHz)");
    title(ax, titles(panel)); colorbar(ax);
    if panel < 3, clim(ax, [displayFloor, displayCeiling]); else, clim(ax, [0, 60]); end
end
title(layout, sprintf("Predetermined rank-5 wide illustration: %s", trackName));
exportgraphics(fig, outputPath, "Resolution", 300);
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
if fid < 0, error("ELEC5305:FinalStatic:WriteJSON", "Cannot write %s.", temporary); end
cleanupFile = onCleanup(@() fclose(fid));
fprintf(fid, "%s\n", jsonText);
clear cleanupFile;
movefile(temporary, outputPath, "f");
end

function sha256 = compute_sha256(filePath)
fid = fopen(filePath, "rb");
if fid < 0, error("ELEC5305:FinalStatic:HashRead", "Cannot open %s.", filePath); end
cleanupFile = onCleanup(@() fclose(fid));
digest = java.security.MessageDigest.getInstance("SHA-256");
while true
    bytes = fread(fid, 1024 * 1024, "*uint8");
    if isempty(bytes), break; end
    digest.update(bytes);
end
sha256 = string(lower(reshape(dec2hex(typecast(digest.digest(), "uint8"), 2).', 1, [])));
end

function value = relative_path(repoRoot, absolutePath)
root = string(repoRoot); pathValue = string(absolutePath); prefix = root + filesep;
if startsWith(pathValue, prefix, "IgnoreCase", true)
    value = strrep(extractAfter(pathValue, strlength(prefix)), "\", "/");
else
    value = strrep(pathValue, "\", "/");
end
end

function mkdir_if_missing(pathValue)
if ~isfolder(pathValue), mkdir(pathValue); end
end

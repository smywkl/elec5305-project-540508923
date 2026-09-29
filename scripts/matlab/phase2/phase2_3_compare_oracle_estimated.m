%% Phase 2.3 - Single-track oracle vs HTDemucs-FT spatial comparison
% Fixed validation excerpt only; no inference and no official test data.

oldPath = path;
cleanupPath = onCleanup(@() path(oldPath));
scriptPath = mfilename("fullpath");
repoRoot = fileparts(fileparts(fileparts(fileparts(scriptPath))));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "comparison"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "hrtf"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "oracle"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "spatial"));

phaseName = "Phase 2.3 - Single-Track Oracle vs HTDemucs-FT Spatial Comparison";
trackName = "Swinging Steaks - Lost My Way";
expectedSampleRate = 44100;
excerptStartSeconds = 30;
excerptDurationSeconds = 30;
listeningGain = 0.25;
wavBitsPerSample = 24;
maximumDirectionMismatchDeg = 1;
conditionNames = ["colocated", "moderate", "wide"];
stemOrder = ["bass", "vocals", "drums", "other"];

trackDirectory = fullfile(repoRoot, "data", "musdb18hq", "train", trackName);
mixturePath = fullfile(trackDirectory, "mixture.wav");
sofaPath = fullfile(repoRoot, "data", "hrtf", "cipic", "subject_003.sofa");
phase1Root = fullfile(repoRoot, "outputs", "evaluation", ...
    "source_separation_comparison", "G_pretrained_HTDemucs_FT");
estimatedDirectory = fullfile(phase1Root, "listening", trackName);
phase1MetadataPath = fullfile(phase1Root, "metadata.json");
phase1ResultPath = fullfile(phase1Root, "song_results", trackName, "result.json");
oracleRoot = fullfile(repoRoot, "outputs", "phase2", "phase2_2_oracle", trackName);
oracleConfigPath = fullfile(oracleRoot, "metadata", "oracle_config.json");
spatialConfigPath = fullfile(oracleRoot, "metadata", "spatial_configurations.csv");
outputRoot = fullfile(repoRoot, "outputs", "phase2", "phase2_3_comparison", trackName);
audioDir = fullfile(outputRoot, "audio");
figuresDir = fullfile(outputRoot, "figures");
metadataDir = fullfile(outputRoot, "metadata");

fprintf("%s\n", phaseName);
fprintf("Repository root: %s\n", repoRoot);

requiredInputs = [mixturePath, sofaPath, phase1MetadataPath, ...
    phase1ResultPath, oracleConfigPath, spatialConfigPath];
if ~all(isfile(requiredInputs)) || ~isfolder(estimatedDirectory)
    error("ELEC5305:Phase2_3:MissingInput", ...
        "Required Phase 1 G, Phase 2.2, dataset, or HRTF input is missing.");
end

oracleConfig = jsondecode(fileread(oracleConfigPath));
validate_oracle_config(oracleConfig, trackName, expectedSampleRate, ...
    excerptStartSeconds, excerptDurationSeconds, listeningGain);
stftConfig = struct( ...
    "window_length_samples", oracleConfig.stft.window_length_samples, ...
    "hop_size_samples", oracleConfig.stft.hop_size_samples, ...
    "fft_size", oracleConfig.stft.fft_size, ...
    "window_type", string(oracleConfig.stft.window_type));

spatialTable = readtable(spatialConfigPath, "TextType", "string");
spatialConfigurations = validate_spatial_configurations( ...
    spatialTable, conditionNames, stemOrder);

subject = load_cipic_subject(sofaPath);
if subject.fs ~= expectedSampleRate || string(oracleConfig.cipic_subject) ~= "subject_003"
    error("ELEC5305:Phase2_3:HRTFIdentity", ...
        "Phase 2.2 HRTF identity or sample rate is not the frozen configuration.");
end
oracleExcerpt = load_musdb_gt_excerpt(trackDirectory, excerptStartSeconds, ...
    excerptDurationSeconds, expectedSampleRate);
estimatedExcerpt = load_estimated_excerpt(estimatedDirectory, phase1ResultPath, ...
    phase1MetadataPath, mixturePath, trackName, excerptStartSeconds, ...
    excerptDurationSeconds, expectedSampleRate);
if oracleExcerpt.frame_count ~= 1323000 || ...
        estimatedExcerpt.frame_count ~= oracleExcerpt.frame_count || ...
        estimatedExcerpt.start_frame_matlab_1_based ~= oracleExcerpt.start_frame_matlab_1_based || ...
        estimatedExcerpt.end_frame_matlab_1_based_inclusive ~= oracleExcerpt.end_frame_matlab_1_based_inclusive
    error("ELEC5305:Phase2_3:ExcerptAlignment", ...
        "Oracle and estimated excerpts do not share the frozen [30 s, 60 s) sample range.");
end

run_si_sdr_unit_test(expectedSampleRate, stftConfig);

if isfolder(outputRoot)
    rmdir(outputRoot, "s");
end
mkdir(audioDir);
mkdir(figuresDir);
mkdir(metadataDir);
writetable(estimatedExcerpt.stats, fullfile(metadataDir, "estimated_input_stats.csv"));

results = struct([]);
audioOutputs = repmat(struct(), numel(conditionNames), 1);
wideOracleRaw = [];
wideEstimatedRaw = [];

for conditionIndex = 1:numel(conditionNames)
    configuration = spatialConfigurations(conditionIndex);
    conditionName = string(configuration.condition);
    azimuthsDeg = double(configuration.azimuths_deg);
    elevationDeg = double(configuration.elevation_deg);

    [oracleRaw, oracleLookups, oracleDiagnostics] = render_stem_mix( ...
        oracleExcerpt.mono, subject, conditionName, azimuthsDeg, elevationDeg, ...
        maximumDirectionMismatchDeg);
    [estimatedRaw, estimatedLookups, estimatedDiagnostics] = render_stem_mix( ...
        estimatedExcerpt.mono, subject, conditionName, azimuthsDeg, elevationDeg, ...
        maximumDirectionMismatchDeg);
    validate_matching_renderers(oracleRaw, estimatedRaw, oracleLookups, ...
        estimatedLookups, oracleDiagnostics, estimatedDiagnostics);

    metricValues = compute_binaural_comparison_metrics( ...
        oracleRaw, estimatedRaw, expectedSampleRate, stftConfig);
    result = metricValues;
    result.condition = conditionName;
    result.oracle_raw_peak = oracleDiagnostics.raw_peak;
    result.estimated_raw_peak = estimatedDiagnostics.raw_peak;
    result.oracle_rms_L = oracleDiagnostics.raw_left_rms;
    result.oracle_rms_R = oracleDiagnostics.raw_right_rms;
    result.estimated_rms_L = estimatedDiagnostics.raw_left_rms;
    result.estimated_rms_R = estimatedDiagnostics.raw_right_rms;
    result.frames = size(oracleRaw, 1);
    result.sample_rate_hz = expectedSampleRate;
    if conditionIndex == 1
        results = result;
    else
        results(conditionIndex) = result;
    end

    listeningAudio = listeningGain * estimatedRaw;
    prewritePeak = max(abs(listeningAudio), [], "all");
    if any(~isfinite(listeningAudio), "all") || prewritePeak > 1
        error("ELEC5305:Phase2_3:ListeningIntegrity", ...
            "%s estimated listening audio is nonfinite or clips at fixed gain %.12g.", ...
            conditionName, listeningGain);
    end
    wavFilename = "estimated_" + conditionName + ".wav";
    wavPath = fullfile(audioDir, wavFilename);
    audiowrite(wavPath, listeningAudio, expectedSampleRate, ...
        "BitsPerSample", wavBitsPerSample);
    [decodedAudio, decodedSampleRate] = audioread(wavPath, "double");
    info = audioinfo(wavPath);
    decodedPeak = max(abs(decodedAudio), [], "all");
    if decodedSampleRate ~= expectedSampleRate || info.SampleRate ~= expectedSampleRate || ...
            info.NumChannels ~= 2 || info.BitsPerSample ~= wavBitsPerSample || ...
            info.TotalSamples ~= size(estimatedRaw, 1) || ...
            any(~isfinite(decodedAudio), "all") || decodedPeak >= 1
        error("ELEC5305:Phase2_3:WrittenWAVIntegrity", ...
            "Written WAV integrity check failed for %s.", wavPath);
    end
    audioOutputs(conditionIndex).condition = conditionName;
    audioOutputs(conditionIndex).relative_path = ...
        strrep(fullfile("audio", wavFilename), "\", "/");
    audioOutputs(conditionIndex).sample_rate_hz = decodedSampleRate;
    audioOutputs(conditionIndex).bits_per_sample = info.BitsPerSample;
    audioOutputs(conditionIndex).channels = info.NumChannels;
    audioOutputs(conditionIndex).frames = info.TotalSamples;
    audioOutputs(conditionIndex).raw_peak = estimatedDiagnostics.raw_peak;
    audioOutputs(conditionIndex).prewrite_peak_after_listening_gain = prewritePeak;
    audioOutputs(conditionIndex).written_peak = decodedPeak;
    audioOutputs(conditionIndex).finite = all(isfinite(decodedAudio), "all");
    audioOutputs(conditionIndex).clipping = decodedPeak >= 1;

    if conditionName == "wide"
        wideOracleRaw = oracleRaw;
        wideEstimatedRaw = estimatedRaw;
    end
    fprintf("%s: SI-SDR L/R/mean %.6f / %.6f / %.6f dB | " + ...
        "relative RMSE %.6f | STFT MAE %.6f dB | estimated raw peak %.9f\n", ...
        conditionName, result.si_sdr_L_db, result.si_sdr_R_db, ...
        result.binaural_si_sdr_db, result.relative_rmse_mean, ...
        result.stft_logmag_mae_mean_db, result.estimated_raw_peak);
end

resultsTable = struct2table(results);
resultsTable = movevars(resultsTable, "condition", "Before", 1);
writetable(resultsTable, fullfile(metadataDir, "comparison_results.csv"));
create_metrics_figure(resultsTable, fullfile(figuresDir, ...
    "downstream_metrics_vs_spread.png"));
create_wide_error_spectrogram(wideOracleRaw, wideEstimatedRaw, ...
    expectedSampleRate, stftConfig, fullfile(figuresDir, ...
    "wide_oracle_estimated_error_spectrogram.png"));

comparisonConfig = struct();
comparisonConfig.phase = phaseName;
comparisonConfig.code_version = "phase2.3-single-track-comparison-v1";
comparisonConfig.track = trackName;
comparisonConfig.split = "validation";
comparisonConfig.official_test_used = false;
comparisonConfig.excerpt = struct( ...
    "start_seconds", excerptStartSeconds, ...
    "duration_seconds", excerptDurationSeconds, ...
    "interval", "[30 s, 60 s)", ...
    "start_frame_matlab_1_based", oracleExcerpt.start_frame_matlab_1_based, ...
    "end_frame_matlab_1_based_inclusive", oracleExcerpt.end_frame_matlab_1_based_inclusive, ...
    "input_frames", oracleExcerpt.frame_count, ...
    "rendered_frames", results(1).frames, ...
    "alignment_rule", "exact same integer sample range; no trim, resample, or cross-correlation alignment");
comparisonConfig.sample_rate_hz = expectedSampleRate;
comparisonConfig.oracle_metadata_path = relative_path(repoRoot, oracleConfigPath);
comparisonConfig.oracle_raw_source = ...
    "re-rendered from Phase 2.2 GT excerpt with shared render_stem_mix; listening WAV not used for metrics";
comparisonConfig.g_estimated_source_paths = estimatedExcerpt.source_paths;
modelConfig = estimatedExcerpt.phase1_metadata.model_configuration;
comparisonConfig.g_model_identity = struct( ...
    "configuration", string(modelConfig.configuration), ...
    "repository", string(modelConfig.repository), ...
    "revision", string(modelConfig.revision), ...
    "official_pretrained", logical(modelConfig.official_pretrained), ...
    "custom_checkpoint_used", logical(modelConfig.custom_checkpoint_used), ...
    "configuration_fingerprint", string(estimatedExcerpt.phase1_metadata.configuration_fingerprint), ...
    "model_source_order", {string(modelConfig.model_source_order)}, ...
    "evaluation_source_order", {string(modelConfig.evaluation_source_order)}, ...
    "models", {modelConfig.models});
comparisonConfig.mono_formula = "x_mono = 0.5 * (x_L + x_R)";
comparisonConfig.hrtf_subject = string(oracleConfig.cipic_subject);
comparisonConfig.hrtf_sofa_path = string(oracleConfig.sofa_path);
comparisonConfig.hrtf_sofa_sha256 = string(oracleConfig.sofa_sha256);
comparisonConfig.hrtf_pipeline = ...
    "oracle and estimate both call render_stem_mix -> find_hrir_direction -> render_static_binaural; full convolution; fixed stem summation order";
comparisonConfig.spatial_configuration_source = relative_path(repoRoot, spatialConfigPath);
comparisonConfig.spatial_configurations = spatialConfigurations;
comparisonConfig.listening_gain = listeningGain;
comparisonConfig.listening_gain_db = 20 * log10(listeningGain);
comparisonConfig.gain_policy = ...
    "raw metrics; fixed 0.25 only for estimated listening WAV; no normalisation or level matching";
comparisonConfig.si_sdr_definition = ...
    "per ear after zero-mean: alpha=dot(shat,s)/dot(s,s), target=alpha*s, noise=shat-target, 10log10(sum(target^2)/sum(noise^2)); perfect case finite-capped at 300 dB; binaural mean of ears";
comparisonConfig.relative_rmse_definition = ...
    "per ear RMS(estimate-oracle)/RMS(oracle); arithmetic mean of ears";
comparisonConfig.stft_metric_definition = ...
    "per ear mean(abs(20log10(abs(STFT_est)+eps)-20log10(abs(STFT_oracle)+eps))); arithmetic mean of ears";
comparisonConfig.stft = struct( ...
    "window_type", stftConfig.window_type, ...
    "window_length_samples", stftConfig.window_length_samples, ...
    "hop_size_samples", stftConfig.hop_size_samples, ...
    "overlap_samples", stftConfig.window_length_samples - stftConfig.hop_size_samples, ...
    "fft_size", stftConfig.fft_size, ...
    "source", "Phase 2.2 oracle_config.json");
comparisonConfig.estimated_audio_outputs = audioOutputs;
comparisonConfig.matlab_version = version;
comparisonConfig.matlab_architecture = computer("arch");
comparisonConfig.output_overwrite_policy = ...
    "deterministic rerun replaces only this fixed Phase 2.3 development-track output tree";
write_json(fullfile(metadataDir, "comparison_config.json"), comparisonConfig);

requiredOutputs = [ ...
    fullfile(audioDir, "estimated_colocated.wav"), ...
    fullfile(audioDir, "estimated_moderate.wav"), ...
    fullfile(audioDir, "estimated_wide.wav"), ...
    fullfile(figuresDir, "downstream_metrics_vs_spread.png"), ...
    fullfile(figuresDir, "wide_oracle_estimated_error_spectrogram.png"), ...
    fullfile(metadataDir, "comparison_results.csv"), ...
    fullfile(metadataDir, "estimated_input_stats.csv"), ...
    fullfile(metadataDir, "comparison_config.json")];
assert(all(isfile(requiredOutputs)), "One or more required Phase 2.3 artifacts are missing.");
fprintf("G cached estimates reused: true\n");
fprintf("Exact excerpt alignment: true (%d input frames)\n", oracleExcerpt.frame_count);
fprintf("Official test used: false\n");
fprintf("PHASE2_3_COMPARISON_COMPLETE\n");

function validate_oracle_config(config, trackName, sampleRate, startSeconds, durationSeconds, listeningGain)
if string(config.track) ~= trackName || string(config.split) ~= "validation" || ...
        logical(config.official_test_used) || config.sample_rate_hz ~= sampleRate || ...
        config.excerpt.start_seconds ~= startSeconds || ...
        config.excerpt.duration_seconds ~= durationSeconds || ...
        config.excerpt.frames ~= durationSeconds * sampleRate || ...
        config.listening_gain ~= listeningGain || ...
        string(config.mono_equation) ~= "x_mono = 0.5 * (x_L + x_R)"
    error("ELEC5305:Phase2_3:OracleConfig", ...
        "Phase 2.2 oracle configuration is not the frozen Phase 2.3 source.");
end
end

function configurations = validate_spatial_configurations(tableValue, conditionNames, stemOrder)
requiredColumns = ["condition", "stem", "requested_azimuth_deg", ...
    "requested_elevation_deg", "matched_azimuth_deg", ...
    "matched_elevation_deg", "measurement_index", "angular_mismatch_deg"];
if ~all(ismember(requiredColumns, string(tableValue.Properties.VariableNames))) || ...
        height(tableValue) ~= 12
    error("ELEC5305:Phase2_3:SpatialConfig", ...
        "Phase 2.2 spatial configuration table is incomplete.");
end
configurations = repmat(struct(), numel(conditionNames), 1);
for conditionIndex = 1:numel(conditionNames)
    conditionName = conditionNames(conditionIndex);
    rows = tableValue(string(tableValue.condition) == conditionName, :);
    if height(rows) ~= 4 || ~isequal(string(rows.stem).', stemOrder) || ...
            any(rows.angular_mismatch_deg ~= 0) || ...
            any(rows.requested_azimuth_deg ~= rows.matched_azimuth_deg) || ...
            any(rows.requested_elevation_deg ~= rows.matched_elevation_deg) || ...
            numel(unique(rows.requested_elevation_deg)) ~= 1
        error("ELEC5305:Phase2_3:SpatialConfig", ...
            "Spatial rows for %s violate the frozen Phase 2.2 mapping.", conditionName);
    end
    configurations(conditionIndex).condition = conditionName;
    configurations(conditionIndex).stem_order = stemOrder;
    configurations(conditionIndex).azimuths_deg = rows.requested_azimuth_deg.';
    configurations(conditionIndex).elevation_deg = rows.requested_elevation_deg(1);
end
end

function run_si_sdr_unit_test(sampleRate, stftConfig)
t = (0:4095).' / sampleRate;
reference = [sin(2 * pi * 440 * t), sin(2 * pi * 660 * t + 0.2)];
identical = compute_binaural_comparison_metrics(reference, reference, sampleRate, stftConfig);
scaled = compute_binaural_comparison_metrics(reference, 2.5 * reference, sampleRate, stftConfig);
if identical.binaural_si_sdr_db < 250 || scaled.binaural_si_sdr_db < 250 || ...
        abs(identical.binaural_si_sdr_db - scaled.binaural_si_sdr_db) > 1e-12
    error("ELEC5305:Phase2_3:SISDRUnitTest", ...
        "Transparent SI-SDR failed perfect or scale-invariance synthetic test.");
end
fprintf("SI-SDR synthetic unit test: passed (perfect/scaled %.3f / %.3f dB)\n", ...
    identical.binaural_si_sdr_db, scaled.binaural_si_sdr_db);
end

function validate_matching_renderers(oracleRaw, estimatedRaw, oracleLookups, estimatedLookups, oracleDiagnostics, estimatedDiagnostics)
if ~isequal(size(oracleRaw), size(estimatedRaw)) || ...
        oracleDiagnostics.input_frames ~= estimatedDiagnostics.input_frames || ...
        oracleDiagnostics.hrir_length ~= estimatedDiagnostics.hrir_length || ...
        oracleDiagnostics.actual_output_frames ~= estimatedDiagnostics.actual_output_frames
    error("ELEC5305:Phase2_3:RendererAlignment", ...
        "Oracle and estimated renderer shapes or lengths differ.");
end
fields = ["stem", "requested_azimuth_deg", "requested_elevation_deg", ...
    "matched_azimuth_deg", "matched_elevation_deg", "measurement_index", ...
    "angular_mismatch_deg"];
for row = 1:numel(oracleLookups)
    for fieldIndex = 1:numel(fields)
        fieldName = char(fields(fieldIndex));
        if ~isequal(oracleLookups(row).(fieldName), estimatedLookups(row).(fieldName))
            error("ELEC5305:Phase2_3:RendererLookup", ...
                "Oracle and estimated HRTF lookups differ.");
        end
    end
end
end

function create_metrics_figure(resultsTable, outputPath)
fig = figure("Visible", "off", "Color", "white", "Position", [100, 100, 1050, 900]);
cleanupFigure = onCleanup(@() close(fig));
layout = tiledlayout(fig, 3, 1, "TileSpacing", "compact", "Padding", "compact");
x = categorical(string(resultsTable.condition), string(resultsTable.condition));
values = {resultsTable.binaural_si_sdr_db, resultsTable.relative_rmse_mean, ...
    resultsTable.stft_logmag_mae_mean_db};
yLabels = ["Binaural SI-SDR (dB)", "Relative waveform RMSE", ...
    "STFT log-magnitude MAE (dB)"];
panelTitles = ["A. Binaural SI-SDR (higher is better)", ...
    "B. Relative waveform RMSE (lower is better)", ...
    "C. STFT log-magnitude MAE (lower is better)"];
for panel = 1:3
    ax = nexttile(layout);
    bar(ax, x, values{panel}, 0.65);
    grid(ax, "on");
    xlabel(ax, "Spatial condition");
    ylabel(ax, yLabels(panel));
    title(ax, panelTitles(panel));
end
title(layout, "Oracle vs HTDemucs-FT downstream metrics - Development track only");
exportgraphics(fig, outputPath, "Resolution", 300);
end

function create_wide_error_spectrogram(oracleRaw, estimatedRaw, sampleRate, config, outputPath)
if isempty(oracleRaw) || isempty(estimatedRaw)
    error("ELEC5305:Phase2_3:WideFigure", "Wide raw signals are unavailable.");
end
window = hann(config.window_length_samples, "periodic");
overlapLength = config.window_length_samples - config.hop_size_samples;
[oracleStft, frequencyHz, timeSeconds] = spectrogram(oracleRaw(:, 1), ...
    window, overlapLength, config.fft_size, sampleRate);
estimatedStft = spectrogram(estimatedRaw(:, 1), window, overlapLength, ...
    config.fft_size, sampleRate);
oracleDb = 20 * log10(abs(oracleStft) + eps);
estimatedDb = 20 * log10(abs(estimatedStft) + eps);
differenceDb = abs(estimatedDb - oracleDb);
displayFloor = -100;
displayCeiling = max([oracleDb(:); estimatedDb(:)]);

fig = figure("Visible", "off", "Color", "white", "Position", [100, 100, 1200, 980]);
cleanupFigure = onCleanup(@() close(fig));
layout = tiledlayout(fig, 3, 1, "TileSpacing", "compact", "Padding", "compact");
data = {max(oracleDb, displayFloor), max(estimatedDb, displayFloor), ...
    min(differenceDb, 60)};
panelTitles = ["Oracle - left ear", "HTDemucs-FT estimate - left ear", ...
    "Absolute log-magnitude difference - left ear (display capped at 60 dB)"];
for panel = 1:3
    ax = nexttile(layout);
    imagesc(ax, timeSeconds, frequencyHz / 1000, data{panel});
    axis(ax, "xy");
    ylim(ax, [0, 20]);
    xlabel(ax, "Time within rendered excerpt (s)");
    ylabel(ax, "Frequency (kHz)");
    title(ax, panelTitles(panel));
    colorbar(ax);
    if panel < 3
        clim(ax, [displayFloor, displayCeiling]);
    else
        clim(ax, [0, 60]);
    end
end
title(layout, sprintf("Wide oracle/estimated/error spectrogram - Development track only " + ...
    "(periodic Hann %d, hop %d, NFFT %d)", ...
    config.window_length_samples, config.hop_size_samples, config.fft_size));
exportgraphics(fig, outputPath, "Resolution", 300);
end

function value = relative_path(repoRoot, absolutePath)
root = string(repoRoot);
pathValue = string(absolutePath);
prefix = root + filesep;
if startsWith(pathValue, prefix, "IgnoreCase", true)
    value = strrep(extractAfter(pathValue, strlength(prefix)), "\", "/");
else
    value = strrep(pathValue, "\", "/");
end
end

function write_json(outputPath, value)
jsonText = jsonencode(value, "PrettyPrint", true);
fid = fopen(outputPath, "w", "n", "UTF-8");
if fid < 0
    error("ELEC5305:Phase2_3:WriteJSON", "Cannot write JSON file: %s", outputPath);
end
cleanupFile = onCleanup(@() fclose(fid));
fprintf(fid, "%s\n", jsonText);
end

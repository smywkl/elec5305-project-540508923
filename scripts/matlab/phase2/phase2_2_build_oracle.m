%% Phase 2.2 - Oracle static spatialisation pipeline
% MUSDB18-HQ ground-truth stems -> fixed mono downmix -> static HRTF oracle.

oldPath = path;
cleanupPath = onCleanup(@() path(oldPath));
scriptPath = mfilename("fullpath");
repoRoot = fileparts(fileparts(fileparts(fileparts(scriptPath))));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "hrtf"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "oracle"));

phaseName = "Phase 2.2 - Oracle Static Spatialisation Pipeline";
trackName = "Swinging Steaks - Lost My Way";
splitRelativePath = fullfile("outputs", "training", "openunmix", "split.json");
splitPath = fullfile(repoRoot, splitRelativePath);
datasetRelativeRoot = fullfile("data", "musdb18hq", "train");
datasetRoot = fullfile(repoRoot, datasetRelativeRoot);
trackDirectory = fullfile(datasetRoot, trackName);
sofaRelativePath = fullfile("data", "hrtf", "cipic", "subject_003.sofa");
sofaPath = fullfile(repoRoot, sofaRelativePath);
outputRoot = fullfile(repoRoot, "outputs", "phase2", "phase2_2_oracle", trackName);
audioDir = fullfile(outputRoot, "audio");
metadataDir = fullfile(outputRoot, "metadata");
figuresDir = fullfile(outputRoot, "figures");

expectedSampleRate = 44100;
excerptStartSeconds = 30.0;
excerptDurationSeconds = 30.0;
listeningGain = 0.25;
wavBitsPerSample = 24;
maximumDirectionMismatchDeg = 1;
maximumStemSumRelativeRmsError = 5e-4;
maximumStemSumAbsoluteError = 5e-4;
expectedSofaSHA256 = "A9DB5F938ED1113B118DCBEB43F5FE1B27B9E191D1BBDB63FBC4803B6959B220";
overwriteExisting = should_overwrite_existing();

stemOrder = ["bass", "vocals", "drums", "other"];
conditionNames = ["colocated", "moderate", "wide"];
azimuthMatrix = [0, 0, 0, 0; -30, -10, 10, 30; -80, -30, 30, 80];
elevationDeg = 0;

stftWindowLength = 1024;
stftHopSize = 256;
stftFFTSize = 1024;
stftWindowType = "periodic Hann";
stftDbFloor = -100;

fprintf("%s\n", phaseName);
fprintf("Repository root: %s\n", repoRoot);

if ~isfile(splitPath)
    error("ELEC5305:Phase2_2:MissingSplit", "Required split.json is missing: %s", splitPath);
end
split = jsondecode(fileread(splitPath));
if ~isfield(split, "validation") || ~any(strcmp(string(split.validation), trackName))
    error("ELEC5305:Phase2_2:WrongSplit", ...
        "Track '%s' is not listed in split.json validation.", trackName);
end
if ~isfield(split, "official_test_used") || logical(split.official_test_used)
    error("ELEC5305:Phase2_2:OfficialTestLock", ...
        "split.json does not confirm official_test_used=false.");
end
if ~isfolder(trackDirectory)
    error("ELEC5305:Phase2_2:MissingTrack", "Validation track directory is missing: %s", trackDirectory);
end
if ~isfile(sofaPath)
    error("ELEC5305:Phase2_2:MissingSOFA", "Required SOFA file is missing: %s", sofaPath);
end

sofaSHA256 = compute_sha256(sofaPath);
if sofaSHA256 ~= expectedSofaSHA256
    error("ELEC5305:Phase2_2:SOFAHash", ...
        "SOFA SHA-256 mismatch: expected %s, received %s.", expectedSofaSHA256, sofaSHA256);
end

if isfolder(outputRoot)
    if ~overwriteExisting
        error("ELEC5305:Phase2_2:OutputExists", ...
            "Output directory exists and overwriteExisting=false: %s", outputRoot);
    end
    rmdir(outputRoot, "s");
end
mkdir(audioDir);
mkdir(metadataDir);
mkdir(figuresDir);

subject = load_cipic_subject(sofaPath);
if subject.fs ~= expectedSampleRate
    error("ELEC5305:Phase2_2:HRTFSampleRate", ...
        "SOFA sample rate %.12g Hz does not match expected %.12g Hz.", ...
        subject.fs, expectedSampleRate);
end

excerpt = load_musdb_gt_excerpt(trackDirectory, excerptStartSeconds, ...
    excerptDurationSeconds, expectedSampleRate);
writetable(excerpt.stats, fullfile(metadataDir, "input_stats.csv"));

stereoStemSum = excerpt.stereo.bass + excerpt.stereo.vocals + ...
    excerpt.stereo.drums + excerpt.stereo.other;
monoStemSum = excerpt.mono.bass + excerpt.mono.vocals + ...
    excerpt.mono.drums + excerpt.mono.other;
stereoValidation = residual_metrics(excerpt.stereo.mixture, stereoStemSum);
monoValidation = residual_metrics(excerpt.mono.mixture, monoStemSum);
if stereoValidation.relative_rms_error > maximumStemSumRelativeRmsError || ...
        stereoValidation.max_abs_error > maximumStemSumAbsoluteError || ...
        monoValidation.relative_rms_error > maximumStemSumRelativeRmsError || ...
        monoValidation.max_abs_error > maximumStemSumAbsoluteError
    error("ELEC5305:Phase2_2:StemSum", ...
        "GT stem-sum residual exceeds engineering threshold; inspect alignment/data before HRTF rendering.");
end
stemSumValidation = struct();
stemSumValidation.definition = ...
    "RMS values use all frames/channels; relative_rms_error=residual_rms/(reference_rms+eps)";
stemSumValidation.thresholds = struct( ...
    "maximum_relative_rms_error", maximumStemSumRelativeRmsError, ...
    "maximum_absolute_error", maximumStemSumAbsoluteError);
stemSumValidation.stereo_mixture_vs_sum_stems = stereoValidation;
stemSumValidation.mono_mixture_vs_sum_mono_stems = monoValidation;
stemSumValidation.passed = true;
write_json(fullfile(metadataDir, "stem_sum_validation.json"), stemSumValidation);

lookupCells = cell(numel(conditionNames), 1);
conditionDiagnosticCells = cell(numel(conditionNames), 1);
audioOutputs = repmat(struct(), numel(conditionNames), 1);
writtenSignals = struct();

for conditionIndex = 1:numel(conditionNames)
    conditionName = conditionNames(conditionIndex);
    [oracleRaw, lookups, renderDiagnostics] = render_oracle_mix( ...
        excerpt.mono, subject, conditionName, azimuthMatrix(conditionIndex, :), ...
        elevationDeg, maximumDirectionMismatchDeg);
    lookupCells{conditionIndex} = lookups;
    conditionDiagnosticCells{conditionIndex} = renderDiagnostics;

    listeningAudio = listeningGain * oracleRaw;
    if any(~isfinite(listeningAudio), "all")
        error("ELEC5305:Phase2_2:NonfiniteOutput", ...
            "%s listening signal contains NaN or Inf.", conditionName);
    end
    prewritePeak = max(abs(listeningAudio), [], "all");
    if prewritePeak >= 1
        error("ELEC5305:Phase2_2:Clipping", ...
            "%s still clips at fixed listening gain %.12g (peak %.12g).", ...
            conditionName, listeningGain, prewritePeak);
    end

    wavFilename = "oracle_" + conditionName + ".wav";
    wavPath = fullfile(audioDir, wavFilename);
    audiowrite(wavPath, listeningAudio, expectedSampleRate, ...
        "BitsPerSample", wavBitsPerSample);
    [decodedAudio, decodedSampleRate] = audioread(wavPath, "double");
    info = audioinfo(wavPath);
    decodedPeak = max(abs(decodedAudio), [], "all");
    integrityPassed = decodedSampleRate == expectedSampleRate && ...
        info.SampleRate == expectedSampleRate && info.NumChannels == 2 && ...
        info.BitsPerSample == wavBitsPerSample && ...
        size(decodedAudio, 1) == renderDiagnostics.actual_output_frames && ...
        all(isfinite(decodedAudio), "all") && decodedPeak < 1;
    if ~integrityPassed
        error("ELEC5305:Phase2_2:WAVIntegrity", ...
            "Written WAV integrity check failed for %s.", wavPath);
    end

    fieldName = char(conditionName);
    writtenSignals.(fieldName) = decodedAudio;
    audioOutputs(conditionIndex).condition = conditionName;
    audioOutputs(conditionIndex).relative_path = ...
        strrep(fullfile("audio", wavFilename), "\", "/");
    audioOutputs(conditionIndex).sample_rate_hz = decodedSampleRate;
    audioOutputs(conditionIndex).bits_per_sample = info.BitsPerSample;
    audioOutputs(conditionIndex).channels = info.NumChannels;
    audioOutputs(conditionIndex).frames = size(decodedAudio, 1);
    audioOutputs(conditionIndex).duration_seconds = size(decodedAudio, 1) / decodedSampleRate;
    audioOutputs(conditionIndex).raw_peak = renderDiagnostics.raw_peak;
    audioOutputs(conditionIndex).raw_left_rms = renderDiagnostics.raw_left_rms;
    audioOutputs(conditionIndex).raw_right_rms = renderDiagnostics.raw_right_rms;
    audioOutputs(conditionIndex).raw_stereo_rms = sqrt(mean(oracleRaw .^ 2, "all"));
    audioOutputs(conditionIndex).prewrite_peak_after_listening_gain = prewritePeak;
    audioOutputs(conditionIndex).written_peak = decodedPeak;
    audioOutputs(conditionIndex).written_left_rms = sqrt(mean(decodedAudio(:, 1) .^ 2));
    audioOutputs(conditionIndex).written_right_rms = sqrt(mean(decodedAudio(:, 2) .^ 2));
    audioOutputs(conditionIndex).written_stereo_rms = sqrt(mean(decodedAudio .^ 2, "all"));
    audioOutputs(conditionIndex).finite = all(isfinite(decodedAudio), "all");
    audioOutputs(conditionIndex).clipping = decodedPeak >= 1;
end

allLookups = vertcat(lookupCells{:});
conditionDiagnostics = vertcat(conditionDiagnosticCells{:});
lookupTable = struct2table(allLookups);
if height(lookupTable) ~= 12
    error("ELEC5305:Phase2_2:LookupCount", "Expected exactly 12 direction lookup rows.");
end
writetable(lookupTable, fullfile(metadataDir, "spatial_configurations.csv"));

create_wide_spectrogram(writtenSignals.wide, expectedSampleRate, ...
    stftWindowLength, stftHopSize, stftFFTSize, stftDbFloor, ...
    fullfile(figuresDir, "oracle_wide_spectrogram.png"));
create_condition_level_figure(conditionNames, conditionDiagnostics, ...
    fullfile(figuresDir, "oracle_condition_levels.png"));

spatialConfigurations = repmat(struct(), numel(conditionNames), 1);
for conditionIndex = 1:numel(conditionNames)
    spatialConfigurations(conditionIndex).condition = conditionNames(conditionIndex);
    spatialConfigurations(conditionIndex).stem_order = stemOrder;
    spatialConfigurations(conditionIndex).azimuths_deg = azimuthMatrix(conditionIndex, :);
    spatialConfigurations(conditionIndex).elevation_deg = elevationDeg;
end

oracleConfig = struct();
oracleConfig.phase = phaseName;
oracleConfig.code_version = "phase2.2-oracle-static-v1";
oracleConfig.track = trackName;
oracleConfig.split = "validation";
oracleConfig.split_path = strrep(splitRelativePath, "\", "/");
oracleConfig.official_test_used = false;
oracleConfig.dataset_root = strrep(datasetRelativeRoot, "\", "/");
oracleConfig.excerpt = struct( ...
    "start_seconds", excerptStartSeconds, ...
    "duration_seconds", excerptDurationSeconds, ...
    "interval", "[30 s, 60 s)", ...
    "start_frame_matlab_1_based", excerpt.start_frame_matlab_1_based, ...
    "end_frame_matlab_1_based_inclusive", excerpt.end_frame_matlab_1_based_inclusive, ...
    "frames", excerpt.frame_count);
oracleConfig.sample_rate_hz = expectedSampleRate;
oracleConfig.channel_convention = "input GT is stereo [left,right]; oracle output is binaural [left,right]";
oracleConfig.mono_equation = "x_mono = 0.5 * (x_L + x_R)";
oracleConfig.cipic_subject = "subject_003";
oracleConfig.sofa_path = strrep(sofaRelativePath, "\", "/");
oracleConfig.sofa_sha256 = sofaSHA256;
oracleConfig.spatial_configurations = spatialConfigurations;
oracleConfig.hrir_length = size(subject.hrir, 3);
oracleConfig.convolution_type = "full linear convolution using render_static_binaural";
oracleConfig.maximum_direction_mismatch_deg = maximumDirectionMismatchDeg;
oracleConfig.listening_gain = listeningGain;
oracleConfig.listening_gain_db = 20 * log10(listeningGain);
oracleConfig.gain_policy = ...
    "one fixed gain for all conditions; no per-condition, per-stem, or per-ear normalisation";
oracleConfig.audio_outputs = audioOutputs;
oracleConfig.stft = struct( ...
    "input", "written oracle_wide binaural signal", ...
    "window_length_samples", stftWindowLength, ...
    "window_length_ms", 1000 * stftWindowLength / expectedSampleRate, ...
    "hop_size_samples", stftHopSize, ...
    "hop_size_ms", 1000 * stftHopSize / expectedSampleRate, ...
    "overlap_samples", stftWindowLength - stftHopSize, ...
    "fft_size", stftFFTSize, ...
    "window_type", stftWindowType, ...
    "db_scale", "20*log10(abs(S)/(sum(window)/2)+eps), clipped at -100 dBFS for display");
oracleConfig.matlab_version = version;
oracleConfig.matlab_architecture = computer("arch");
oracleConfig.output_overwrite_policy = ...
    "overwriteExisting=true intentionally replaces only this fixed development-track experiment tree";
write_json(fullfile(metadataDir, "oracle_config.json"), oracleConfig);

requiredFiles = [ ...
    fullfile(audioDir, "oracle_colocated.wav"), ...
    fullfile(audioDir, "oracle_moderate.wav"), ...
    fullfile(audioDir, "oracle_wide.wav"), ...
    fullfile(metadataDir, "oracle_config.json"), ...
    fullfile(metadataDir, "input_stats.csv"), ...
    fullfile(metadataDir, "stem_sum_validation.json"), ...
    fullfile(metadataDir, "spatial_configurations.csv"), ...
    fullfile(figuresDir, "oracle_wide_spectrogram.png"), ...
    fullfile(figuresDir, "oracle_condition_levels.png")];
assert(all(isfile(requiredFiles)), "One or more required Phase 2.2 artifacts are missing.");

disp(excerpt.stats);
disp(lookupTable);
fprintf("Stereo stem-sum max abs %.12g, relative RMS %.12g\n", ...
    stereoValidation.max_abs_error, stereoValidation.relative_rms_error);
fprintf("Mono stem-sum max abs %.12g, relative RMS %.12g\n", ...
    monoValidation.max_abs_error, monoValidation.relative_rms_error);
for conditionIndex = 1:numel(conditionNames)
    fprintf("%s: raw peak %.12g, written peak %.12g, frames %d\n", ...
        conditionNames(conditionIndex), audioOutputs(conditionIndex).raw_peak, ...
        audioOutputs(conditionIndex).written_peak, audioOutputs(conditionIndex).frames);
end
fprintf("Official test used: false\n");
fprintf("PHASE2_2_ORACLE_COMPLETE\n");

function metrics = residual_metrics(reference, estimate)
residual = double(reference) - double(estimate);
metrics = struct();
metrics.max_abs_error = max(abs(residual), [], "all");
metrics.residual_rms = sqrt(mean(residual .^ 2, "all"));
metrics.reference_rms = sqrt(mean(double(reference) .^ 2, "all"));
metrics.relative_rms_error = metrics.residual_rms / (metrics.reference_rms + eps);
end

function create_wide_spectrogram(stereo, sampleRate, windowLength, hopSize, fftSize, dbFloor, outputPath)
window = hann(windowLength, "periodic");
overlapLength = windowLength - hopSize;
fig = figure("Visible", "off", "Color", "white", "Position", [100, 100, 1200, 760]);
cleanupFigure = onCleanup(@() close(fig));
layout = tiledlayout(fig, 2, 1, "TileSpacing", "compact", "Padding", "compact");
earNames = ["Left ear", "Right ear"];
for channel = 1:2
    [spectrum, frequencyHz, timeSeconds] = spectrogram( ...
        stereo(:, channel), window, overlapLength, fftSize, sampleRate);
    magnitudeDb = 20 * log10(abs(spectrum) / (sum(window) / 2) + eps);
    magnitudeDb = max(magnitudeDb, dbFloor);
    ax = nexttile(layout);
    imagesc(ax, timeSeconds, frequencyHz / 1000, magnitudeDb);
    axis(ax, "xy");
    ylim(ax, [0, 20]);
    xlabel(ax, "Time within rendered excerpt (s)");
    ylabel(ax, "Frequency (kHz)");
    title(ax, earNames(channel));
    colorbar(ax);
    clim(ax, [dbFloor, 0]);
end
title(layout, sprintf("Wide oracle spectrogram (periodic Hann %d, hop %d, NFFT %d; dBFS)", ...
    windowLength, hopSize, fftSize));
exportgraphics(fig, outputPath, "Resolution", 300);
end

function create_condition_level_figure(conditionNames, diagnostics, outputPath)
levels = [[diagnostics.raw_left_rms].', [diagnostics.raw_right_rms].', [diagnostics.raw_peak].'];
fig = figure("Visible", "off", "Color", "white", "Position", [100, 100, 980, 560]);
cleanupFigure = onCleanup(@() close(fig));
ax = axes(fig);
bar(ax, categorical(conditionNames, conditionNames), levels, "grouped");
grid(ax, "on");
xlabel(ax, "Spatial condition");
ylabel(ax, "Raw linear amplitude");
title(ax, "Oracle condition levels (engineering comparison; no perceptual claim)");
legend(ax, "Left RMS", "Right RMS", "Stereo peak", ...
    "Location", "northoutside", "Orientation", "horizontal");
exportgraphics(fig, outputPath, "Resolution", 300);
end

function sha256 = compute_sha256(filePath)
fid = fopen(filePath, "rb");
if fid < 0
    error("ELEC5305:Phase2_2:HashRead", "Cannot open file for SHA-256: %s", filePath);
end
cleanupFile = onCleanup(@() fclose(fid));
bytes = fread(fid, Inf, "*uint8");
digest = java.security.MessageDigest.getInstance("SHA-256");
digest.update(bytes);
sha256 = string(upper(reshape(dec2hex(typecast(digest.digest(), "uint8"), 2).', 1, [])));
end

function write_json(outputPath, value)
jsonText = jsonencode(value, "PrettyPrint", true);
fid = fopen(outputPath, "w", "n", "UTF-8");
if fid < 0
    error("ELEC5305:Phase2_2:WriteJSON", "Cannot write JSON file: %s", outputPath);
end
cleanupFile = onCleanup(@() fclose(fid));
fprintf(fid, "%s\n", jsonText);
end

function overwriteExisting = should_overwrite_existing()
% Intentional fixed-track rerun policy, isolated behind a function so the
% branch remains explicit and MATLAB Code Analyzer does not fold it away.
overwriteExisting = true;
end

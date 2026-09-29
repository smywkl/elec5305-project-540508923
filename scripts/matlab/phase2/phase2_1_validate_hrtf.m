%% Phase 2.1 - Static HRTF renderer validation
% Reproducible, noninteractive validation using CIPIC subject_003.

oldPath = path;
cleanupPath = onCleanup(@() path(oldPath));
scriptPath = mfilename("fullpath");
repoRoot = fileparts(fileparts(fileparts(fileparts(scriptPath))));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "hrtf"));

phaseName = "Phase 2.1 - Static HRTF Renderer Validation";
datasetURL = "https://sofacoustics.org/data/database/cipic/subject_003.sofa";
downloadDate = "2026-09-29";
sofaRelativePath = fullfile("data", "hrtf", "cipic", "subject_003.sofa");
sofaPath = fullfile(repoRoot, sofaRelativePath);
outputRoot = fullfile(repoRoot, "outputs", "phase2", "phase2_1_hrtf_validation", "subject_003");
metadataDir = fullfile(outputRoot, "metadata");
figuresDir = fullfile(outputRoot, "figures");
audioDir = fullfile(outputRoot, "audio");

targetAzimuths = [-80, -65, -30, 0, 30, 65, 80];
targetElevation = 0;
representativeAzimuths = [-80, 0, 80];
fftSize = 4096;
randomSeed = 5305;
noiseDurationSeconds = 3;
noiseRMS = 0.1;
wavPeakTarget = 0.95;
wavBitsPerSample = 24;
maximumAllowedMismatchDeg = 1;

fprintf("%s\n", phaseName);
fprintf("Repository root: %s\n", repoRoot);
if ~isfile(sofaPath)
    error("ELEC5305:Phase2_1:MissingSOFA", "Required SOFA file is missing: %s", sofaPath);
end

% This stable experiment owns this output directory, so deterministic reruns
% intentionally replace only its own generated artifacts.
if isfolder(outputRoot)
    rmdir(outputRoot, "s");
end
mkdir(metadataDir);
mkdir(figuresDir);
mkdir(audioDir);

subject = load_cipic_subject(sofaPath);
if subject.fs ~= 44100
    error("ELEC5305:Phase2_1:SampleRate", ...
        "Expected 44100 Hz for this milestone; SOFA file reports %.12g Hz.", subject.fs);
end
sofaSHA256 = compute_sha256(sofaPath);
sofaInfo = dir(sofaPath);

numDirections = numel(targetAzimuths);
matchCells = cell(numDirections, 1);
cueCells = cell(numDirections, 1);
for directionIndex = 1:numDirections
    matchCells{directionIndex} = find_hrir_direction(subject, ...
        targetAzimuths(directionIndex), targetElevation);
    match = matchCells{directionIndex};
    if match.angular_mismatch_deg > maximumAllowedMismatchDeg
        error("ELEC5305:Phase2_1:DirectionMismatch", ...
            "Direction %+g deg has %.6f deg mismatch, exceeding %.1f deg.", ...
            targetAzimuths(directionIndex), ...
            match.angular_mismatch_deg, maximumAllowedMismatchDeg);
    end
    cueCells{directionIndex} = compute_hrir_cues(match.left_hrir, ...
        match.right_hrir, subject.fs);

    % A one-sample unit impulse must reproduce the selected HRIR pair exactly.
    [impulseOutput, impulseDiagnostics] = render_static_binaural(1, ...
        match.left_hrir, match.right_hrir);
    expectedImpulse = [match.left_hrir, match.right_hrir];
    assert(isequal(impulseOutput, expectedImpulse), ...
        "Unit-impulse convolution did not reproduce the selected HRIR pair.");
    assert(impulseDiagnostics.output_length == size(subject.hrir, 3), ...
        "Unit-impulse output length is inconsistent with the HRIR length.");
end
matches = vertcat(matchCells{:});
cues = vertcat(cueCells{:});

requestedAzimuthDeg = reshape([matches.requested_azimuth_deg], [], 1);
requestedElevationDeg = reshape([matches.requested_elevation_deg], [], 1);
actualAzimuthDeg = reshape([matches.actual_azimuth_deg], [], 1);
actualElevationDeg = reshape([matches.actual_elevation_deg], [], 1);
measurementIndex = reshape([matches.measurement_index], [], 1);
angularMismatchDeg = reshape([matches.angular_mismatch_deg], [], 1);
exactMatch = reshape([matches.exact_match], [], 1);
itdSamples = reshape([cues.itd_samples], [], 1);
itdUs = reshape([cues.itd_us], [], 1);
ildDb = reshape([cues.ild_db], [], 1);
hrirLength = repmat(size(subject.hrir, 3), numDirections, 1);
sampleRateHz = repmat(subject.fs, numDirections, 1);
leftRms = reshape([cues.left_rms], [], 1);
rightRms = reshape([cues.right_rms], [], 1);
leftPeak = reshape([cues.left_peak], [], 1);
rightPeak = reshape([cues.right_peak], [], 1);

results = table(requestedAzimuthDeg, requestedElevationDeg, actualAzimuthDeg, ...
    actualElevationDeg, measurementIndex, angularMismatchDeg, exactMatch, ...
    itdSamples, itdUs, ildDb, hrirLength, sampleRateHz, leftRms, rightRms, ...
    leftPeak, rightPeak, 'VariableNames', { ...
    'requested_azimuth_deg', 'requested_elevation_deg', 'actual_azimuth_deg', ...
    'actual_elevation_deg', 'measurement_index', 'angular_mismatch_deg', ...
    'exact_match', 'itd_samples', 'itd_us', 'ild_db', 'hrir_length', ...
    'sample_rate_hz', 'left_rms', 'right_rms', 'left_peak', 'right_peak'});
writetable(results, fullfile(metadataDir, "validation_results.csv"));

% Generate deterministic broadband input with an explicitly controlled RMS.
rng(randomSeed, "twister");
noise = randn(round(noiseDurationSeconds * subject.fs), 1);
noise = noise - mean(noise);
noise = noiseRMS * noise / sqrt(mean(noise .^ 2));
representativeIndices = zeros(size(representativeAzimuths));
rawRenders = cell(size(representativeAzimuths));
rawRenderPeaks = zeros(size(representativeAzimuths));
for index = 1:numel(representativeAzimuths)
    representativeIndices(index) = find(targetAzimuths == representativeAzimuths(index), 1);
    match = matches(representativeIndices(index));
    [rawRenders{index}, renderDiagnostics] = render_static_binaural( ...
        noise, match.left_hrir, match.right_hrir);
    rawRenderPeaks(index) = renderDiagnostics.peak;
end
maximumRawPeak = max(rawRenderPeaks);
globalHeadroomFactor = min(1, wavPeakTarget / maximumRawPeak);

audioIntegrity = repmat(struct(), numel(representativeAzimuths), 1);
for index = 1:numel(representativeAzimuths)
    azimuth = representativeAzimuths(index);
    outputAudio = rawRenders{index} * globalHeadroomFactor;
    filename = sprintf("noise_az_%s.wav", azimuth_token(azimuth));
    wavPath = fullfile(audioDir, filename);
    audiowrite(wavPath, outputAudio, subject.fs, "BitsPerSample", wavBitsPerSample);
    [decodedAudio, decodedFs] = audioread(wavPath);
    info = audioinfo(wavPath);
    assert(decodedFs == subject.fs && info.SampleRate == subject.fs, "WAV sample-rate check failed.");
    assert(size(decodedAudio, 2) == 2, "WAV channel-count check failed.");
    assert(size(decodedAudio, 1) == size(outputAudio, 1), "WAV frame-count check failed.");
    assert(all(isfinite(decodedAudio), "all"), "WAV contains NaN or Inf.");
    decodedPeak = max(abs(decodedAudio), [], "all");
    assert(decodedPeak <= 1, "WAV clipping check failed.");
    audioIntegrity(index).filename = filename;
    audioIntegrity(index).azimuth_deg = azimuth;
    audioIntegrity(index).sample_rate_hz = decodedFs;
    audioIntegrity(index).channels = size(decodedAudio, 2);
    audioIntegrity(index).frames = size(decodedAudio, 1);
    audioIntegrity(index).duration_seconds = size(decodedAudio, 1) / decodedFs;
    audioIntegrity(index).peak = decodedPeak;
    audioIntegrity(index).finite = all(isfinite(decodedAudio), "all");
    audioIntegrity(index).clipping = decodedPeak >= 1;
end

create_hrir_figure(matches, representativeIndices, subject.fs, ...
    fullfile(figuresDir, "hrir_waveforms_selected.png"));
create_hrtf_figure(matches, representativeIndices, subject.fs, fftSize, ...
    fullfile(figuresDir, "hrtf_magnitude_selected.png"));
create_summary_figure(requestedAzimuthDeg, itdUs, "ITD (microseconds)", ...
    "Broadband ITD vs azimuth", fullfile(figuresDir, "itd_vs_azimuth.png"));
create_summary_figure(requestedAzimuthDeg, ildDb, "ILD (dB)", ...
    "Broadband ILD vs azimuth", fullfile(figuresDir, "ild_vs_azimuth.png"));

centreIndex = find(targetAzimuths == 0, 1);
leftIndex = find(targetAzimuths == -80, 1);
rightIndex = find(targetAzimuths == 80, 1);
sanityChecks = struct();
sanityChecks.centre_itd_near_zero = abs(itdSamples(centreIndex)) <= 2;
sanityChecks.centre_ild_relatively_small = abs(ildDb(centreIndex)) <= 3;
sanityChecks.positive_80_right_ear_earlier = itdSamples(rightIndex) > 0;
sanityChecks.positive_80_right_ear_stronger = ildDb(rightIndex) > 0;
sanityChecks.negative_80_left_ear_earlier = itdSamples(leftIndex) < 0;
sanityChecks.negative_80_left_ear_stronger = ildDb(leftIndex) < 0;
if ~all(structfun(@(value) logical(value), sanityChecks))
    error("ELEC5305:Phase2_1:PhysicalSanity", ...
        "One or more ITD/ILD physical sanity checks failed; inspect coordinate and receiver conventions.");
end

directionRecords = repmat(struct(), numDirections, 1);
for index = 1:numDirections
    directionRecords(index).requested_azimuth_deg = matches(index).requested_azimuth_deg;
    directionRecords(index).requested_elevation_deg = matches(index).requested_elevation_deg;
    directionRecords(index).measurement_index_matlab_1_based = matches(index).measurement_index;
    directionRecords(index).actual_project_azimuth_deg = matches(index).actual_azimuth_deg;
    directionRecords(index).actual_elevation_deg = matches(index).actual_elevation_deg;
    directionRecords(index).stored_sofa_azimuth_deg = matches(index).sofa_azimuth_deg;
    directionRecords(index).distance_m = matches(index).actual_distance_m;
    directionRecords(index).angular_mismatch_deg = matches(index).angular_mismatch_deg;
    directionRecords(index).exact_match = matches(index).exact_match;
end

geometrySummary = struct();
geometrySummary.dataset = "CIPIC HRTF Database";
geometrySummary.subject = "subject_003";
geometrySummary.source_url = datasetURL;
geometrySummary.download_date = downloadDate;
geometrySummary.file_size_bytes = sofaInfo.bytes;
geometrySummary.sha256 = sofaSHA256;
geometrySummary.sofa_convention = subject.sofa_convention;
geometrySummary.sofa_convention_version = subject.sofa_convention_version;
geometrySummary.data_type = subject.data_type;
geometrySummary.sample_rate_hz = subject.fs;
geometrySummary.hrir_dimensions_measurements_receivers_samples = size(subject.hrir);
geometrySummary.source_position_type = subject.source_position_type;
geometrySummary.source_position_units = subject.source_position_units;
geometrySummary.source_position_columns = ["azimuth_deg", "elevation_deg", "distance_m"];
geometrySummary.sofa_coordinate_convention = ...
    "listener-centred right-handed frame: +x forward, +y left, +z up; spherical azimuth is positive toward +y";
geometrySummary.project_coordinate_convention = ...
    "azimuth 0 deg is front; positive project azimuth is right; SOFA lookup uses mod(-project_azimuth,360)";
geometrySummary.listener_view = subject.listener_view;
geometrySummary.listener_up = subject.listener_up;
geometrySummary.receiver_order = subject.receiver_order;
geometrySummary.receiver_positions_cartesian_m = subject.receiver_positions;
geometrySummary.receiver_position_type = subject.receiver_position_type;
geometrySummary.receiver_position_units = subject.receiver_position_units;
geometrySummary.receiver_order_basis = ...
    "receiver 1 has +y and is left; receiver 2 has -y and is right";
geometrySummary.delay_samples = subject.delay;
geometrySummary.delay_interpretation = subject.delay_interpretation;
geometrySummary.selected_directions = directionRecords;
write_json(fullfile(metadataDir, "geometry_summary.json"), geometrySummary);
write_json(fullfile(outputRoot, "geometry_summary.json"), geometrySummary);
write_geometry_markdown(fullfile(outputRoot, "geometry_summary.md"), geometrySummary);

runConfig = struct();
runConfig.phase = phaseName;
runConfig.code_version = "phase2.1-static-hrtf-v1";
runConfig.dataset = "CIPIC HRTF Database";
runConfig.subject = "subject_003";
runConfig.dataset_url = datasetURL;
runConfig.dataset_download_date = downloadDate;
runConfig.sofa_path = strrep(sofaRelativePath, "\", "/");
runConfig.sofa_sha256 = sofaSHA256;
runConfig.sample_rate_hz = subject.fs;
runConfig.target_azimuths_deg = targetAzimuths;
runConfig.target_elevation_deg = targetElevation;
runConfig.maximum_allowed_angular_mismatch_deg = maximumAllowedMismatchDeg;
runConfig.fft_size = fftSize;
runConfig.itd_definition = ...
    "negative of absolute-peak lag from xcorr(hR,hL); positive means right ear earlier";
runConfig.ild_definition = "20*log10((RMS(hR)+eps)/(RMS(hL)+eps)); positive means right ear stronger";
runConfig.random_seed = randomSeed;
runConfig.test_signal = struct("type", "zero-mean white noise", ...
    "duration_seconds", noiseDurationSeconds, "rms", noiseRMS, ...
    "generator", "MATLAB rng(seed,'twister') followed by randn");
runConfig.impulse_test = "one-sample unit impulse; output must equal the selected HRIR pair exactly";
runConfig.audio_output = struct("representative_azimuths_deg", representativeAzimuths, ...
    "bits_per_sample", wavBitsPerSample, "raw_render_peaks", rawRenderPeaks, ...
    "maximum_raw_peak", maximumRawPeak, "peak_target", wavPeakTarget, ...
    "global_headroom_factor", globalHeadroomFactor, ...
    "gain_policy", "single shared non-increasing gain across every validation WAV; never per-ear or per-direction normalisation", ...
    "integrity", audioIntegrity);
runConfig.matlab_version = version;
runConfig.matlab_architecture = computer("arch");
runConfig.required_toolboxes = toolbox_versions();
runConfig.output_overwrite_policy = ...
    "deterministic rerun replaces only outputs/phase2/phase2_1_hrtf_validation/subject_003";
runConfig.sanity_checks = sanityChecks;
write_json(fullfile(metadataDir, "run_config.json"), runConfig);

expectedFiles = [ ...
    fullfile(metadataDir, "geometry_summary.json"), ...
    fullfile(metadataDir, "validation_results.csv"), ...
    fullfile(metadataDir, "run_config.json"), ...
    fullfile(figuresDir, "hrir_waveforms_selected.png"), ...
    fullfile(figuresDir, "hrtf_magnitude_selected.png"), ...
    fullfile(figuresDir, "itd_vs_azimuth.png"), ...
    fullfile(figuresDir, "ild_vs_azimuth.png"), ...
    fullfile(audioDir, "noise_az_m80.wav"), ...
    fullfile(audioDir, "noise_az_0.wav"), ...
    fullfile(audioDir, "noise_az_p80.wav")];
assert(all(isfile(expectedFiles)), "One or more required output files are missing.");
assert(height(results) == 7 && numel(unique(results.requested_azimuth_deg)) == 7, ...
    "Validation CSV must contain all seven unique requested directions.");

disp(results(:, {'requested_azimuth_deg', 'actual_azimuth_deg', ...
    'measurement_index', 'itd_samples', 'itd_us', 'ild_db'}));
fprintf("SOFA SHA-256: %s\n", sofaSHA256);
fprintf("Shared audio headroom factor: %.12g\n", globalHeadroomFactor);
fprintf("PHASE2_1_VALIDATION_COMPLETE\n");

function sha256 = compute_sha256(filePath)
fid = fopen(filePath, "rb");
if fid < 0
    error("ELEC5305:Phase2_1:HashRead", "Cannot open file for SHA-256: %s", filePath);
end
cleanupFile = onCleanup(@() fclose(fid));
bytes = fread(fid, Inf, "*uint8");
digest = java.security.MessageDigest.getInstance("SHA-256");
digest.update(bytes);
sha256 = upper(reshape(dec2hex(typecast(digest.digest(), "uint8"), 2).', 1, []));
end

function token = azimuth_token(azimuth)
if azimuth < 0
    token = sprintf("m%d", abs(round(azimuth)));
elseif azimuth > 0
    token = sprintf("p%d", round(azimuth));
else
    token = "0";
end
end

function create_hrir_figure(matches, indices, sampleRate, outputPath)
fig = figure("Visible", "off", "Color", "white", "Position", [100, 100, 1000, 780]);
cleanupFigure = onCleanup(@() close(fig));
layout = tiledlayout(fig, 3, 1, "TileSpacing", "compact", "Padding", "compact");
for plotIndex = 1:numel(indices)
    match = matches(indices(plotIndex));
    timeMs = (0:numel(match.left_hrir)-1) / sampleRate * 1000;
    ax = nexttile(layout);
    plot(ax, timeMs, match.left_hrir, "LineWidth", 1.0); hold(ax, "on");
    plot(ax, timeMs, match.right_hrir, "LineWidth", 1.0);
    grid(ax, "on");
    ylabel(ax, "Amplitude");
    title(ax, sprintf("Requested %+g deg (actual %+g deg)", ...
        match.requested_azimuth_deg, match.actual_azimuth_deg));
    legend(ax, "Left", "Right", "Location", "best");
end
xlabel(layout, "Time (ms)");
title(layout, "CIPIC subject_003 HRIR waveforms");
exportgraphics(fig, outputPath, "Resolution", 200);
end

function create_hrtf_figure(matches, indices, sampleRate, fftSize, outputPath)
fig = figure("Visible", "off", "Color", "white", "Position", [100, 100, 1000, 780]);
cleanupFigure = onCleanup(@() close(fig));
layout = tiledlayout(fig, 3, 1, "TileSpacing", "compact", "Padding", "compact");
frequencyHz = (0:fftSize/2).' * sampleRate / fftSize;
displayBins = frequencyHz >= 20 & frequencyHz <= 20000;
for plotIndex = 1:numel(indices)
    match = matches(indices(plotIndex));
    leftSpectrum = fft(match.left_hrir, fftSize);
    rightSpectrum = fft(match.right_hrir, fftSize);
    leftMagnitudeDb = 20 * log10(abs(leftSpectrum(1:fftSize/2+1)) + eps);
    rightMagnitudeDb = 20 * log10(abs(rightSpectrum(1:fftSize/2+1)) + eps);
    ax = nexttile(layout);
    semilogx(ax, frequencyHz(displayBins) / 1000, leftMagnitudeDb(displayBins), "LineWidth", 1.0);
    hold(ax, "on");
    semilogx(ax, frequencyHz(displayBins) / 1000, rightMagnitudeDb(displayBins), "LineWidth", 1.0);
    grid(ax, "on");
    xlim(ax, [0.02, 20]);
    ylabel(ax, "Magnitude (dB)");
    title(ax, sprintf("Requested %+g deg (actual %+g deg)", ...
        match.requested_azimuth_deg, match.actual_azimuth_deg));
    legend(ax, "Left", "Right", "Location", "best");
end
xlabel(layout, "Frequency (kHz)");
title(layout, sprintf("CIPIC subject_003 HRTF magnitude (NFFT = %d, common absolute reference)", fftSize));
exportgraphics(fig, outputPath, "Resolution", 200);
end

function create_summary_figure(azimuths, values, yLabelText, titleText, outputPath)
fig = figure("Visible", "off", "Color", "white", "Position", [100, 100, 850, 520]);
cleanupFigure = onCleanup(@() close(fig));
ax = axes(fig);
plot(ax, azimuths, values, "-o", "LineWidth", 1.5, "MarkerSize", 6);
hold(ax, "on");
yline(ax, 0, "--", "Zero reference", "LabelHorizontalAlignment", "left");
grid(ax, "on");
xlabel(ax, "Project azimuth (deg; positive = right)");
ylabel(ax, yLabelText);
title(ax, titleText);
exportgraphics(fig, outputPath, "Resolution", 200);
end

function versions = toolbox_versions()
installed = ver;
wanted = ["Signal Processing Toolbox", "Audio Toolbox", "DSP System Toolbox"];
versions = repmat(struct("name", "", "version", ""), numel(wanted), 1);
for wantedIndex = 1:numel(wanted)
    match = find(strcmp({installed.Name}, wanted(wantedIndex)), 1);
    if isempty(match)
        error("ELEC5305:Phase2_1:MissingToolbox", ...
            "Required toolbox is unavailable: %s", wanted(wantedIndex));
    end
    versions(wantedIndex).name = installed(match).Name;
    versions(wantedIndex).version = installed(match).Version;
end
end

function write_json(outputPath, value)
jsonText = jsonencode(value, "PrettyPrint", true);
fid = fopen(outputPath, "w", "n", "UTF-8");
if fid < 0
    error("ELEC5305:Phase2_1:WriteJSON", "Cannot write JSON file: %s", outputPath);
end
cleanupFile = onCleanup(@() fclose(fid));
fprintf(fid, "%s\n", jsonText);
end

function write_geometry_markdown(outputPath, geometry)
fid = fopen(outputPath, "w", "n", "UTF-8");
if fid < 0
    error("ELEC5305:Phase2_1:WriteMarkdown", "Cannot write Markdown file: %s", outputPath);
end
cleanupFile = onCleanup(@() fclose(fid));
fprintf(fid, "# CIPIC subject_003 geometry summary\n\n");
fprintf(fid, "- Source: `%s`\n", geometry.source_url);
fprintf(fid, "- Download date: %s\n", geometry.download_date);
fprintf(fid, "- SHA-256: `%s`\n", geometry.sha256);
fprintf(fid, "- SOFA convention: `%s` %s\n", geometry.sofa_convention, geometry.sofa_convention_version);
fprintf(fid, "- HRIR dimensions: %s (measurements x receivers x samples)\n", ...
    mat2str(geometry.hrir_dimensions_measurements_receivers_samples));
fprintf(fid, "- Sample rate: %.0f Hz\n", geometry.sample_rate_hz);
fprintf(fid, "- SOFA source positions: `%s`, units `%s`, columns azimuth/elevation/distance.\n", ...
    geometry.source_position_type, geometry.source_position_units);
fprintf(fid, "- Coordinate conversion: project azimuth is positive right; SOFA lookup uses `mod(-azimuth, 360)`.\n");
fprintf(fid, "- Receiver order: receiver 1 = left (+y), receiver 2 = right (-y).\n");
fprintf(fid, "- Delay metadata: %s samples.\n\n", mat2str(geometry.delay_samples));
fprintf(fid, "| Requested azimuth | Requested elevation | MATLAB measurement index | Actual azimuth | Actual elevation | Angular mismatch | Exact |\n");
fprintf(fid, "|---:|---:|---:|---:|---:|---:|:---:|\n");
for record = reshape(geometry.selected_directions, 1, [])
    fprintf(fid, "| %+.0f | %.0f | %d | %+.9g | %+.9g | %.9g | %s |\n", ...
        record.requested_azimuth_deg, record.requested_elevation_deg, ...
        record.measurement_index_matlab_1_based, record.actual_project_azimuth_deg, ...
        record.actual_elevation_deg, record.angular_mismatch_deg, ...
        string(record.exact_match));
end
end

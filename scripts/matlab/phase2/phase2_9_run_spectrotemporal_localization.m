%% Phase 2.9 - Spectro-temporal localization of downstream binaural error

oldPath = path;
cleanupPath = onCleanup(@() path(oldPath));
scriptPath = mfilename("fullpath");
repoRoot = fileparts(fileparts(fileparts(fileparts(scriptPath))));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "comparison"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "hrtf"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "oracle"));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "spatial"));

overallStarted = tic;
mechanismPath = fullfile(repoRoot, "config", "phase2", "mechanism_analysis_protocol.json");
staticPath = fullfile(repoRoot, "config", "phase2", "static_experiment_protocol.json");
manifestPath = fullfile(repoRoot, "config", "phase2", "final_test_manifest.json");
sofaPath = fullfile(repoRoot, "data", "hrtf", "cipic", "subject_003.sofa");
expectedMechanismHash = "3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0";
expectedStaticHash = "3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3";
expectedManifestHash = "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc";
expectedSofaHash = "a9db5f938ed1113b118dcbeb43f5fe1b27b9e191d1bbdb63fbc4803b6959b220";

mechanismHash = compute_sha256(mechanismPath);
staticHash = compute_sha256(staticPath);
manifestHash = compute_sha256(manifestPath);
sofaHash = compute_sha256(sofaPath);
if mechanismHash ~= expectedMechanismHash || staticHash ~= expectedStaticHash || ...
        manifestHash ~= expectedManifestHash || sofaHash ~= expectedSofaHash
    error("ELEC5305:Spectrotemporal:FrozenHash", ...
        "Frozen hash mismatch: mechanism=%s static=%s manifest=%s SOFA=%s.", ...
        mechanismHash, staticHash, manifestHash, sofaHash);
end
mechanism = jsondecode(fileread(mechanismPath));
protocol = jsondecode(fileread(staticPath));
manifest = jsondecode(fileread(manifestPath));
selectedTracks = manifest.selected_tracks;
if string(mechanism.protocol_version) ~= "1.0" || ...
        string(protocol.protocol_version) ~= "1.1" || ...
        numel(selectedTracks) ~= 10 || manifest.selected_track_count ~= 10
    error("ELEC5305:Spectrotemporal:FrozenConfig", "Frozen configuration mismatch.");
end

sampleRate = double(protocol.excerpt.sample_rate_hz);
excerptStartSeconds = double(protocol.excerpt.start_seconds);
excerptDurationSeconds = double(protocol.excerpt.duration_seconds);
expectedInputFrames = double(protocol.excerpt.frames);
maxMismatch = double(protocol.hrtf.maximum_direction_mismatch_deg);
stft = protocol.stft;
if sampleRate ~= 44100 || excerptStartSeconds ~= 30 || excerptDurationSeconds ~= 30 || ...
        expectedInputFrames ~= 1323000 || double(stft.window_length_samples) ~= 1024 || ...
        double(stft.hop_size_samples) ~= 256 || double(stft.fft_size) ~= 1024 || ...
        string(stft.window_type) ~= "periodic Hann"
    error("ELEC5305:Spectrotemporal:FrozenDSP", "Frozen excerpt/STFT mismatch.");
end
configs = parse_spatial_conditions(protocol);
validate_mechanism_rq5(mechanism, configs);

phase27Root = fullfile(repoRoot, "outputs", "phase2", "phase2_7_error_interaction");
phase28Root = fullfile(repoRoot, "outputs", "phase2", "phase2_8_stem_attribution");
phase27Snapshot = snapshot_tree(phase27Root);
phase28Snapshot = snapshot_tree(phase28Root);
validate_prerequisites(phase27Root, phase28Root);

subject = load_cipic_subject(sofaPath);
if subject.fs ~= sampleRate || size(subject.hrir, 3) ~= 200 || ...
        ~isequal(string(subject.receiver_order), ["left", "right"])
    error("ELEC5305:Spectrotemporal:HRTF", "Frozen HRTF invariant failed.");
end
expectedRenderedFrames = expectedInputFrames + size(subject.hrir, 3) - 1;
if expectedRenderedFrames ~= 1323199
    error("ELEC5305:Spectrotemporal:RenderedLength", "Unexpected rendered length.");
end

outputRoot = fullfile(repoRoot, "outputs", "phase2", "phase2_9_spectrotemporal");
metricsRoot = fullfile(outputRoot, "metrics");
tracksRoot = fullfile(outputRoot, "tracks");
logsRoot = fullfile(outputRoot, "logs");
mkdir_if_missing(metricsRoot); mkdir_if_missing(tracksRoot); mkdir_if_missing(logsRoot);
diary(fullfile(logsRoot, "matlab_phase2_9.log"));
cleanupDiary = onCleanup(@() diary("off")); %#ok<NASGU>

perTrackRuntime = zeros(10, 1);
cacheTrackCount = 0; cacheStemCount = 0; resumedCount = 0;
for trackIndex = 1:10
    track = selectedTracks(trackIndex);
    rank = double(track.rank);
    trackName = string(track.track_name_original);
    if rank ~= trackIndex
        error("ELEC5305:Spectrotemporal:Rank", "Manifest rank/order mismatch.");
    end
    fprintf("[%d/10] %s\n", rank, trackName);
    trackStarted = tic;
    trackDirectory = fullfile(repoRoot, string(track.dataset_relative_path));
    cacheDirectory = fullfile(repoRoot, "outputs", "phase2", "phase2_5_final", ...
        "cache", "htdemucs_ft", trackName);
    cacheCompletion = fullfile(cacheDirectory, "completion.json");
    oracle = load_musdb_gt_excerpt(trackDirectory, excerptStartSeconds, ...
        excerptDurationSeconds, sampleRate);
    estimated = load_final_cached_excerpt(cacheDirectory, cacheCompletion, trackName, ...
        excerptStartSeconds, excerptDurationSeconds, sampleRate);
    validate_excerpt_pair(oracle, estimated, expectedInputFrames, rank, trackName);
    cacheTrackCount = cacheTrackCount + 1;
    cacheStemCount = cacheStemCount + 4;

    trackOutput = fullfile(tracksRoot, trackName);
    completionPath = fullfile(trackOutput, "completion.json");
    if validate_track_completion(completionPath, trackOutput, rank, trackName, ...
            mechanismHash, staticHash, manifestHash)
        completion = jsondecode(fileread(completionPath));
        perTrackRuntime(rank) = double(completion.runtime_seconds);
        resumedCount = resumedCount + 1;
        fprintf("  SKIPPED_COMPLETE (cache revalidated)\n");
        continue;
    end
    mkdir_if_missing(trackOutput);
    cleanup_partial_track(trackOutput);
    [frequencyTable, stemTable, maskTable, transientTable, validation] = process_track( ...
        rank, trackName, oracle, estimated, subject, configs, sampleRate, ...
        expectedInputFrames, expectedRenderedFrames, maxMismatch);

    frequencyPath = fullfile(trackOutput, "frequency_profiles.csv");
    stemPath = fullfile(trackOutput, "stem_frequency_profiles.csv");
    maskPath = fullfile(trackOutput, "transient_mask.csv");
    transientPath = fullfile(trackOutput, "transient_metrics.csv");
    validationPath = fullfile(trackOutput, "validation.json");
    atomic_writetable(frequencyTable, frequencyPath);
    atomic_writetable(stemTable, stemPath);
    atomic_writetable(maskTable, maskPath);
    atomic_writetable(transientTable, transientPath);
    atomic_write_json(validationPath, validation);
    runtimeSeconds = toc(trackStarted);
    perTrackRuntime(rank) = runtimeSeconds;
    completion = struct("schema", "phase2_9_spectrotemporal_completion_v1", ...
        "status", "COMPLETE", "rank", rank, "track", trackName, ...
        "mechanism_protocol_sha256", mechanismHash, "static_protocol_sha256", staticHash, ...
        "manifest_sha256", manifestHash, "cache_completion_sha256", compute_sha256(cacheCompletion), ...
        "frequency_rows", height(frequencyTable), "stem_frequency_rows", height(stemTable), ...
        "transient_mask_rows", height(maskTable), "transient_rows", height(transientTable), ...
        "runtime_seconds", runtimeSeconds, "frequency_sha256", compute_sha256(frequencyPath), ...
        "stem_frequency_sha256", compute_sha256(stemPath), "transient_mask_sha256", compute_sha256(maskPath), ...
        "transient_sha256", compute_sha256(transientPath), "validation_sha256", compute_sha256(validationPath));
    atomic_write_json(completionPath, completion); % Must be last.
    fprintf("  COMPLETE runtime %.3f s\n", runtimeSeconds);
end

perSongFrequency = collect_track_tables(selectedTracks, tracksRoot, "frequency_profiles.csv");
perSongStem = collect_track_tables(selectedTracks, tracksRoot, "stem_frequency_profiles.csv");
transient = collect_track_tables(selectedTracks, tracksRoot, "transient_metrics.csv");
validate_per_song_aggregates(perSongFrequency, perSongStem, transient);
pooledFrequency = build_pooled_frequency(perSongFrequency);
frequencyBands = build_frequency_bands(pooledFrequency, false);
pooledStem = build_pooled_stem_frequency(perSongStem);
stemBands = build_frequency_bands(pooledStem, true);
rank4Absolute = perSongStem(perSongStem.rank == 4 & perSongStem.stem == "vocals", ...
    ["condition", "frequency_bin", "frequency_hz", "rendered_error_power"]);
contrasts = build_transient_contrasts(transient);

atomic_writetable(pooledFrequency, fullfile(metricsRoot, "frequency_error_profiles.csv"));
atomic_writetable(perSongFrequency, fullfile(metricsRoot, "frequency_error_profiles_per_song.csv"));
atomic_writetable(frequencyBands, fullfile(metricsRoot, "frequency_band_summary.csv"));
atomic_writetable(pooledStem, fullfile(metricsRoot, "stem_frequency_error_profiles.csv"));
atomic_writetable(perSongStem, fullfile(metricsRoot, "stem_frequency_error_profiles_per_song.csv"));
atomic_writetable(stemBands, fullfile(metricsRoot, "stem_frequency_band_summary.csv"));
atomic_writetable(rank4Absolute, fullfile(metricsRoot, "rank4_vocals_absolute_error_spectrum.csv"));
atomic_writetable(transient, fullfile(metricsRoot, "transient_vs_nontransient_error.csv"));
atomic_writetable(contrasts, fullfile(metricsRoot, "transient_error_contrasts.csv"));

if ~isequal(phase27Snapshot, snapshot_tree(phase27Root)) || ...
        ~isequal(phase28Snapshot, snapshot_tree(phase28Root))
    error("ELEC5305:Spectrotemporal:PrerequisiteMutation", "Phase 2.7/2.8 outputs changed.");
end

summary = struct("schema", "phase2_9_matlab_spectrotemporal_summary_v1", ...
    "status", "MATLAB_COMPLETE", "mechanism_protocol_sha256", mechanismHash, ...
    "static_protocol_sha256", staticHash, "manifest_sha256", manifestHash, ...
    "sofa_sha256", sofaHash, "cache_valid_tracks", cacheTrackCount, ...
    "cache_valid_stems", cacheStemCount, "resumed_complete_tracks", resumedCount, ...
    "direct_decomposition_pass_count", 30, ...
    "direct_decomposition_max_relerr", max_validation_value(selectedTracks, tracksRoot, "direct_decomposition_max_relerr"), ...
    "stft_window", "periodic Hann", "stft_window_length_samples", 1024, ...
    "stft_hop_samples", 256, "stft_overlap_samples", 768, "stft_fft_size", 1024, ...
    "frequency_bin_count", 513, "frequency_min_hz", 0, "frequency_max_hz", 22050, ...
    "pooled_frequency_rows", height(pooledFrequency), "per_song_frequency_rows", height(perSongFrequency), ...
    "frequency_band_rows", height(frequencyBands), "pooled_stem_frequency_rows", height(pooledStem), ...
    "per_song_stem_frequency_rows", height(perSongStem), "stem_band_rows", height(stemBands), ...
    "rank4_vocals_absolute_rows", height(rank4Absolute), "transient_rows", height(transient), ...
    "transient_contrast_rows", height(contrasts), "per_track_runtime_seconds", perTrackRuntime, ...
    "sum_per_track_runtime_seconds", sum(perTrackRuntime), ...
    "this_invocation_wall_seconds", toc(overallStarted), "matlab_version", version, ...
    "matlab_architecture", computer("arch"), "phase_2_10_results_computed", false);
toolboxInfo = ver; summary.available_toolboxes = string({toolboxInfo.Name});
atomic_write_json(fullfile(metricsRoot, "matlab_spectrotemporal_summary.json"), summary);
fprintf("PHASE2_9_MATLAB_COMPLETE total=%d stem=%d transient=%d\n", ...
    height(pooledFrequency), height(pooledStem), height(transient));

function [frequencyTable, stemTable, maskTable, transientTable, validation] = process_track(rank, trackName, oracle, estimated, subject, configs, sampleRate, expectedInputFrames, expectedRenderedFrames, maxMismatch)
stemNames = ["bass", "vocals", "drums", "other"];
errors = struct(); gtMixture = zeros(expectedInputFrames, 1); referenceStatus = repmat("ACTIVE", 4, 1);
for stemIndex = 1:4
    field = char(stemNames(stemIndex));
    gt = double(oracle.mono.(field)); estimate = double(estimated.mono.(field));
    errors.(field) = estimate - gt; gtMixture = gtMixture + gt;
    if sum(gt.^2) == 0, referenceStatus(stemIndex) = "INACTIVE_REFERENCE"; end
end
if rank == 4
    if trackName ~= "Skelpolu - Resurrection" || referenceStatus(2) ~= "INACTIVE_REFERENCE" || sum(estimated.mono.vocals.^2) <= 0
        error("ELEC5305:Spectrotemporal:Rank4", "Rank-4 vocals invariant failed.");
    end
elseif any(referenceStatus ~= "ACTIVE")
    error("ELEC5305:Spectrotemporal:InactiveReference", "Unexpected inactive reference.");
end
mask = compute_transient_mask(gtMixture, expectedRenderedFrames, sampleRate);
if mask.padding_samples ~= 199 || numel(mask.frequency_hz) ~= 513
    error("ELEC5305:Spectrotemporal:TransientAlignment", "Transient alignment invariant failed.");
end
maskTable = table(repmat(rank, numel(mask.frame_index), 1), repmat(trackName, numel(mask.frame_index), 1), ...
    mask.frame_index, mask.time_seconds, mask.spectral_flux, mask.frame_class, ...
    'VariableNames', ["rank", "track", "frame_index", "time_seconds", "spectral_flux", "frame_class"]);

frequencyCells = cell(3, 1); stemCells = cell(12, 1); transientCells = cell(6, 1);
conditionValidation = cell(3, 1); stemCellIndex = 0; transientCellIndex = 0;
for conditionIndex = 1:3
    config = configs(conditionIndex);
    errorResult = compute_rendered_error_components(errors, subject, config.condition, ...
        config.azimuths_deg, config.elevation_deg, maxMismatch);
    [oracleRaw, oracleLookups, oracleDiagnostics, oracleComponents] = render_stem_mix( ...
        oracle.mono, subject, config.condition, config.azimuths_deg, config.elevation_deg, maxMismatch);
    [estimatedRaw, estimatedLookups, estimatedDiagnostics, estimatedComponents] = render_stem_mix( ...
        estimated.mono, subject, config.condition, config.azimuths_deg, config.elevation_deg, maxMismatch);
    validate_matching_renders(errorResult, oracleRaw, estimatedRaw, oracleLookups, estimatedLookups, ...
        oracleDiagnostics, estimatedDiagnostics, expectedRenderedFrames);
    directResidual = estimatedRaw - oracleRaw;
    directEnergy = sum(directResidual.^2, "all");
    directRelerr = sqrt(sum((directResidual-errorResult.decomposed_residual).^2, "all") / directEnergy);
    if directEnergy <= 0 || directRelerr > 1e-10
        error("ELEC5305:Spectrotemporal:ResidualIdentity", "Residual decomposition failed.");
    end
    totalProfile = compute_frequency_error_profile(oracleRaw, directResidual, sampleRate);
    if any(totalProfile.metric_status ~= "DEFINED") || any(~isfinite(totalProfile.relative_error_db))
        error("ELEC5305:Spectrotemporal:TotalFrequencyEdge", "Unexpected total-profile zero edge case.");
    end
    frequencyCells{conditionIndex} = profile_table(rank, trackName, config.condition, totalProfile);
    if size(totalProfile.reference_stft, 2) ~= numel(mask.frame_index)
        error("ELEC5305:Spectrotemporal:MaskGrid", "Transient mask/STFT frame grids differ.");
    end
    classes = ["HIGH_TRANSIENT", "NON_HIGH_TRANSIENT"];
    for classIndex = 1:2
        transientCellIndex = transientCellIndex + 1;
        selected = mask.frame_class == classes(classIndex);
        residualPower = sum(abs(totalProfile.residual_stft(:, selected, :)).^2, "all");
        oraclePower = sum(abs(totalProfile.reference_stft(:, selected, :)).^2, "all");
        if residualPower <= 0 || oraclePower <= 0
            error("ELEC5305:Spectrotemporal:TransientPower", "Nonpositive transient-class power.");
        end
        transientCells{transientCellIndex} = table(rank, trackName, config.condition, classes(classIndex), ...
            sum(selected), residualPower, oraclePower, 10*log10(residualPower/oraclePower), ...
            'VariableNames', ["rank", "track", "condition", "frame_class", "selected_frame_count", ...
            "residual_power", "oracle_power", "relative_error_db"]);
    end
    stemConsistencyMax = 0;
    for stemIndex = 1:4
        stemCellIndex = stemCellIndex + 1;
        field = char(stemNames(stemIndex));
        renderedError = errorResult.rendered_components.(field);
        componentDifference = estimatedComponents.(field) - oracleComponents.(field);
        scale = max(sum(renderedError.^2, "all"), realmin);
        stemConsistency = sqrt(sum((componentDifference-renderedError).^2, "all") / scale);
        stemConsistencyMax = max(stemConsistencyMax, stemConsistency);
        if stemConsistency > 1e-10
            error("ELEC5305:Spectrotemporal:StemRenderIdentity", "Stem render identity failed.");
        end
        stemProfile = compute_frequency_error_profile(oracleComponents.(field), renderedError, sampleRate);
        stemCells{stemCellIndex} = stem_profile_table(rank, trackName, config.condition, ...
            stemNames(stemIndex), referenceStatus(stemIndex), stemProfile);
    end
    conditionValidation{conditionIndex} = struct("condition", config.condition, ...
        "direct_decomposition_relerr", directRelerr, "stem_render_identity_max_relerr", stemConsistencyMax, ...
        "input_frames", expectedInputFrames, "rendered_frames", size(oracleRaw, 1), ...
        "stft_frames", size(totalProfile.reference_stft, 2), "frequency_bins", numel(totalProfile.frequency_hz), ...
        "frequency_min_hz", totalProfile.frequency_hz(1), "frequency_max_hz", totalProfile.frequency_hz(end), ...
        "oracle_peak", max(abs(oracleRaw), [], "all"), "estimated_peak", max(abs(estimatedRaw), [], "all"), ...
        "all_arrays_finite", true, "transient_mask_sha256_not_applicable", "condition-independent in-memory mask");
end
frequencyTable = vertcat(frequencyCells{:}); stemTable = vertcat(stemCells{:}); transientTable = vertcat(transientCells{:});
conditionValidation = vertcat(conditionValidation{:});
if height(frequencyTable) ~= 1539 || height(stemTable) ~= 6156 || height(transientTable) ~= 6
    error("ELEC5305:Spectrotemporal:TrackRows", "Per-track row count gate failed.");
end
validation = struct("schema", "phase2_9_spectrotemporal_validation_v1", "status", "PASS", ...
    "rank", rank, "track", trackName, "conditions", conditionValidation, ...
    "direct_decomposition_max_relerr", max([conditionValidation.direct_decomposition_relerr]), ...
    "transient_valid_frames", mask.valid_frame_count, "transient_selected_frames", mask.selected_frame_count, ...
    "transient_expected_selected_frames", ceil(0.20*mask.valid_frame_count), ...
    "transient_mask_condition_invariant", true, "transient_padding_samples", mask.padding_samples, ...
    "rank4_vocals_inactive", rank == 4, "phase_2_10_results_computed", false);
end

function value = profile_table(rank, trackName, condition, profile)
n = numel(profile.frequency_hz);
value = table(repmat(rank,n,1), repmat(trackName,n,1), repmat(condition,n,1), (0:n-1).', ...
    profile.frequency_hz, profile.residual_power, profile.oracle_power, profile.relative_error_db, profile.metric_status, ...
    'VariableNames', ["rank","track","condition","frequency_bin","frequency_hz","residual_power", ...
    "oracle_power","relative_error_db","metric_status"]);
end

function value = stem_profile_table(rank, trackName, condition, stem, referenceStatus, profile)
n = numel(profile.frequency_hz); relative = profile.relative_error_db; status = profile.metric_status;
if referenceStatus == "INACTIVE_REFERENCE"
    relative(:) = NaN; status(:) = "INACTIVE_REFERENCE";
elseif any(status ~= "DEFINED") || any(~isfinite(relative))
    error("ELEC5305:Spectrotemporal:StemFrequencyEdge", "Unexpected active-stem zero edge case.");
end
value = table(repmat(rank,n,1), repmat(trackName,n,1), repmat(condition,n,1), repmat(stem,n,1), ...
    repmat(referenceStatus,n,1), (0:n-1).', profile.frequency_hz, profile.residual_power, profile.oracle_power, ...
    relative, status, 'VariableNames', ["rank","track","condition","stem","reference_status", ...
    "frequency_bin","frequency_hz","rendered_error_power","rendered_gt_power","relative_error_db","metric_status"]);
end

function pooled = build_pooled_frequency(perSong)
conditions = ["colocated","moderate","wide"]; rows = cell(3,1);
for c = 1:3
    selected = perSong(perSong.condition == conditions(c), :);
    selected = sortrows(selected, ["frequency_bin","rank"]);
    err = sum(reshape(selected.residual_power,10,513),1).';
    ref = sum(reshape(selected.oracle_power,10,513),1).';
    if any(err <= 0) || any(ref <= 0), error("ELEC5305:Spectrotemporal:PooledTotalPower", "Nonpositive pooled total power."); end
    q = 10*log10(err./ref); n=(0:512).'; f=selected.frequency_hz(1:10:end);
    rows{c}=table(repmat(conditions(c),513,1),n,f,err,ref,q,zeros(513,1), ...
        'VariableNames', ["condition","frequency_bin","frequency_hz","residual_power","oracle_power","relative_error_db","delta_vs_colocated_db"]);
end
pooled=vertcat(rows{:}); base=rows{1}.relative_error_db;
pooled.delta_vs_colocated_db(pooled.condition=="colocated")=0;
pooled.delta_vs_colocated_db(pooled.condition=="moderate")=rows{2}.relative_error_db-base;
pooled.delta_vs_colocated_db(pooled.condition=="wide")=rows{3}.relative_error_db-base;
end

function pooled = build_pooled_stem_frequency(perSong)
conditions=["colocated","moderate","wide"]; stems=["bass","vocals","drums","other"]; rows=cell(12,1); k=0;
for c=1:3
    for s=1:4
        k=k+1; selected=perSong(perSong.condition==conditions(c) & perSong.stem==stems(s) & perSong.reference_status=="ACTIVE",:);
        activeCount=numel(unique(selected.rank)); expected=10-(stems(s)=="vocals");
        if activeCount~=expected, error("ELEC5305:Spectrotemporal:ActiveCount", "Stem active-song count mismatch."); end
        selected=sortrows(selected,["frequency_bin","rank"]);
        err=sum(reshape(selected.rendered_error_power,activeCount,513),1).';
        ref=sum(reshape(selected.rendered_gt_power,activeCount,513),1).';
        if any(ref==0), error("ELEC5305:Spectrotemporal:PooledStemZeroReference", "Pooled active stem has zero-reference bin."); end
        if any(err==0), error("ELEC5305:Spectrotemporal:PooledStemZeroResidual", "Pooled active stem has exact-zero residual bin."); end
        q=10*log10(err./ref); f=selected.frequency_hz(1:activeCount:end);
        rows{k}=table(repmat(conditions(c),513,1),repmat(stems(s),513,1),repmat(activeCount,513,1), ...
            (0:512).',f,err,ref,q,repmat("DEFINED",513,1), 'VariableNames', ["condition","stem","active_song_count", ...
            "frequency_bin","frequency_hz","rendered_error_power","rendered_gt_power","relative_error_db","metric_status"]);
    end
end
pooled=vertcat(rows{:});
end

function output = build_frequency_bands(profile, isStem)
[bandIndex, bandNames]=assign_predefined_frequency_bands(profile.frequency_hz(1:513));
lows=[0,500,2000,8000]; highs=[500,2000,8000,20000];
conditions=["colocated","moderate","wide"];
if isStem, stems=["bass","vocals","drums","other"]; else, stems=""; end
rows=cell(3*numel(stems)*4,1); k=0;
for c=1:3
 for s=1:numel(stems)
  if isStem, selected=profile(profile.condition==conditions(c)&profile.stem==stems(s),:); else, selected=profile(profile.condition==conditions(c),:); end
  selected=sortrows(selected,"frequency_bin");
  for b=1:4
   k=k+1; mask=bandIndex==b;
   if isStem, err=sum(selected.rendered_error_power(mask)); ref=sum(selected.rendered_gt_power(mask)); count=selected.active_song_count(1);
   else, err=sum(selected.residual_power(mask)); ref=sum(selected.oracle_power(mask)); count=[]; end
   q=10*log10(err/ref);
   if isStem
    rows{k}=table(conditions(c),stems(s),count,bandNames(b),lows(b),highs(b),err,ref,q,0, ...
     'VariableNames',["condition","stem","active_song_count","band_name","low_hz","high_hz","residual_power","oracle_power","relative_error_db","delta_vs_colocated_db"]);
   else
    rows{k}=table(conditions(c),bandNames(b),lows(b),highs(b),err,ref,q,0, ...
     'VariableNames',["condition","band_name","low_hz","high_hz","residual_power","oracle_power","relative_error_db","delta_vs_colocated_db"]);
   end
  end
 end
end
output=vertcat(rows{:});
for s=1:numel(stems)
 for b=1:4
  if isStem, key=output.stem==stems(s)&output.band_name==bandNames(b); else, key=output.band_name==bandNames(b); end
  base=output.relative_error_db(key&output.condition=="colocated");
  output.delta_vs_colocated_db(key&output.condition=="moderate")=output.relative_error_db(key&output.condition=="moderate")-base;
  output.delta_vs_colocated_db(key&output.condition=="wide")=output.relative_error_db(key&output.condition=="wide")-base;
 end
end
end

function contrasts=build_transient_contrasts(transient)
rows=cell(30,1); k=0; conditions=["colocated","moderate","wide"];
for rank=1:10
 for c=1:3
  k=k+1; selected=transient(transient.rank==rank&transient.condition==conditions(c),:);
  high=selected.relative_error_db(selected.frame_class=="HIGH_TRANSIENT"); non=selected.relative_error_db(selected.frame_class=="NON_HIGH_TRANSIENT");
  rows{k}=table(rank,selected.track(1),conditions(c),high,non,high-non, ...
   'VariableNames',["rank","track","condition","high_transient_db","non_high_transient_db","transient_minus_nontransient_db"]);
 end
end
contrasts=vertcat(rows{:});
end

function validate_per_song_aggregates(frequency, stem, transient)
if height(frequency)~=15390 || height(stem)~=61560 || height(transient)~=60 || ...
        height(unique(frequency(:,["rank","condition","frequency_bin"]),'rows'))~=15390
    error("ELEC5305:Spectrotemporal:AggregateRows", "Per-song aggregate row/key gate failed.");
end
inactive=stem(stem.metric_status=="INACTIVE_REFERENCE",:);
if height(inactive)~=3*513 || any(inactive.rank~=4) || any(inactive.stem~="vocals") || any(~isnan(inactive.relative_error_db))
    error("ELEC5305:Spectrotemporal:Rank4Aggregate", "Rank-4 vocals status gate failed.");
end
if any(frequency.metric_status~="DEFINED") || any(~isfinite(frequency.relative_error_db)) || ...
        any(~isfinite(transient.relative_error_db)) || any(transient.oracle_power<=0)
    error("ELEC5305:Spectrotemporal:FiniteAggregate", "Official total/transient finite gate failed.");
end
end

function configs=parse_spatial_conditions(protocol)
names=["colocated","moderate","wide"]; az=[0,0,0,0;-30,-10,10,30;-80,-30,30,80];
configs=repmat(struct("condition","","azimuths_deg",zeros(1,4),"elevation_deg",0),3,1);
for i=1:3
 c=protocol.spatial_conditions(i); order=string(c.source_order(:)).'; actual=double(c.azimuths_deg(:)).';
 if string(c.condition)~=names(i)||~isequal(actual,az(i,:))||~isequal(order,["bass","vocals","drums","other"]), error("ELEC5305:Spectrotemporal:Spatial", "Frozen spatial condition mismatch."); end
 configs(i)=struct("condition",names(i),"azimuths_deg",actual,"elevation_deg",double(protocol.hrtf.elevation_deg));
end
end

function validate_mechanism_rq5(mechanism,configs)
q=mechanism.rq5_frequency_localization; t=mechanism.rq5_transient_localization;
if double(q.stft.window_length_samples)~=1024||double(q.stft.hop_size_samples)~=256||double(q.stft.overlap_samples)~=768||double(q.stft.fft_size)~=1024||double(q.stft.sample_rate_hz)~=44100||double(t.high_transient_fraction)~=0.2||numel(configs)~=3
 error("ELEC5305:Spectrotemporal:Mechanism", "Mechanism RQ5 configuration mismatch.");
end
end

function validate_prerequisites(p27,p28)
s27=jsondecode(fileread(fullfile(p27,"metrics","matlab_error_interaction_summary.json")));
s28=jsondecode(fileread(fullfile(p28,"metrics","matlab_stem_attribution_summary.json")));
if string(s27.status)~="MATLAB_COMPLETE"||s27.song_condition_rows<30||s27.component_rows<120||s27.pairwise_rows<180|| ...
 string(s28.status)~="MATLAB_COMPLETE"||s28.independent_rows<120||s28.coalition_rows<480||s28.shapley_rows<120
 error("ELEC5305:Spectrotemporal:Prerequisite", "Phase 2.7/2.8 prerequisite gate failed.");
end
end

function validate_excerpt_pair(o,e,n,rank,track)
if o.sample_rate_hz~=e.sample_rate_hz||o.frame_count~=n||e.frame_count~=n||o.start_frame_matlab_1_based~=e.start_frame_matlab_1_based||o.end_frame_matlab_1_based_inclusive~=e.end_frame_matlab_1_based_inclusive
 error("ELEC5305:Spectrotemporal:Alignment", "GT/estimate mismatch rank %d %s.",rank,track); end
end

function validate_matching_renders(result,o,e,ol,el,od,ed,expected)
if ~isa(o,"double")||~isa(e,"double")||~isequal(size(o),size(e),size(result.decomposed_residual))||size(o,1)~=expected||size(o,2)~=2||any(~isfinite(o),"all")||any(~isfinite(e),"all")||od.actual_output_frames~=ed.actual_output_frames
 error("ELEC5305:Spectrotemporal:Renderer", "Renderer integrity mismatch."); end
fields=["stem","requested_azimuth_deg","requested_elevation_deg","matched_azimuth_deg","matched_elevation_deg","measurement_index","angular_mismatch_deg"];
for r=1:4, for f=fields, name=char(f); if ~isequal(result.lookups(r).(name),ol(r).(name),el(r).(name)), error("ELEC5305:Spectrotemporal:Lookup", "HRTF lookup mismatch."); end, end, end
end

function valid=validate_track_completion(pathValue,root,rank,track,mh,sh,fh)
valid=false; try
 if ~isfile(pathValue), return; end; c=jsondecode(fileread(pathValue));
 files=["frequency_profiles.csv","stem_frequency_profiles.csv","transient_mask.csv","transient_metrics.csv","validation.json"];
 if string(c.status)~="COMPLETE"||c.rank~=rank||string(c.track)~=track||string(c.mechanism_protocol_sha256)~=mh||string(c.static_protocol_sha256)~=sh||string(c.manifest_sha256)~=fh||c.frequency_rows~=1539||c.stem_frequency_rows~=6156||c.transient_rows~=6||~all(isfile(fullfile(root,files))), return; end
 hashes=[string(c.frequency_sha256),string(c.stem_frequency_sha256),string(c.transient_mask_sha256),string(c.transient_sha256),string(c.validation_sha256)];
 for i=1:5, if compute_sha256(fullfile(root,files(i)))~=hashes(i), return; end, end
 valid=true;
catch, valid=false; end
end

function cleanup_partial_track(root)
files=["frequency_profiles.csv","stem_frequency_profiles.csv","transient_mask.csv","transient_metrics.csv","validation.json","completion.json"];
for f=files, p=fullfile(root,f); if isfile(p), delete(p); end, end
end

function output=collect_track_tables(tracks,root,fileName)
parts=cell(10,1); for i=1:10, p=fullfile(root,string(tracks(i).track_name_original),fileName); if ~isfile(p), error("ELEC5305:Spectrotemporal:MissingTrack", "Missing %s.",p); end; parts{i}=readtable(p,"TextType","string"); end; output=vertcat(parts{:});
end

function value=max_validation_value(tracks,root,field)
values=zeros(10,1); for i=1:10, v=jsondecode(fileread(fullfile(root,string(tracks(i).track_name_original),"validation.json"))); values(i)=double(v.(field)); end; value=max(values);
end

function snapshot=snapshot_tree(root)
items=dir(fullfile(root,"**","*")); items=items(~[items.isdir]); names=strings(numel(items),1); hashes=strings(numel(items),1);
for i=1:numel(items), names(i)=string(fullfile(items(i).folder,items(i).name)); hashes(i)=compute_sha256(names(i)); end
[names,order]=sort(names); hashes=hashes(order); snapshot=table(names,hashes);
end

function atomic_writetable(value,pathValue)
mkdir_if_missing(fileparts(pathValue)); temporary=pathValue+".tmp.csv"; writetable(value,temporary); movefile(temporary,pathValue,"f");
end
function atomic_write_json(pathValue,value)
mkdir_if_missing(fileparts(pathValue)); temporary=pathValue+".tmp"; fid=fopen(temporary,"w"); if fid<0,error("ELEC5305:Spectrotemporal:Write","Cannot write JSON.");end; cleanup=onCleanup(@() fclose(fid)); fprintf(fid,"%s\n",jsonencode(value,PrettyPrint=true)); clear cleanup; movefile(temporary,pathValue,"f");
end
function hash=compute_sha256(pathValue)
fid=fopen(pathValue,"rb"); if fid<0,error("ELEC5305:Spectrotemporal:HashRead","Cannot open %s.",pathValue);end
cleanup=onCleanup(@() fclose(fid)); digest=java.security.MessageDigest.getInstance("SHA-256");
while true, bytes=fread(fid,1024*1024,"*uint8"); if isempty(bytes),break;end; digest.update(bytes); end
hash=string(lower(reshape(dec2hex(typecast(digest.digest(),"uint8"),2).',1,[])));
end
function mkdir_if_missing(pathValue)
if ~isfolder(pathValue),[ok,message]=mkdir(pathValue);if ~ok,error("ELEC5305:Spectrotemporal:Mkdir","%s",message);end,end
end

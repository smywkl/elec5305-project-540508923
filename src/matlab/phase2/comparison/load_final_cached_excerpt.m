function estimated = load_final_cached_excerpt(cacheDirectory, completionPath, trackName, startSeconds, durationSeconds, expectedSampleRate)
%LOAD_FINAL_CACHED_EXCERPT Validate final cache provenance and load one excerpt.

arguments
    cacheDirectory (1, 1) string
    completionPath (1, 1) string
    trackName (1, 1) string
    startSeconds (1, 1) double {mustBeFinite, mustBeNonnegative}
    durationSeconds (1, 1) double {mustBeFinite, mustBePositive}
    expectedSampleRate (1, 1) double {mustBeFinite, mustBePositive}
end

provenancePath = fullfile(cacheDirectory, "provenance.json");
if ~isfolder(cacheDirectory) || ~isfile(completionPath) || ~isfile(provenancePath)
    error("ELEC5305:FinalCache:Missing", "Final cache files are missing for %s.", trackName);
end
completion = jsondecode(fileread(completionPath));
provenance = jsondecode(fileread(provenancePath));
if string(completion.status) ~= "COMPLETE" || string(completion.track) ~= trackName || ...
        string(completion.protocol_sha256) ~= "54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0" || ...
        string(completion.manifest_sha256) ~= "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc" || ...
        string(completion.model_configuration) ~= "G_pretrained_HTDemucs_FT" || ...
        string(completion.model_repository) ~= "adefossez/HTDemucs-ft" || ...
        string(completion.model_revision) ~= "d74ac89c3a1e874fc78f152555cf4d8533f06cd4" || ...
        string(completion.configuration_fingerprint) ~= "038a7a3bd24dad340ccbab26565f463f7f04173848b931e7c1a5610726c621b2" || ...
        completion.sample_rate ~= expectedSampleRate || completion.channels ~= 2 || ...
        ~logical(completion.all_outputs_finite) || ~logical(completion.source_identity_verified)
    error("ELEC5305:FinalCache:Completion", "Completion identity/integrity mismatch for %s.", trackName);
end
if string(provenance.track) ~= trackName || ...
        string(provenance.manifest_sha256) ~= "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc" || ...
        string(provenance.model.repository) ~= "adefossez/HTDemucs-ft" || ...
        string(provenance.model.revision) ~= string(completion.model_revision) || ...
        string(provenance.model.configuration_fingerprint) ~= string(completion.configuration_fingerprint) || ...
        logical(provenance.model.custom_checkpoint_used) || ~logical(provenance.model.official_pretrained)
    error("ELEC5305:FinalCache:Provenance", "Model provenance mismatch for %s.", trackName);
end

startFrame = round(startSeconds * expectedSampleRate) + 1;
frameCount = round(durationSeconds * expectedSampleRate);
endFrame = startFrame + frameCount - 1;
if startSeconds * expectedSampleRate ~= startFrame - 1 || ...
        durationSeconds * expectedSampleRate ~= frameCount || endFrame > completion.mixture_frame_count
    error("ELEC5305:FinalCache:Excerpt", "Frozen excerpt is unavailable for %s.", trackName);
end

stemNames = ["vocals", "drums", "bass", "other"];
stereo = struct();
mono = struct();
sourcePaths = struct();
stemColumn = strings(4, 1);
sourcePathColumn = strings(4, 1);
stereoRmsLeft = zeros(4, 1);
stereoRmsRight = zeros(4, 1);
stereoPeak = zeros(4, 1);
monoRms = zeros(4, 1);
monoPeak = zeros(4, 1);

for stemIndex = 1:4
    stem = stemNames(stemIndex);
    fieldName = char(stem);
    pathValue = fullfile(cacheDirectory, stem + ".wav");
    marker = completion.stems.(fieldName);
    if ~isfile(pathValue) || ~strcmpi(compute_sha256(pathValue), string(marker.sha256))
        error("ELEC5305:FinalCache:Hash", "Cached %s hash mismatch for %s.", stem, trackName);
    end
    info = audioinfo(pathValue);
    if info.SampleRate ~= expectedSampleRate || info.NumChannels ~= 2 || ...
            info.TotalSamples ~= completion.mixture_frame_count || info.BitsPerSample ~= 32 || ...
            marker.frames ~= completion.mixture_frame_count || string(marker.subtype) ~= "FLOAT"
        error("ELEC5305:FinalCache:AudioProperties", "Cached %s metadata mismatch for %s.", stem, trackName);
    end
    [audio, sampleRate] = audioread(pathValue, [startFrame, endFrame], "double");
    if sampleRate ~= expectedSampleRate || ~isequal(size(audio), [frameCount, 2]) || ...
            any(~isfinite(audio), "all")
        error("ELEC5305:FinalCache:ExcerptIntegrity", "Cached %s excerpt invalid for %s.", stem, trackName);
    end
    stereo.(fieldName) = audio;
    mono.(fieldName) = downmix_stereo_to_mono(audio);
    sourcePaths.(fieldName) = pathValue;
    stemColumn(stemIndex) = stem;
    sourcePathColumn(stemIndex) = pathValue;
    stereoRmsLeft(stemIndex) = sqrt(mean(audio(:, 1) .^ 2));
    stereoRmsRight(stemIndex) = sqrt(mean(audio(:, 2) .^ 2));
    stereoPeak(stemIndex) = max(abs(audio), [], "all");
    monoRms(stemIndex) = sqrt(mean(mono.(fieldName) .^ 2));
    monoPeak(stemIndex) = max(abs(mono.(fieldName)));
end

estimated = struct();
estimated.stereo = stereo;
estimated.mono = mono;
estimated.source_paths = sourcePaths;
estimated.sample_rate_hz = expectedSampleRate;
estimated.start_frame_matlab_1_based = startFrame;
estimated.end_frame_matlab_1_based_inclusive = endFrame;
estimated.frame_count = frameCount;
estimated.full_track_frames = completion.mixture_frame_count;
estimated.completion = completion;
estimated.provenance = provenance;
estimated.stats = table(stemColumn, sourcePathColumn, stereoRmsLeft, ...
    stereoRmsRight, stereoPeak, monoRms, monoPeak, ...
    repmat(frameCount, 4, 1), repmat(expectedSampleRate, 4, 1), ...
    'VariableNames', {'stem', 'source_path', 'stereo_rms_L', 'stereo_rms_R', ...
    'stereo_peak', 'mono_rms', 'mono_peak', 'frames', 'sample_rate'});
end

function sha256 = compute_sha256(filePath)
fid = fopen(filePath, "rb");
if fid < 0
    error("ELEC5305:FinalCache:HashRead", "Cannot open file: %s", filePath);
end
cleanupFile = onCleanup(@() fclose(fid));
digest = java.security.MessageDigest.getInstance("SHA-256");
while true
    bytes = fread(fid, 1024 * 1024, "*uint8");
    if isempty(bytes)
        break;
    end
    digest.update(bytes);
end
sha256 = string(lower(reshape(dec2hex(typecast(digest.digest(), "uint8"), 2).', 1, [])));
end

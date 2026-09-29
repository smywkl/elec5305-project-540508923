function estimated = load_estimated_excerpt(estimatedDirectory, phase1ResultPath, phase1MetadataPath, mixturePath, trackName, startSeconds, durationSeconds, expectedSampleRate)
%LOAD_ESTIMATED_EXCERPT Validate Phase 1 G provenance and load one excerpt.

arguments
    estimatedDirectory (1, 1) string
    phase1ResultPath (1, 1) string
    phase1MetadataPath (1, 1) string
    mixturePath (1, 1) string
    trackName (1, 1) string
    startSeconds (1, 1) double {mustBeFinite, mustBeNonnegative}
    durationSeconds (1, 1) double {mustBeFinite, mustBePositive}
    expectedSampleRate (1, 1) double {mustBeFinite, mustBePositive}
end

requiredFiles = [phase1ResultPath, phase1MetadataPath, mixturePath];
if ~all(isfile(requiredFiles)) || ~isfolder(estimatedDirectory)
    error("ELEC5305:Comparison:MissingEstimatedInput", ...
        "Phase 1 G cached estimates or provenance files are missing.");
end

result = jsondecode(fileread(phase1ResultPath));
metadata = jsondecode(fileread(phase1MetadataPath));
validate_provenance(result, metadata, trackName, expectedSampleRate);

mixtureInfo = audioinfo(mixturePath);
if mixtureInfo.SampleRate ~= expectedSampleRate || mixtureInfo.NumChannels ~= 2
    error("ELEC5305:Comparison:DatasetAudioProperties", ...
        "Dataset mixture must be stereo at %.12g Hz.", expectedSampleRate);
end
if mixtureInfo.TotalSamples ~= result.frames
    error("ELEC5305:Comparison:FullTrackAlignment", ...
        "G estimate length %d does not equal dataset length %d; no trimming is allowed.", ...
        result.frames, mixtureInfo.TotalSamples);
end

startOffsetSamples = startSeconds * expectedSampleRate;
frameCount = durationSeconds * expectedSampleRate;
if startOffsetSamples ~= round(startOffsetSamples) || frameCount ~= round(frameCount)
    error("ELEC5305:Comparison:NonintegerExcerpt", ...
        "Excerpt boundaries must map exactly to integer samples.");
end
startFrame = round(startOffsetSamples) + 1;
frameCount = round(frameCount);
endFrame = startFrame + frameCount - 1;
if endFrame > result.frames
    error("ELEC5305:Comparison:ExcerptTooShort", ...
        "Requested excerpt ends after the validated G full-track estimate.");
end

stemNames = ["vocals", "drums", "bass", "other"];
stereo = struct();
mono = struct();
sourcePaths = struct();
stemColumn = strings(numel(stemNames), 1);
sourcePathColumn = strings(numel(stemNames), 1);
stereoRmsLeft = zeros(numel(stemNames), 1);
stereoRmsRight = zeros(numel(stemNames), 1);
stereoPeak = zeros(numel(stemNames), 1);
monoRms = zeros(numel(stemNames), 1);
monoPeak = zeros(numel(stemNames), 1);
frames = zeros(numel(stemNames), 1);
sampleRates = zeros(numel(stemNames), 1);
provenanceIdentifiers = strings(numel(stemNames), 1);

modelConfig = metadata.model_configuration;
modelIdentifier = string(modelConfig.configuration) + "|" + ...
    string(modelConfig.repository) + "@" + string(modelConfig.revision) + ...
    "|fingerprint=" + string(metadata.configuration_fingerprint);

for stemIndex = 1:numel(stemNames)
    stemName = stemNames(stemIndex);
    fieldName = char(stemName);
    expectedPath = fullfile(estimatedDirectory, stemName + ".wav");
    outputRecord = result.listening_outputs.(fieldName);
    sourcePath = string(outputRecord.path);
    if ~strcmpi(char(sourcePath), char(expectedPath))
        error("ELEC5305:Comparison:UnexpectedEstimatedPath", ...
            "Result marker path for %s does not match the fixed G cache directory.", stemName);
    end
    if ~isfile(sourcePath)
        error("ELEC5305:Comparison:MissingStem", "Missing G cached stem: %s", sourcePath);
    end
    actualHash = compute_sha256(sourcePath);
    if ~strcmpi(char(actualHash), char(string(outputRecord.sha256)))
        error("ELEC5305:Comparison:StemHash", ...
            "SHA-256 mismatch for G cached %s stem.", stemName);
    end

    info = audioinfo(sourcePath);
    if info.SampleRate ~= expectedSampleRate || info.NumChannels ~= 2 || ...
            info.TotalSamples ~= result.frames || info.BitsPerSample ~= 32
        error("ELEC5305:Comparison:EstimatedAudioProperties", ...
            "Unexpected sample rate, channels, frames, or bit depth for %s.", sourcePath);
    end
    if outputRecord.sample_rate ~= expectedSampleRate || outputRecord.channels ~= 2 || ...
            outputRecord.frames ~= result.frames || string(outputRecord.subtype) ~= "FLOAT"
        error("ELEC5305:Comparison:EstimatedMarkerProperties", ...
            "Phase 1 marker audio properties are inconsistent for %s.", stemName);
    end
    if ~logical(result.finite.(fieldName)) || logical(result.clipping.(fieldName)) || ...
            result.stem_peaks.(fieldName) >= 1
        error("ELEC5305:Comparison:EstimatedIntegrity", ...
            "Phase 1 marker does not certify finite, unclipped %s audio.", stemName);
    end

    [audio, sampleRate] = audioread(sourcePath, [startFrame, endFrame], "double");
    if sampleRate ~= expectedSampleRate || size(audio, 1) ~= frameCount || size(audio, 2) ~= 2
        error("ELEC5305:Comparison:EstimatedExcerptShape", ...
            "Aligned excerpt read failed for %s.", sourcePath);
    end
    if any(~isfinite(audio), "all") || max(abs(audio), [], "all") >= 1
        error("ELEC5305:Comparison:EstimatedExcerptIntegrity", ...
            "Estimated excerpt for %s is nonfinite or clipped.", stemName);
    end

    stereo.(fieldName) = audio;
    mono.(fieldName) = downmix_stereo_to_mono(audio);
    sourcePaths.(fieldName) = sourcePath;
    stemColumn(stemIndex) = stemName;
    sourcePathColumn(stemIndex) = sourcePath;
    stereoRmsLeft(stemIndex) = sqrt(mean(audio(:, 1) .^ 2));
    stereoRmsRight(stemIndex) = sqrt(mean(audio(:, 2) .^ 2));
    stereoPeak(stemIndex) = max(abs(audio), [], "all");
    monoRms(stemIndex) = sqrt(mean(mono.(fieldName) .^ 2));
    monoPeak(stemIndex) = max(abs(mono.(fieldName)));
    frames(stemIndex) = size(audio, 1);
    sampleRates(stemIndex) = sampleRate;
    provenanceIdentifiers(stemIndex) = modelIdentifier;
end

estimated = struct();
estimated.stereo = stereo;
estimated.mono = mono;
estimated.source_paths = sourcePaths;
estimated.sample_rate_hz = expectedSampleRate;
estimated.start_frame_matlab_1_based = startFrame;
estimated.end_frame_matlab_1_based_inclusive = endFrame;
estimated.frame_count = frameCount;
estimated.full_track_frames = result.frames;
estimated.phase1_result = result;
estimated.phase1_metadata = metadata;
estimated.stats = table(stemColumn, sourcePathColumn, stereoRmsLeft, ...
    stereoRmsRight, stereoPeak, monoRms, monoPeak, frames, sampleRates, ...
    provenanceIdentifiers, 'VariableNames', { ...
    'stem', 'source_path', 'stereo_rms_L', 'stereo_rms_R', 'stereo_peak', ...
    'mono_rms', 'mono_peak', 'frames', 'sample_rate', ...
    'provenance_model_identifier'});
end

function validate_provenance(result, metadata, trackName, expectedSampleRate)
if string(result.status) ~= "complete" || string(metadata.status) ~= "complete" || ...
        logical(result.official_test_used) || ...
        string(result.configuration) ~= "G_pretrained_HTDemucs_FT" || ...
        string(result.song) ~= trackName
    error("ELEC5305:Comparison:ProvenanceIdentity", ...
        "Phase 1 marker is not the complete fixed validation-track G result.");
end
if string(result.configuration_fingerprint) ~= string(metadata.configuration_fingerprint)
    error("ELEC5305:Comparison:ProvenanceFingerprint", ...
        "Phase 1 song and run fingerprints differ.");
end
if result.sample_rate ~= expectedSampleRate || result.channels ~= 2 || ...
        result.frames <= 0 || ~logical(result.all_finite) || logical(result.any_clipping)
    error("ELEC5305:Comparison:ProvenanceIntegrity", ...
        "Phase 1 song marker fails sample-rate, channel, finite, or clipping gates.");
end
config = metadata.model_configuration;
if string(config.configuration) ~= "G_pretrained_HTDemucs_FT" || ...
        ~logical(config.official_pretrained) || logical(config.custom_checkpoint_used) || ...
        string(config.repository) ~= "adefossez/HTDemucs-ft" || ...
        config.inference.sample_rate ~= expectedSampleRate || config.inference.channels ~= 2 || ...
        string(config.inference.output_processing) ~= "none" || ...
        logical(config.inference.automatic_rescaling) || ...
        string(config.inference.wav_subtype) ~= "FLOAT"
    error("ELEC5305:Comparison:ModelProvenance", ...
        "G cache is not the official unscaled htdemucs_ft configuration.");
end
models = config.models;
if numel(models) ~= 4
    error("ELEC5305:Comparison:ModelBag", "Expected four source-specific FT models.");
end
expectedTargets = ["drums", "bass", "other", "vocals"];
for modelIndex = 1:4
    weights = double(models(modelIndex).bag_weights(:));
    if string(models(modelIndex).target_assignment) ~= expectedTargets(modelIndex) || ...
            numel(weights) ~= 4 || nnz(weights) ~= 1 || weights(modelIndex) ~= 1
        error("ELEC5305:Comparison:ModelBag", ...
            "Source-specific FT bag assignment is not the frozen G configuration.");
    end
end
end

function sha256 = compute_sha256(filePath)
fid = fopen(filePath, "rb");
if fid < 0
    error("ELEC5305:Comparison:HashRead", "Cannot open file for SHA-256: %s", filePath);
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
sha256 = string(upper(reshape(dec2hex(typecast(digest.digest(), "uint8"), 2).', 1, [])));
end

function excerpt = load_musdb_gt_excerpt(trackDirectory, startSeconds, durationSeconds, expectedSampleRate)
%LOAD_MUSDB_GT_EXCERPT Load one aligned MUSDB18-HQ ground-truth excerpt.

arguments
    trackDirectory (1, 1) string
    startSeconds (1, 1) double {mustBeFinite, mustBeNonnegative}
    durationSeconds (1, 1) double {mustBeFinite, mustBePositive}
    expectedSampleRate (1, 1) double {mustBeFinite, mustBePositive}
end

sourceNames = ["mixture", "vocals", "drums", "bass", "other"];
startOffsetSamples = startSeconds * expectedSampleRate;
frameCount = durationSeconds * expectedSampleRate;
if startOffsetSamples ~= round(startOffsetSamples) || frameCount ~= round(frameCount)
    error("ELEC5305:Oracle:NonintegerExcerpt", ...
        "Excerpt boundaries must map exactly to integer samples.");
end
startFrame = round(startOffsetSamples) + 1;
frameCount = round(frameCount);
endFrame = startFrame + frameCount - 1;

stereo = struct();
mono = struct();
sourceColumn = strings(numel(sourceNames), 1);
stereoRmsLeft = zeros(numel(sourceNames), 1);
stereoRmsRight = zeros(numel(sourceNames), 1);
stereoPeak = zeros(numel(sourceNames), 1);
monoRms = zeros(numel(sourceNames), 1);
monoPeak = zeros(numel(sourceNames), 1);
frames = zeros(numel(sourceNames), 1);
sampleRates = zeros(numel(sourceNames), 1);
stereoChannels = repmat(2, numel(sourceNames), 1);
monoChannels = ones(numel(sourceNames), 1);

for sourceIndex = 1:numel(sourceNames)
    sourceName = sourceNames(sourceIndex);
    audioPath = fullfile(trackDirectory, sourceName + ".wav");
    if ~isfile(audioPath)
        error("ELEC5305:Oracle:MissingGT", "Missing MUSDB18-HQ GT file: %s", audioPath);
    end
    info = audioinfo(audioPath);
    if info.SampleRate ~= expectedSampleRate
        error("ELEC5305:Oracle:SampleRate", ...
            "%s is %.12g Hz; expected %.12g Hz.", audioPath, info.SampleRate, expectedSampleRate);
    end
    if info.NumChannels ~= 2
        error("ELEC5305:Oracle:ChannelCount", ...
            "%s has %d channels; expected stereo.", audioPath, info.NumChannels);
    end
    if info.TotalSamples < endFrame
        error("ELEC5305:Oracle:ExcerptTooShort", ...
            "%s has %d frames and does not reach requested frame %d.", ...
            audioPath, info.TotalSamples, endFrame);
    end

    [audio, sampleRate] = audioread(audioPath, [startFrame, endFrame], "double");
    if sampleRate ~= expectedSampleRate || size(audio, 1) ~= frameCount || size(audio, 2) ~= 2
        error("ELEC5305:Oracle:ExcerptShape", ...
            "Aligned excerpt read failed for %s.", audioPath);
    end
    if any(~isfinite(audio), "all")
        error("ELEC5305:Oracle:NonfiniteGT", "%s excerpt contains NaN or Inf.", audioPath);
    end

    fieldName = char(sourceName);
    stereo.(fieldName) = audio;
    mono.(fieldName) = downmix_stereo_to_mono(audio);
    sourceColumn(sourceIndex) = sourceName;
    stereoRmsLeft(sourceIndex) = sqrt(mean(audio(:, 1) .^ 2));
    stereoRmsRight(sourceIndex) = sqrt(mean(audio(:, 2) .^ 2));
    stereoPeak(sourceIndex) = max(abs(audio), [], "all");
    monoRms(sourceIndex) = sqrt(mean(mono.(fieldName) .^ 2));
    monoPeak(sourceIndex) = max(abs(mono.(fieldName)));
    frames(sourceIndex) = size(audio, 1);
    sampleRates(sourceIndex) = sampleRate;
end

excerpt = struct();
excerpt.stereo = stereo;
excerpt.mono = mono;
excerpt.sample_rate_hz = expectedSampleRate;
excerpt.start_frame_matlab_1_based = startFrame;
excerpt.end_frame_matlab_1_based_inclusive = endFrame;
excerpt.frame_count = frameCount;
excerpt.stats = table(sourceColumn, stereoRmsLeft, stereoRmsRight, stereoPeak, ...
    monoRms, monoPeak, frames, stereoChannels, monoChannels, sampleRates, ...
    'VariableNames', { ...
    'source', 'stereo_rms_L', 'stereo_rms_R', 'stereo_peak', ...
    'mono_rms', 'mono_peak', 'frames', 'stereo_channels', 'mono_channels', ...
    'sample_rate'});
end

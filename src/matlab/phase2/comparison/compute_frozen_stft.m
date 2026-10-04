function [spectrum, frequencyHz, timeSeconds] = compute_frozen_stft(signal, sampleRate)
%COMPUTE_FROZEN_STFT Phase 2 periodic-Hann STFT with frozen framing.

arguments
    signal (:, :) double {mustBeFinite}
    sampleRate (1, 1) double {mustBeFinite, mustBePositive}
end

windowLength = 1024;
hopSize = 256;
overlapLength = 768;
fftSize = 1024;
if sampleRate ~= 44100 || size(signal, 1) < windowLength || isempty(signal)
    error("ELEC5305:Spectrotemporal:FrozenSTFT", ...
        "Frozen STFT requires 44.1 kHz and at least 1024 samples.");
end

window = hann(windowLength, "periodic");
channelCount = size(signal, 2);
for channel = channelCount:-1:1
    [channelSpectrum, channelFrequency, channelTime] = spectrogram( ...
        signal(:, channel), window, overlapLength, fftSize, sampleRate);
    if channel == channelCount
        spectrum = complex(zeros(size(channelSpectrum, 1), ...
            size(channelSpectrum, 2), channelCount));
        frequencyHz = channelFrequency;
        timeSeconds = channelTime;
    elseif ~isequal(channelFrequency, frequencyHz) || ~isequal(channelTime, timeSeconds)
        error("ELEC5305:Spectrotemporal:STFTGrid", ...
            "STFT grids differ between channels.");
    end
    spectrum(:, :, channel) = channelSpectrum;
end

if size(spectrum, 1) ~= 513 || frequencyHz(1) ~= 0 || ...
        frequencyHz(end) ~= sampleRate / 2 || any(~isfinite(spectrum), "all")
    error("ELEC5305:Spectrotemporal:STFTGrid", ...
        "Frozen one-sided STFT grid validation failed.");
end
end

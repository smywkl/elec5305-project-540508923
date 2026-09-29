function metrics = compute_binaural_comparison_metrics(reference, estimate, sampleRate, stftConfig)
%COMPUTE_BINAURAL_COMPARISON_METRICS Compare raw floating-point binaural mixes.

arguments
    reference (:, 2) double {mustBeFinite}
    estimate (:, 2) double {mustBeFinite}
    sampleRate (1, 1) double {mustBeFinite, mustBePositive}
    stftConfig (1, 1) struct
end

if size(reference, 1) ~= size(estimate, 1) || isempty(reference)
    error("ELEC5305:Comparison:MetricAlignment", ...
        "Reference and estimate must be nonempty, aligned stereo arrays.");
end
validate_stft_config(stftConfig);

siSdr = zeros(1, 2);
relativeRmse = zeros(1, 2);
logMagnitudeMae = zeros(1, 2);
window = hann(stftConfig.window_length_samples, "periodic");
overlapLength = stftConfig.window_length_samples - stftConfig.hop_size_samples;

for channel = 1:2
    referenceChannel = reference(:, channel);
    estimateChannel = estimate(:, channel);
    siSdr(channel) = transparent_si_sdr(referenceChannel, estimateChannel);
    errorSignal = estimateChannel - referenceChannel;
    referenceRms = sqrt(mean(referenceChannel .^ 2));
    if referenceRms <= eps
        error("ELEC5305:Comparison:SilentReference", ...
            "Relative RMSE is undefined for a silent reference.");
    end
    relativeRmse(channel) = sqrt(mean(errorSignal .^ 2)) / referenceRms;

    referenceStft = spectrogram(referenceChannel, window, overlapLength, ...
        stftConfig.fft_size, sampleRate);
    estimateStft = spectrogram(estimateChannel, window, overlapLength, ...
        stftConfig.fft_size, sampleRate);
    referenceDb = 20 * log10(abs(referenceStft) + eps);
    estimateDb = 20 * log10(abs(estimateStft) + eps);
    logMagnitudeMae(channel) = mean(abs(estimateDb - referenceDb), "all");
end

metrics = struct();
metrics.si_sdr_L_db = siSdr(1);
metrics.si_sdr_R_db = siSdr(2);
metrics.binaural_si_sdr_db = mean(siSdr);
metrics.relative_rmse_L = relativeRmse(1);
metrics.relative_rmse_R = relativeRmse(2);
metrics.relative_rmse_mean = mean(relativeRmse);
metrics.stft_logmag_mae_L_db = logMagnitudeMae(1);
metrics.stft_logmag_mae_R_db = logMagnitudeMae(2);
metrics.stft_logmag_mae_mean_db = mean(logMagnitudeMae);
end

function value = transparent_si_sdr(reference, estimate)
reference = reference(:) - mean(reference);
estimate = estimate(:) - mean(estimate);
referenceEnergy = sum(reference .^ 2);
if referenceEnergy <= eps
    error("ELEC5305:Comparison:SilentReference", ...
        "SI-SDR is undefined for a silent reference.");
end
alpha = dot(estimate, reference) / referenceEnergy;
target = alpha * reference;
noise = estimate - target;
targetEnergy = sum(target .^ 2);
noiseEnergy = sum(noise .^ 2);
if noiseEnergy <= eps * max(targetEnergy, 1)
    value = 300;
else
    value = 10 * log10((targetEnergy + eps) / (noiseEnergy + eps));
    value = min(value, 300);
end
if ~isfinite(value)
    error("ELEC5305:Comparison:NonfiniteSISDR", "SI-SDR is nonfinite.");
end
end

function validate_stft_config(config)
required = ["window_length_samples", "hop_size_samples", "fft_size", "window_type"];
if ~all(isfield(config, required)) || ...
        config.window_length_samples <= 0 || config.hop_size_samples <= 0 || ...
        config.hop_size_samples > config.window_length_samples || ...
        config.fft_size < config.window_length_samples || ...
        string(config.window_type) ~= "periodic Hann"
    error("ELEC5305:Comparison:STFTConfig", ...
        "STFT configuration must match the Phase 2.2 periodic-Hann setup.");
end
end

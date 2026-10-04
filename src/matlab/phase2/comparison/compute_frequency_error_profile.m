function result = compute_frequency_error_profile(reference, residual, sampleRate)
%COMPUTE_FREQUENCY_ERROR_PROFILE Sum linear STFT powers over time/channels.

arguments
    reference (:, :) double {mustBeFinite}
    residual (:, :) double {mustBeFinite}
    sampleRate (1, 1) double {mustBeFinite, mustBePositive}
end

if ~isequal(size(reference), size(residual)) || size(reference, 2) < 1
    error("ELEC5305:Spectrotemporal:ProfileAlignment", ...
        "Reference and residual arrays must have identical nonempty shapes.");
end
[referenceStft, frequencyHz, timeSeconds] = compute_frozen_stft(reference, sampleRate);
[residualStft, residualFrequency, residualTime] = compute_frozen_stft(residual, sampleRate);
if ~isequal(frequencyHz, residualFrequency) || ~isequal(timeSeconds, residualTime)
    error("ELEC5305:Spectrotemporal:ProfileGrid", "Reference/residual STFT grids differ.");
end

oraclePower = squeeze(sum(abs(referenceStft) .^ 2, [2, 3]));
residualPower = squeeze(sum(abs(residualStft) .^ 2, [2, 3]));
[relativeErrorDb, metricStatus] = relative_power_db(residualPower, oraclePower);
result = struct("frequency_hz", frequencyHz, "time_seconds", timeSeconds, ...
    "oracle_power", oraclePower, "residual_power", residualPower, ...
    "relative_error_db", relativeErrorDb, "metric_status", metricStatus, ...
    "reference_stft", referenceStft, "residual_stft", residualStft);
end

function [value, status] = relative_power_db(errorPower, referencePower)
value = nan(size(errorPower));
status = repmat("DEFINED", size(errorPower));
zeroReference = referencePower == 0;
zeroResidual = errorPower == 0 & ~zeroReference;
defined = ~zeroReference & ~zeroResidual;
value(defined) = 10 * log10(errorPower(defined) ./ referencePower(defined));
value(zeroResidual) = -Inf;
status(zeroReference) = "ZERO_REFERENCE_BIN";
status(zeroResidual) = "EXACT_ZERO_RESIDUAL";
if any(referencePower < 0) || any(errorPower < 0) || ...
        any(~isfinite(referencePower)) || any(~isfinite(errorPower))
    error("ELEC5305:Spectrotemporal:PowerIntegrity", "Power values are invalid.");
end
end

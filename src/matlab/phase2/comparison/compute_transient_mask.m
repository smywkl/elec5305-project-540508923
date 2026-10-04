function result = compute_transient_mask(gtMonoMixture, renderedLength, sampleRate)
%COMPUTE_TRANSIENT_MASK Deterministic per-song GT positive-spectral-flux mask.

arguments
    gtMonoMixture (:, 1) double {mustBeFinite}
    renderedLength (1, 1) double {mustBeInteger, mustBePositive}
    sampleRate (1, 1) double {mustBeFinite, mustBePositive}
end

padding = renderedLength - numel(gtMonoMixture);
if padding < 0
    error("ELEC5305:Spectrotemporal:TransientAlignment", ...
        "Rendered length is shorter than the GT mixture.");
end
padded = [gtMonoMixture; zeros(padding, 1)];
[mixtureStft, frequencyHz, timeSeconds] = compute_frozen_stft(padded, sampleRate);
magnitude = abs(mixtureStft(:, :, 1));
frameCount = size(magnitude, 2);
validIndices = (2:frameCount).';
positiveDifference = max(magnitude(:, 2:end) - magnitude(:, 1:end-1), 0);
flux = sum(positiveDifference .^ 2, 1).';
validCount = numel(validIndices);
selectedCount = ceil(0.20 * validCount);
ranking = sortrows([-flux, validIndices], [1, 2]);
selectedIndices = sort(ranking(1:selectedCount, 2));
frameClass = repmat("NON_HIGH_TRANSIENT", frameCount, 1);
frameClass(1) = "NO_PREDECESSOR";
frameClass(selectedIndices) = "HIGH_TRANSIENT";
fluxAll = nan(frameCount, 1);
fluxAll(validIndices) = flux;

result = struct("frame_index", (1:frameCount).', "time_seconds", timeSeconds(:), ...
    "spectral_flux", fluxAll, "frame_class", frameClass, ...
    "valid_frame_count", validCount, "selected_frame_count", selectedCount, ...
    "selected_frame_indices", selectedIndices, "padding_samples", padding, ...
    "frequency_hz", frequencyHz);
end

function [binauralRaw, lookups, diagnostics] = render_stem_mix(monoStems, subject, conditionName, requestedAzimuthsDeg, requestedElevationDeg, maximumMismatchDeg)
%RENDER_STEM_MIX Render and sum four aligned mono stems as point sources.

arguments
    monoStems (1, 1) struct
    subject (1, 1) struct
    conditionName (1, 1) string
    requestedAzimuthsDeg (1, 4) double {mustBeFinite}
    requestedElevationDeg (1, 1) double {mustBeFinite}
    maximumMismatchDeg (1, 1) double {mustBeFinite, mustBeNonnegative}
end

stemNames = ["bass", "vocals", "drums", "other"];
inputLength = [];
binauralRaw = [];
lookups = repmat(struct(), numel(stemNames), 1);
stemDiagnostics = repmat(struct(), numel(stemNames), 1);

for stemIndex = 1:numel(stemNames)
    stemName = stemNames(stemIndex);
    fieldName = char(stemName);
    if ~isfield(monoStems, fieldName)
        error("ELEC5305:Spatial:MissingStem", "Missing mono stem '%s'.", stemName);
    end
    mono = double(monoStems.(fieldName));
    mono = mono(:);
    if isempty(inputLength)
        inputLength = numel(mono);
    elseif numel(mono) ~= inputLength
        error("ELEC5305:Spatial:StemAlignment", ...
            "Mono stems do not have equal frame counts.");
    end
    if any(~isfinite(mono))
        error("ELEC5305:Spatial:NonfiniteStem", ...
            "Stem '%s' contains NaN or Inf.", stemName);
    end

    match = find_hrir_direction(subject, requestedAzimuthsDeg(stemIndex), requestedElevationDeg);
    if match.angular_mismatch_deg > maximumMismatchDeg
        error("ELEC5305:Spatial:DirectionMismatch", ...
            "%s/%s mismatch %.9g deg exceeds %.9g deg.", ...
            conditionName, stemName, match.angular_mismatch_deg, maximumMismatchDeg);
    end
    [rendered, renderInfo] = render_static_binaural(mono, match.left_hrir, match.right_hrir);
    if isempty(binauralRaw)
        binauralRaw = zeros(size(rendered));
    end
    % Preserve the fixed bass, vocals, drums, other summation order.
    binauralRaw = binauralRaw + rendered;

    lookups(stemIndex).condition = conditionName;
    lookups(stemIndex).stem = stemName;
    lookups(stemIndex).requested_azimuth_deg = match.requested_azimuth_deg;
    lookups(stemIndex).requested_elevation_deg = match.requested_elevation_deg;
    lookups(stemIndex).matched_azimuth_deg = match.actual_azimuth_deg;
    lookups(stemIndex).matched_elevation_deg = match.actual_elevation_deg;
    lookups(stemIndex).measurement_index = match.measurement_index;
    lookups(stemIndex).angular_mismatch_deg = match.angular_mismatch_deg;
    stemDiagnostics(stemIndex).stem = stemName;
    stemDiagnostics(stemIndex).render = renderInfo;
end

if any(~isfinite(binauralRaw), "all")
    error("ELEC5305:Spatial:NonfiniteMix", "Rendered mix contains NaN or Inf.");
end
expectedLength = inputLength + size(subject.hrir, 3) - 1;
if size(binauralRaw, 1) ~= expectedLength || size(binauralRaw, 2) ~= 2
    error("ELEC5305:Spatial:OutputShape", ...
        "Rendered output shape violates the N+L-1 stereo invariant.");
end

diagnostics = struct();
diagnostics.condition = conditionName;
diagnostics.input_frames = inputLength;
diagnostics.hrir_length = size(subject.hrir, 3);
diagnostics.expected_output_frames = expectedLength;
diagnostics.actual_output_frames = size(binauralRaw, 1);
diagnostics.raw_peak = max(abs(binauralRaw), [], "all");
diagnostics.raw_left_rms = sqrt(mean(binauralRaw(:, 1) .^ 2));
diagnostics.raw_right_rms = sqrt(mean(binauralRaw(:, 2) .^ 2));
diagnostics.finite = all(isfinite(binauralRaw), "all");
diagnostics.stems = stemDiagnostics;
end

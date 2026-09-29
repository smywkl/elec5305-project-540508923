function [oracleRaw, lookups, diagnostics] = render_oracle_mix(monoStems, subject, conditionName, requestedAzimuthsDeg, requestedElevationDeg, maximumMismatchDeg)
%RENDER_ORACLE_MIX Render and sum four mono GT stems as point sources.

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
oracleRaw = [];
lookups = repmat(struct(), numel(stemNames), 1);
stemDiagnostics = repmat(struct(), numel(stemNames), 1);

for stemIndex = 1:numel(stemNames)
    stemName = stemNames(stemIndex);
    fieldName = char(stemName);
    if ~isfield(monoStems, fieldName)
        error("ELEC5305:Oracle:MissingStem", "Missing mono stem '%s'.", stemName);
    end
    mono = double(monoStems.(fieldName));
    mono = mono(:);
    if isempty(inputLength)
        inputLength = numel(mono);
    elseif numel(mono) ~= inputLength
        error("ELEC5305:Oracle:StemAlignment", "Mono stems do not have equal frame counts.");
    end
    if any(~isfinite(mono))
        error("ELEC5305:Oracle:NonfiniteStem", "Stem '%s' contains NaN or Inf.", stemName);
    end

    match = find_hrir_direction(subject, requestedAzimuthsDeg(stemIndex), requestedElevationDeg);
    if match.angular_mismatch_deg > maximumMismatchDeg
        error("ELEC5305:Oracle:DirectionMismatch", ...
            "%s/%s mismatch %.9g deg exceeds %.9g deg.", ...
            conditionName, stemName, match.angular_mismatch_deg, maximumMismatchDeg);
    end
    [rendered, renderInfo] = render_static_binaural(mono, match.left_hrir, match.right_hrir);
    if isempty(oracleRaw)
        oracleRaw = zeros(size(rendered));
    end
    oracleRaw = oracleRaw + rendered;

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

if any(~isfinite(oracleRaw), "all")
    error("ELEC5305:Oracle:NonfiniteMix", "Oracle mix contains NaN or Inf.");
end
expectedLength = inputLength + size(subject.hrir, 3) - 1;
if size(oracleRaw, 1) ~= expectedLength || size(oracleRaw, 2) ~= 2
    error("ELEC5305:Oracle:OutputShape", "Oracle output shape violates N+L-1 stereo invariant.");
end

diagnostics = struct();
diagnostics.condition = conditionName;
diagnostics.input_frames = inputLength;
diagnostics.hrir_length = size(subject.hrir, 3);
diagnostics.expected_output_frames = expectedLength;
diagnostics.actual_output_frames = size(oracleRaw, 1);
diagnostics.raw_peak = max(abs(oracleRaw), [], "all");
diagnostics.raw_left_rms = sqrt(mean(oracleRaw(:, 1) .^ 2));
diagnostics.raw_right_rms = sqrt(mean(oracleRaw(:, 2) .^ 2));
diagnostics.finite = all(isfinite(oracleRaw), "all");
diagnostics.stems = stemDiagnostics;
end

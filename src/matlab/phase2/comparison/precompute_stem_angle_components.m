function [gtComponents, errorComponents, audit] = precompute_stem_angle_components(gtMonoStems, errorMonoStems, subject, anglesDeg, elevationDeg, maximumMismatchDeg)
%PRECOMPUTE_STEM_ANGLE_COMPONENTS Render each stem once at each frozen angle.
%   Components are generated only through find_hrir_direction and the
%   existing full-linear-convolution renderer. Every stored component is
%   immediately audited against a second direct renderer call.

arguments
    gtMonoStems (1, 1) struct
    errorMonoStems (1, 1) struct
    subject (1, 1) struct
    anglesDeg (1, :) double {mustBeFinite}
    elevationDeg (1, 1) double {mustBeFinite}
    maximumMismatchDeg (1, 1) double {mustBeFinite, mustBeNonnegative}
end

stemNames = ["bass", "vocals", "drums", "other"];
if numel(unique(anglesDeg)) ~= numel(anglesDeg)
    error("ELEC5305:Robustness:DuplicateAngles", "Precomputation angles must be unique.");
end

gtComponents = cell(4, numel(anglesDeg));
errorComponents = cell(4, numel(anglesDeg));
gtRelativeErrors = nan(4, numel(anglesDeg));
gtAbsoluteErrors = nan(4, numel(anglesDeg));
gtStatuses = strings(4, numel(anglesDeg));
errorRelativeErrors = nan(4, numel(anglesDeg));
errorAbsoluteErrors = nan(4, numel(anglesDeg));
errorStatuses = strings(4, numel(anglesDeg));
measurementIndices = zeros(1, numel(anglesDeg));

for angleIndex = 1:numel(anglesDeg)
    match = find_hrir_direction(subject, anglesDeg(angleIndex), elevationDeg);
    if ~match.exact_match || match.angular_mismatch_deg ~= 0 || ...
            match.angular_mismatch_deg > maximumMismatchDeg || ...
            match.actual_azimuth_deg ~= anglesDeg(angleIndex) || ...
            match.actual_elevation_deg ~= elevationDeg
        error("ELEC5305:Robustness:NonexactDirection", ...
            "Frozen angle %.17g degrees is not an exact HRTF grid match.", anglesDeg(angleIndex));
    end
    measurementIndices(angleIndex) = match.measurement_index;
    for stemIndex = 1:4
        fieldName = char(stemNames(stemIndex));
        if ~isfield(gtMonoStems, fieldName) || ~isfield(errorMonoStems, fieldName)
            error("ELEC5305:Robustness:MissingStem", "Missing stem %s.", stemNames(stemIndex));
        end
        gt = double(gtMonoStems.(fieldName)(:));
        sourceError = double(errorMonoStems.(fieldName)(:));
        if isempty(gt) || numel(gt) ~= numel(sourceError) || ...
                any(~isfinite(gt)) || any(~isfinite(sourceError))
            error("ELEC5305:Robustness:InvalidSource", ...
                "Invalid GT/error source pair for %s.", stemNames(stemIndex));
        end

        gtComponents{stemIndex, angleIndex} = render_static_binaural( ...
            gt, match.left_hrir, match.right_hrir);
        errorComponents{stemIndex, angleIndex} = render_static_binaural( ...
            sourceError, match.left_hrir, match.right_hrir);

        gtDirect = render_static_binaural(gt, match.left_hrir, match.right_hrir);
        errorDirect = render_static_binaural(sourceError, match.left_hrir, match.right_hrir);
        [gtRelativeErrors(stemIndex, angleIndex), gtAbsoluteErrors(stemIndex, angleIndex), ...
            gtStatuses(stemIndex, angleIndex)] = validate_component( ...
            gtComponents{stemIndex, angleIndex}, gtDirect);
        [errorRelativeErrors(stemIndex, angleIndex), errorAbsoluteErrors(stemIndex, angleIndex), ...
            errorStatuses(stemIndex, angleIndex)] = validate_component( ...
            errorComponents{stemIndex, angleIndex}, errorDirect);
    end
end

audit = struct();
audit.stem_names = stemNames;
audit.angles_deg = anglesDeg;
audit.measurement_indices = measurementIndices;
audit.gt_case_count = numel(gtComponents);
audit.error_case_count = numel(errorComponents);
audit.gt_pass_count = sum(startsWith(gtStatuses, "PASS"), "all");
audit.error_pass_count = sum(startsWith(errorStatuses, "PASS"), "all");
audit.gt_relative_errors = gtRelativeErrors;
audit.gt_absolute_errors = gtAbsoluteErrors;
audit.gt_statuses = gtStatuses;
audit.error_relative_errors = errorRelativeErrors;
audit.error_absolute_errors = errorAbsoluteErrors;
audit.error_statuses = errorStatuses;
audit.gt_zero_denominator_count = sum(gtStatuses == "PASS_ABSOLUTE_ZERO_DENOMINATOR", "all");
audit.error_zero_denominator_count = sum(errorStatuses == "PASS_ABSOLUTE_ZERO_DENOMINATOR", "all");
audit.gt_max_relative_error = maximum_finite_or_zero(gtRelativeErrors);
audit.error_max_relative_error = maximum_finite_or_zero(errorRelativeErrors);
audit.gt_max_zero_denominator_absolute_error = maximum_for_status( ...
    gtAbsoluteErrors, gtStatuses, "PASS_ABSOLUTE_ZERO_DENOMINATOR");
audit.error_max_zero_denominator_absolute_error = maximum_for_status( ...
    errorAbsoluteErrors, errorStatuses, "PASS_ABSOLUTE_ZERO_DENOMINATOR");
end

function [relativeError, absoluteError, status] = validate_component(value, direct)
if ~isa(value, "double") || ~isequal(size(value), size(direct)) || ...
        size(value, 2) ~= 2 || any(~isfinite(value), "all") || any(~isfinite(direct), "all")
    error("ELEC5305:Robustness:ComponentShape", "Invalid rendered component.");
end
difference = value - direct;
absoluteError = sqrt(sum(difference .^ 2, "all"));
denominatorEnergy = sum(direct .^ 2, "all");
if denominatorEnergy == 0
    relativeError = NaN;
    if absoluteError > 1e-10
        error("ELEC5305:Robustness:ComponentAbsolute", ...
            "Zero-denominator component absolute error %.17g exceeds tolerance.", absoluteError);
    end
    status = "PASS_ABSOLUTE_ZERO_DENOMINATOR";
else
    relativeError = absoluteError / sqrt(denominatorEnergy);
    if relativeError > 1e-10
        error("ELEC5305:Robustness:ComponentRelative", ...
            "Component relative error %.17g exceeds tolerance.", relativeError);
    end
    status = "PASS_RELATIVE";
end
end

function value = maximum_finite_or_zero(values)
finiteValues = values(isfinite(values));
if isempty(finiteValues)
    value = 0;
else
    value = max(finiteValues);
end
end

function value = maximum_for_status(values, statuses, requestedStatus)
selected = values(statuses == requestedStatus);
if isempty(selected)
    value = 0;
else
    value = max(selected);
end
end

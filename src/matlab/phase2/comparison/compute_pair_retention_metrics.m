function result = compute_pair_retention_metrics(firstComponent, secondComponent)
%COMPUTE_PAIR_RETENTION_METRICS Compute frozen RQ6 pairwise metrics.
%   Exact-zero pair energy returns an explicit undefined status. No epsilon
%   regularisation or scientific-value clamping is permitted.

arguments
    firstComponent double
    secondComponent double
end

if isempty(firstComponent) || ~isequal(size(firstComponent), size(secondComponent)) || ...
        size(firstComponent, 2) ~= 2 || ...
        any(~isfinite(firstComponent), "all") || any(~isfinite(secondComponent), "all")
    error("ELEC5305:AssignmentSensitivity:PairShape", ...
        "Pair components must be finite, equally sized [frames x 2] arrays.");
end

energyFirst = sum(firstComponent .^ 2, "all");
energySecond = sum(secondComponent .^ 2, "all");
denominator = energyFirst + energySecond;
innerProduct = sum(firstComponent .* secondComponent, "all");

result = struct();
result.energy_i = energyFirst;
result.energy_j = energySecond;
result.inner_product = innerProduct;
result.denominator = denominator;

if denominator == 0
    result.pair_retention_ratio = NaN;
    result.expanded_pair_retention_ratio = NaN;
    result.cosine_alignment = NaN;
    result.algebra_relative_error = NaN;
    result.metric_status = "UNDEFINED_ZERO_PAIR_ENERGY";
    return;
end

pairSum = firstComponent + secondComponent;
pairRetention = sum(pairSum .^ 2, "all") / denominator;
expanded = 1 + 2 * innerProduct / denominator;
algebraError = abs(pairRetention - expanded) / max(1, abs(pairRetention));

if energyFirst == 0 || energySecond == 0
    cosine = NaN;
    status = "PAIR_DEFINED_COSINE_UNDEFINED_ZERO_COMPONENT_NORM";
else
    cosine = innerProduct / sqrt(energyFirst * energySecond);
    status = "DEFINED";
end

result.pair_retention_ratio = pairRetention;
result.expanded_pair_retention_ratio = expanded;
result.cosine_alignment = cosine;
result.algebra_relative_error = algebraError;
result.metric_status = status;
end

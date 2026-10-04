function result = compute_shapley_attribution(renderedComponents, oracleEnergy)
%COMPUTE_SHAPLEY_ATTRIBUTION Exact four-stem squared-error Shapley values.
%   Coalition bit order is fixed as bass (bit 1), vocals (bit 2),
%   drums (bit 3), and other (bit 4). The canonical result is computed by
%   exact enumeration of all 16 coalition values. The closed-form result
%   is returned only as an independent numerical cross-check.

arguments
    renderedComponents (1, 1) struct
    oracleEnergy (1, 1) double {mustBeFinite, mustBePositive}
end

stemNames = ["bass", "vocals", "drums", "other"];
componentSize = [];
for stemIndex = 1:4
    fieldName = char(stemNames(stemIndex));
    if ~isfield(renderedComponents, fieldName)
        error("ELEC5305:StemAttribution:MissingComponent", ...
            "Missing rendered component %s.", stemNames(stemIndex));
    end
    value = renderedComponents.(fieldName);
    if ~isa(value, "double") || size(value, 2) ~= 2 || any(~isfinite(value), "all")
        error("ELEC5305:StemAttribution:InvalidComponent", ...
            "Rendered component %s must be a finite double binaural array.", stemNames(stemIndex));
    end
    if isempty(componentSize)
        componentSize = size(value);
    elseif ~isequal(size(value), componentSize)
        error("ELEC5305:StemAttribution:ComponentSize", ...
            "All rendered components must have identical sizes.");
    end
end

coalitionIds = (0:15).';
memberships = false(16, 4);
coalitionSizes = zeros(16, 1);
coalitionValues = zeros(16, 1);
coalitionResiduals = cell(16, 1);
estimatedStemLabels = strings(16, 1);
for row = 1:16
    coalitionId = coalitionIds(row);
    residual = zeros(componentSize, "double");
    labels = strings(0, 1);
    for stemIndex = 1:4
        memberships(row, stemIndex) = logical(bitget(coalitionId, stemIndex));
        if memberships(row, stemIndex)
            fieldName = char(stemNames(stemIndex));
            residual = residual + renderedComponents.(fieldName);
            labels(end + 1, 1) = stemNames(stemIndex); %#ok<AGROW>
        end
    end
    coalitionSizes(row) = sum(memberships(row, :));
    coalitionResiduals{row} = residual;
    coalitionValues(row) = sum(residual .^ 2, "all") / oracleEnergy;
    if isempty(labels)
        estimatedStemLabels(row) = "none";
    else
        estimatedStemLabels(row) = join(labels, "+");
    end
end

shapley = zeros(4, 1);
for stemIndex = 1:4
    for coalitionId = 0:15
        if bitget(coalitionId, stemIndex) ~= 0
            continue;
        end
        coalitionSize = sum(bitget(coalitionId, 1:4));
        weight = factorial(coalitionSize) * factorial(4 - coalitionSize - 1) / factorial(4);
        withoutValue = coalitionValues(coalitionId + 1);
        withId = bitset(coalitionId, stemIndex, 1);
        withValue = coalitionValues(withId + 1);
        shapley(stemIndex) = shapley(stemIndex) + weight * (withValue - withoutValue);
    end
end

componentEnergy = zeros(4, 1);
assignedInteraction = zeros(4, 1);
analyticShapley = zeros(4, 1);
for stemIndex = 1:4
    stem = renderedComponents.(char(stemNames(stemIndex)));
    componentEnergy(stemIndex) = sum(stem .^ 2, "all");
    crossInnerProducts = 0;
    for otherIndex = 1:4
        if otherIndex == stemIndex
            continue;
        end
        other = renderedComponents.(char(stemNames(otherIndex)));
        crossInnerProducts = crossInnerProducts + sum(stem .* other, "all");
    end
    assignedInteraction(stemIndex) = crossInnerProducts / oracleEnergy;
    analyticShapley(stemIndex) = componentEnergy(stemIndex) / oracleEnergy + ...
        assignedInteraction(stemIndex);
end

singleStemNre = componentEnergy / oracleEnergy;
analyticValidationError = comparison_error(shapley, analyticShapley);
interactionIdentityError = comparison_error(shapley - singleStemNre, assignedInteraction);
fullValue = coalitionValues(16);
efficiencyError = comparison_error(sum(shapley), fullValue);

result = struct();
result.stem_names = stemNames;
result.coalition_ids = coalitionIds;
result.coalition_sizes = coalitionSizes;
result.coalition_memberships = memberships;
result.estimated_stem_labels = estimatedStemLabels;
result.coalition_values = coalitionValues;
result.coalition_residuals = coalitionResiduals;
result.component_energy = componentEnergy;
result.single_stem_nre = singleStemNre;
result.shapley_nre = shapley;
result.analytic_shapley_nre = analyticShapley;
result.assigned_interaction_nre = assignedInteraction;
result.analytic_validation_error = analyticValidationError;
result.interaction_identity_error = interactionIdentityError;
result.efficiency_error = efficiencyError;
result.empty_coalition_value = coalitionValues(1);
result.full_coalition_value = fullValue;
end

function value = comparison_error(actual, expected)
difference = abs(actual - expected);
scale = max(abs(actual), abs(expected));
value = difference;
nonzero = scale > 0;
value(nonzero) = difference(nonzero) ./ scale(nonzero);
end

function result = evaluate_error_component_assignment(gtComponents, errorComponents, angleGridDeg, assignedAnglesDeg)
%EVALUATE_ERROR_COMPONENT_ASSIGNMENT Compose pre-rendered stem components.

arguments
    gtComponents (4, :) cell
    errorComponents (4, :) cell
    angleGridDeg (1, :) double {mustBeFinite}
    assignedAnglesDeg (1, 4) double {mustBeFinite}
end

if size(gtComponents, 2) ~= numel(angleGridDeg) || ...
        ~isequal(size(gtComponents), size(errorComponents)) || ...
        numel(unique(angleGridDeg)) ~= numel(angleGridDeg)
    error("ELEC5305:Robustness:ComponentGrid", "Component grid dimensions are invalid.");
end

selectedGT = cell(4, 1);
selectedError = cell(4, 1);
componentEnergy = zeros(4, 1);
for stemIndex = 1:4
    angleIndex = find(angleGridDeg == assignedAnglesDeg(stemIndex));
    if numel(angleIndex) ~= 1
        error("ELEC5305:Robustness:AssignmentAngle", ...
            "Assigned angle %.17g does not occur exactly once in the grid.", assignedAnglesDeg(stemIndex));
    end
    selectedGT{stemIndex} = gtComponents{stemIndex, angleIndex};
    selectedError{stemIndex} = errorComponents{stemIndex, angleIndex};
    if ~isa(selectedGT{stemIndex}, "double") || ~isa(selectedError{stemIndex}, "double") || ...
            ~isequal(size(selectedGT{stemIndex}), size(selectedError{stemIndex})) || ...
            size(selectedGT{stemIndex}, 2) ~= 2 || ...
            any(~isfinite(selectedGT{stemIndex}), "all") || ...
            any(~isfinite(selectedError{stemIndex}), "all")
        error("ELEC5305:Robustness:SelectedComponent", "Invalid selected component.");
    end
    componentEnergy(stemIndex) = sum(selectedError{stemIndex} .^ 2, "all");
end

oracle = selectedGT{1};
residual = selectedError{1};
for stemIndex = 2:4
    oracle = oracle + selectedGT{stemIndex};
    residual = residual + selectedError{stemIndex};
end
A = sum(componentEnergy);
T = sum(residual .^ 2, "all");
oracleEnergy = sum(oracle .^ 2, "all");
if A <= 0 || T <= 0 || oracleEnergy <= 0
    error("ELEC5305:Robustness:NonpositiveEnergy", ...
        "A, T, and oracle energy must be positive (%.17g, %.17g, %.17g).", A, T, oracleEnergy);
end
I = T - A;
energyIdentityRelerr = abs(T - (A + I)) / max(T, A);
R = T / A;
G = 10 * log10(A / T);
V = T / oracleEnergy;
values = [A, T, I, R, G, oracleEnergy, V, energyIdentityRelerr];
if any(~isfinite(values)) || V < 0 || energyIdentityRelerr > 1e-10 || ...
        abs(G - 10 * log10(1 / R)) > 1e-12 * max(1, abs(G))
    error("ELEC5305:Robustness:AssignmentMetric", "Assignment metric invariant failed.");
end

result = struct( ...
    "assigned_angles_deg", assignedAnglesDeg, ...
    "selected_gt_components", {selectedGT}, ...
    "selected_error_components", {selectedError}, ...
    "oracle", oracle, ...
    "decomposed_residual", residual, ...
    "component_energy", componentEnergy, ...
    "A_individual_error_energy", A, ...
    "T_total_error_energy", T, ...
    "I_interaction_energy", I, ...
    "error_retention_ratio", R, ...
    "cancellation_gain_db", G, ...
    "oracle_energy", oracleEnergy, ...
    "normalized_total_error", V, ...
    "energy_identity_relerr", energyIdentityRelerr);
end

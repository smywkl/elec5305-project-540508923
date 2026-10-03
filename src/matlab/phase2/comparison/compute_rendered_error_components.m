function result = compute_rendered_error_components(errorMonoStems, subject, conditionName, requestedAzimuthsDeg, requestedElevationDeg, maximumMismatchDeg)
%COMPUTE_RENDERED_ERROR_COMPONENTS Render stem errors and compute RQ3 energies.
%   Rendering is delegated to the existing Phase 2 render_stem_mix path.

arguments
    errorMonoStems (1, 1) struct
    subject (1, 1) struct
    conditionName (1, 1) string
    requestedAzimuthsDeg (1, 4) double {mustBeFinite}
    requestedElevationDeg (1, 1) double {mustBeFinite}
    maximumMismatchDeg (1, 1) double {mustBeFinite, mustBeNonnegative}
end

stemNames = ["bass", "vocals", "drums", "other"];
[decomposedResidual, lookups, renderDiagnostics, rendered] = render_stem_mix( ...
    errorMonoStems, subject, conditionName, requestedAzimuthsDeg, ...
    requestedElevationDeg, maximumMismatchDeg);

componentEnergy = zeros(4, 1);
componentNorm = zeros(4, 1);
for stemIndex = 1:4
    value = rendered.(char(stemNames(stemIndex)));
    if ~isa(value, "double") || size(value, 2) ~= 2 || ...
            ~isequal(size(value), size(decomposedResidual)) || any(~isfinite(value), "all")
        error("ELEC5305:ErrorInteraction:RenderedComponent", ...
            "Invalid rendered error component for %s/%s.", conditionName, stemNames(stemIndex));
    end
    componentEnergy(stemIndex) = sum(value .^ 2, "all");
    componentNorm(stemIndex) = sqrt(componentEnergy(stemIndex));
end

A = sum(componentEnergy);
T = sum(decomposedResidual .^ 2, "all");
if A <= 0 || T <= 0
    error("ELEC5305:ErrorInteraction:ZeroEnergy", ...
        "A and T must both be strictly positive for %s (A=%.17g, T=%.17g).", ...
        conditionName, A, T);
end

pairIndices = [1, 2; 1, 3; 1, 4; 2, 3; 2, 4; 3, 4];
pairStemI = strings(6, 1);
pairStemJ = strings(6, 1);
pairInteraction = zeros(6, 1);
pairNormalized = zeros(6, 1);
pairCosine = nan(6, 1);
pairCosineStatus = strings(6, 1);
for pairIndex = 1:6
    i = pairIndices(pairIndex, 1);
    j = pairIndices(pairIndex, 2);
    di = rendered.(char(stemNames(i)));
    dj = rendered.(char(stemNames(j)));
    innerProduct = sum(di .* dj, "all");
    pairStemI(pairIndex) = stemNames(i);
    pairStemJ(pairIndex) = stemNames(j);
    pairInteraction(pairIndex) = 2 * innerProduct;
    pairNormalized(pairIndex) = pairInteraction(pairIndex) / A;
    if componentNorm(i) == 0 || componentNorm(j) == 0
        pairCosineStatus(pairIndex) = "UNDEFINED_ZERO_NORM";
    else
        pairCosine(pairIndex) = innerProduct / (componentNorm(i) * componentNorm(j));
        pairCosineStatus(pairIndex) = "DEFINED";
    end
end

I = sum(pairInteraction);
energyIdentityRelerr = abs(T - (A + I)) / max(T, A);
if energyIdentityRelerr > 1e-10
    error("ELEC5305:ErrorInteraction:EnergyIdentity", ...
        "Energy identity failed for %s: %.17g.", conditionName, energyIdentityRelerr);
end

result = struct();
result.decomposed_residual = decomposedResidual;
result.rendered_components = rendered;
result.lookups = lookups;
result.render_diagnostics = renderDiagnostics;
result.stem_names = stemNames;
result.component_energy = componentEnergy;
result.component_norm = componentNorm;
result.A_individual_error_energy = A;
result.T_total_error_energy = T;
result.I_interaction_energy = I;
result.error_retention_ratio = T / A;
result.cancellation_gain_db = 10 * log10(A / T);
result.energy_identity_relerr = energyIdentityRelerr;
result.pair_stem_i = pairStemI;
result.pair_stem_j = pairStemJ;
result.pair_interaction_energy = pairInteraction;
result.pair_normalized_interaction = pairNormalized;
result.pair_cosine_alignment = pairCosine;
result.pair_cosine_status = pairCosineStatus;
end

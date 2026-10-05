%% Synthetic implementation validation for Phase 2.11b

oldPath = path;
cleanupPath = onCleanup(@() path(oldPath));
scriptPath = mfilename("fullpath");
repoRoot = fileparts(fileparts(fileparts(fileparts(scriptPath))));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "comparison"));

first = [1, 0.2; -0.4, 0.3; 0.1, -0.2];
second = [-0.3, 0.1; 0.2, -0.1; 0.4, 0.05];
pair = compute_pair_retention_metrics(first, second);
assert(pair.metric_status == "DEFINED");
assert(pair.algebra_relative_error <= 1e-12);
assert(pair.pair_retention_ratio >= -1e-12);

cancelling = compute_pair_retention_metrics(first, -first);
assert(abs(cancelling.pair_retention_ratio) <= 1e-12);
aligned = compute_pair_retention_metrics(first, first);
assert(aligned.pair_retention_ratio > 1);

zero = zeros(size(first));
undefined = compute_pair_retention_metrics(zero, zero);
assert(undefined.metric_status == "UNDEFINED_ZERO_PAIR_ENERGY");
assert(isnan(undefined.pair_retention_ratio));

angles = [-30, -10, 10, 30];
assignments = sortrows(perms(angles));
assert(size(assignments, 1) == 24);
for stemIndex = 1:4
    for angle = angles
        assert(sum(assignments(:, stemIndex) == angle) == 6);
    end
end
for firstIndex = 1:3
    for secondIndex = firstIndex + 1:4
        for angleFirst = angles
            for angleSecond = angles
                if angleFirst ~= angleSecond
                    assert(sum(assignments(:, firstIndex) == angleFirst & ...
                        assignments(:, secondIndex) == angleSecond) == 2);
                end
            end
        end
    end
end

components = cat(3, first, second, 0.4 * first, -0.2 * second);
componentEnergy = squeeze(sum(components .^ 2, [1, 2]));
A = sum(componentEnergy);
residual = sum(components, 3);
T = sum(residual .^ 2, "all");
I = T - A;
R = T / A;
K = I / A;
oracleEnergy = 7.5;
U = A / oracleEnergy;
W = I / oracleEnergy;
V = T / oracleEnergy;
assert(abs(R - (1 + K)) <= 1e-12);
assert(abs(V - (U + W)) <= 1e-12);

scale = 3.25;
scaledComponents = scale * components;
scaledA = sum(squeeze(sum(scaledComponents .^ 2, [1, 2])));
scaledT = sum(sum(scaledComponents, 3) .^ 2, "all");
scaledI = scaledT - scaledA;
scaledR = scaledT / scaledA;
scaledK = scaledI / scaledA;
assert(abs(scaledA - scale ^ 2 * A) <= 1e-12 * max(1, scaledA));
assert(abs(scaledT - scale ^ 2 * T) <= 1e-12 * max(1, scaledT));
assert(abs(scaledI - scale ^ 2 * I) <= 1e-12 * max(1, abs(scaledI)));
assert(abs(scaledR - R) <= 1e-12);
assert(abs(scaledK - K) <= 1e-12);
assert(abs(scaledA / oracleEnergy - scale ^ 2 * U) <= 1e-12 * max(1, scaledA / oracleEnergy));
assert(abs(scaledI / oracleEnergy - scale ^ 2 * W) <= 1e-12 * max(1, abs(scaledI / oracleEnergy)));
assert(abs(scaledT / oracleEnergy - scale ^ 2 * V) <= 1e-12 * max(1, scaledT / oracleEnergy));

pairIndices = [1, 2; 1, 3; 1, 4; 2, 3; 2, 4; 3, 4];
J = zeros(6, 1);
for pairIndex = 1:6
    i = pairIndices(pairIndex, 1);
    j = pairIndices(pairIndex, 2);
    J(pairIndex) = 2 * sum(components(:, :, i) .* components(:, :, j), "all") / A;
end
assert(abs(sum(J) - (R - 1)) <= 1e-12);

assignmentJ = [J.'; 0.8 * J.'; 1.1 * J.'];
assignmentR = 1 + sum(assignmentJ, 2);
deltaJ = assignmentJ(1, :) - mean(assignmentJ, 1);
assert(max(abs((assignmentR - 1) - sum(assignmentJ, 2))) <= 1e-12);
assert(abs(sum(deltaJ) - (assignmentR(1) - mean(assignmentR))) <= 1e-12);
assert(max(abs(diff(assignmentR) - diff(sum(assignmentJ, 2)))) <= 1e-12);

assignmentE = [componentEnergy.'; 0.9 * componentEnergy.'; 1.2 * componentEnergy.'];
assignmentA = sum(assignmentE, 2);
deltaE = assignmentE(1, :) - mean(assignmentE, 1);
assert(abs(sum(deltaE) - (assignmentA(1) - mean(assignmentA))) <= 1e-12);

commonAtA = compute_pair_retention_metrics(first, second);
commonAtB = compute_pair_retention_metrics(0.8 * first, 0.4 * second);
differential = compute_pair_retention_metrics(first, 0.4 * second);
matchedCommon = 0.5 * (commonAtA.pair_retention_ratio + commonAtB.pair_retention_ratio);
L = differential.pair_retention_ratio - matchedCommon;
assert(abs(L - (differential.pair_retention_ratio - matchedCommon)) <= 1e-12);

% Rank-4-like inactive GT does not remove a nonzero error component.
rank4GroundTruth = zero;
rank4Estimate = 0.3 * first;
rank4Error = rank4Estimate - rank4GroundTruth;
assert(sum(rank4GroundTruth .^ 2, "all") == 0);
assert(sum(rank4Error .^ 2, "all") > 0);
rank4Pair = compute_pair_retention_metrics(rank4Error, second);
assert(rank4Pair.metric_status == "DEFINED");

fprintf("PHASE2_11B_MATLAB_SYNTHETIC_PASS\n");

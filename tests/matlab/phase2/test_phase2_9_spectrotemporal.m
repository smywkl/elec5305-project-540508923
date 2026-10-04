%% Synthetic regression tests for Phase 2.9 spectro-temporal localization

oldPath = path;
cleanupPath = onCleanup(@() path(oldPath));
scriptPath = mfilename("fullpath");
repoRoot = fileparts(fileparts(fileparts(fileparts(scriptPath))));
addpath(fullfile(repoRoot, "src", "matlab", "phase2", "comparison"));

fs = 44100;
n = 44100;
t = (0:n-1).' / fs;
reference = [sin(2*pi*1000*t), sin(2*pi*1000*t)];

% A/B: localized sinusoidal residual peaks follow their expected bins.
lowResidual = [sin(2*pi*(20*fs/1024)*t), sin(2*pi*(20*fs/1024)*t)];
low = compute_frequency_error_profile(reference, lowResidual, fs);
[~, lowPeak] = max(low.residual_power);
assert(lowPeak - 1 == 20);
highResidual = [sin(2*pi*(300*fs/1024)*t), sin(2*pi*(300*fs/1024)*t)];
high = compute_frequency_error_profile(reference, highResidual, fs);
[~, highPeak] = max(high.residual_power);
assert(highPeak - 1 == 300 && highPeak > lowPeak);

% C: exact-zero residual is represented as -Inf, never floored.
zeroResult = compute_frequency_error_profile(reference, zeros(size(reference)), fs);
active = zeroResult.oracle_power > 0;
assert(all(zeroResult.residual_power == 0));
assert(all(isinf(zeroResult.relative_error_db(active)) & zeroResult.relative_error_db(active) < 0));
assert(all(zeroResult.metric_status(active) == "EXACT_ZERO_RESIDUAL"));

% D/I: delta is subtraction of pooled-power ratios, not mean dB.
conditionError = [2, 8]; conditionReference = [1, 4];
pooledQ = 10*log10(sum(conditionError)/sum(conditionReference));
meanQ = mean(10*log10(conditionError./conditionReference));
assert(abs(pooledQ - 10*log10(2)) < 1e-14);
assert(abs(pooledQ - meanQ) < 1e-14); % equal-ratio control
qColocated = 10*log10(1/4); qCondition = 10*log10(2/4);
assert(abs((qCondition-qColocated) - 10*log10(2)) < 1e-14);
unequalError = [1, 100]; unequalReference = [1, 1];
assert(abs(10*log10(sum(unequalError)/sum(unequalReference)) - ...
    mean(10*log10(unequalError./unequalReference))) > 1);

% E: exact band boundaries and exclusion above 20 kHz.
[bandIndex, ~] = assign_predefined_frequency_bands([0; 499; 500; 1999; 2000; 7999; 8000; 20000; 20001]);
assert(isequal(bandIndex.', [1, 1, 2, 2, 3, 3, 4, 4, 0]));

% F/G/H: exact ceil(20%), deterministic tie break, invariant reuse.
mixture = zeros(4096, 1);
maskA = compute_transient_mask(mixture, 4295, fs);
maskB = compute_transient_mask(mixture, 4295, fs);
assert(maskA.selected_frame_count == ceil(0.20*maskA.valid_frame_count));
expectedTieSelection = (2:(1+maskA.selected_frame_count)).';
assert(isequal(maskA.selected_frame_indices, expectedTieSelection));
assert(isequal(maskA.frame_class, maskB.frame_class));

% J: silent reference stays undefined while absolute error remains available.
silentReference = zeros(size(reference));
absoluteError = compute_frequency_error_profile(silentReference, lowResidual, fs);
assert(all(absoluteError.metric_status == "ZERO_REFERENCE_BIN"));
assert(all(isnan(absoluteError.relative_error_db)));
assert(any(absoluteError.residual_power > 0));

fprintf("PHASE2_9_SYNTHETIC_PASS bins=%d low_bin=%d high_bin=%d transient=%d/%d\n", ...
    numel(low.frequency_hz), lowPeak-1, highPeak-1, ...
    maskA.selected_frame_count, maskA.valid_frame_count);

function cues = compute_hrir_cues(leftHRIR, rightHRIR, sampleRate)
%COMPUTE_HRIR_CUES Compute broadband ITD and ILD from an HRIR pair.
%   MATLAB xcorr(hR,hL) gives a positive peak lag when hR is later than hL.
%   This project defines positive ITD as right-ear-earlier, hence the minus.

arguments
    leftHRIR {mustBeNumeric}
    rightHRIR {mustBeNumeric}
    sampleRate (1, 1) double {mustBeFinite, mustBePositive}
end

if ~isvector(leftHRIR) || ~isvector(rightHRIR) || isempty(leftHRIR) || isempty(rightHRIR)
    error("ELEC5305:HRTF:HRIRInput", "Left and right HRIRs must be nonempty vectors.");
end
leftHRIR = double(leftHRIR(:));
rightHRIR = double(rightHRIR(:));
if numel(leftHRIR) ~= numel(rightHRIR)
    error("ELEC5305:HRTF:HRIRLength", "Left and right HRIR lengths must match.");
end
if any(~isfinite(leftHRIR)) || any(~isfinite(rightHRIR))
    error("ELEC5305:HRTF:NonfiniteInput", "HRIR samples must all be finite.");
end

[correlation, lags] = xcorr(rightHRIR, leftHRIR);
[~, peakIndex] = max(abs(correlation));
xcorrLagSamples = lags(peakIndex);
itdSamples = -xcorrLagSamples;
leftRMS = sqrt(mean(leftHRIR .^ 2));
rightRMS = sqrt(mean(rightHRIR .^ 2));
ildDB = 20 * log10((rightRMS + eps) / (leftRMS + eps));

cues = struct();
cues.itd_samples = itdSamples;
cues.itd_us = itdSamples / sampleRate * 1e6;
cues.xcorr_hR_hL_peak_lag_samples = xcorrLagSamples;
cues.ild_db = ildDB;
cues.left_rms = leftRMS;
cues.right_rms = rightRMS;
cues.left_peak = max(abs(leftHRIR));
cues.right_peak = max(abs(rightHRIR));
end

function [stereo, diagnostics] = render_static_binaural(mono, leftHRIR, rightHRIR)
%RENDER_STATIC_BINAURAL Render a mono signal with transparent convolution.

arguments
    mono {mustBeNumeric}
    leftHRIR {mustBeNumeric}
    rightHRIR {mustBeNumeric}
end

if ~isvector(mono) || isempty(mono)
    error("ELEC5305:HRTF:MonoInput", "Input signal must be a nonempty mono vector.");
end
if ~isvector(leftHRIR) || ~isvector(rightHRIR) || isempty(leftHRIR) || isempty(rightHRIR)
    error("ELEC5305:HRTF:HRIRInput", "Left and right HRIRs must be nonempty vectors.");
end

mono = double(mono(:));
leftHRIR = double(leftHRIR(:));
rightHRIR = double(rightHRIR(:));
if any(~isfinite(mono)) || any(~isfinite(leftHRIR)) || any(~isfinite(rightHRIR))
    error("ELEC5305:HRTF:NonfiniteInput", "Signal and HRIR samples must all be finite.");
end
if numel(leftHRIR) ~= numel(rightHRIR)
    error("ELEC5305:HRTF:HRIRLength", "Left and right HRIR lengths must match.");
end

% Full linear convolution makes the expected N+L-1 output length explicit.
left = conv(mono, leftHRIR, "full");
right = conv(mono, rightHRIR, "full");
stereo = [left, right];
expectedLength = numel(mono) + numel(leftHRIR) - 1;
if size(stereo, 1) ~= expectedLength || size(stereo, 2) ~= 2
    error("ELEC5305:HRTF:OutputShape", "Unexpected binaural output shape.");
end
if any(~isfinite(stereo), "all")
    error("ELEC5305:HRTF:NonfiniteOutput", "Binaural output contains NaN or Inf.");
end

diagnostics = struct();
diagnostics.input_length = numel(mono);
diagnostics.hrir_length = numel(leftHRIR);
diagnostics.output_length = size(stereo, 1);
diagnostics.peak = max(abs(stereo), [], "all");
diagnostics.clipping_risk = diagnostics.peak > 1;
end

function mono = downmix_stereo_to_mono(stereo)
%DOWNMIX_STEREO_TO_MONO Apply the fixed Phase 2 oracle downmix equation.

arguments
    stereo {mustBeNumeric}
end

if isempty(stereo) || ~ismatrix(stereo) || size(stereo, 2) ~= 2
    error("ELEC5305:Oracle:StereoInput", ...
        "Input must be a nonempty frames-by-2 stereo array.");
end
stereo = double(stereo);
if any(~isfinite(stereo), "all")
    error("ELEC5305:Oracle:NonfiniteInput", "Stereo input contains NaN or Inf.");
end

mono = 0.5 * (stereo(:, 1) + stereo(:, 2));
if any(~isfinite(mono))
    error("ELEC5305:Oracle:NonfiniteOutput", "Mono downmix contains NaN or Inf.");
end
end

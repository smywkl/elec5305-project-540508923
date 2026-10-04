function [bandIndex, bandNames] = assign_predefined_frequency_bands(frequencyHz)
%ASSIGN_PREDEFINED_FREQUENCY_BANDS Fixed Phase 2.9 descriptive bands.

arguments
    frequencyHz (:, 1) double {mustBeFinite, mustBeNonnegative}
end
bandNames = ["0-500 Hz", "500-2000 Hz", "2000-8000 Hz", "8000-20000 Hz"];
bandIndex = zeros(size(frequencyHz));
bandIndex(frequencyHz >= 0 & frequencyHz < 500) = 1;
bandIndex(frequencyHz >= 500 & frequencyHz < 2000) = 2;
bandIndex(frequencyHz >= 2000 & frequencyHz < 8000) = 3;
bandIndex(frequencyHz >= 8000 & frequencyHz <= 20000) = 4;
end

function match = find_hrir_direction(subject, requestedAzimuthDeg, requestedElevationDeg)
%FIND_HRIR_DIRECTION Select the nearest measured HRIR without interpolation.
%   Project azimuth is positive to the listener's right. SOFA spherical
%   azimuth is positive from +x toward +y (the listener's left), so the
%   requested project azimuth is negated before metadata-based matching.

arguments
    subject (1, 1) struct
    requestedAzimuthDeg (1, 1) double {mustBeFinite}
    requestedElevationDeg (1, 1) double {mustBeFinite}
end

requiredFields = ["hrir", "source_positions", "receiver_order"];
for fieldName = requiredFields
    if ~isfield(subject, fieldName)
        error("ELEC5305:HRTF:InvalidSubject", "Subject is missing field '%s'.", fieldName);
    end
end
if ~isequal(string(subject.receiver_order), ["left", "right"])
    error("ELEC5305:HRTF:ReceiverOrder", "Expected HRIR receiver order [left, right].");
end

positions = double(subject.source_positions);
sofaRequestedAzimuth = mod(-requestedAzimuthDeg, 360);

% Unit-vector angular distance avoids wrap-around errors at 0/360 degrees.
requestedVector = direction_vector(sofaRequestedAzimuth, requestedElevationDeg);
measurementVectors = direction_vector(positions(:, 1), positions(:, 2));
metadataToleranceDeg = 1e-9;
exactCandidates = find(abs(wrap_to_180(positions(:, 1) - sofaRequestedAzimuth)) <= metadataToleranceDeg & ...
    abs(positions(:, 2) - requestedElevationDeg) <= metadataToleranceDeg);
if ~isempty(exactCandidates)
    measurementIndex = exactCandidates(1);
    angularMismatchDeg = 0;
else
    cosineDistance = measurementVectors * requestedVector.';
    cosineDistance = max(-1, min(1, cosineDistance));
    angularDistances = acosd(cosineDistance);
    [angularMismatchDeg, measurementIndex] = min(angularDistances);
end

actualSofaAzimuth = positions(measurementIndex, 1);
actualElevation = positions(measurementIndex, 2);
actualProjectAzimuth = wrap_to_180(-actualSofaAzimuth);
leftHRIR = reshape(subject.hrir(measurementIndex, 1, :), [], 1);
rightHRIR = reshape(subject.hrir(measurementIndex, 2, :), [], 1);

match = struct();
match.requested_azimuth_deg = requestedAzimuthDeg;
match.requested_elevation_deg = requestedElevationDeg;
match.measurement_index = measurementIndex;
match.actual_azimuth_deg = actualProjectAzimuth;
match.actual_elevation_deg = actualElevation;
match.actual_distance_m = positions(measurementIndex, 3);
match.sofa_azimuth_deg = actualSofaAzimuth;
match.angular_mismatch_deg = angularMismatchDeg;
match.exact_match = angularMismatchDeg == 0;
match.left_hrir = leftHRIR;
match.right_hrir = rightHRIR;
end

function vectors = direction_vector(azimuthDeg, elevationDeg)
cosElevation = cosd(elevationDeg);
vectors = [cosElevation .* cosd(azimuthDeg), ...
    cosElevation .* sind(azimuthDeg), sind(elevationDeg)];
end

function angleDeg = wrap_to_180(angleDeg)
angleDeg = mod(angleDeg + 180, 360) - 180;
end

function subject = load_cipic_subject(sofaPath)
%LOAD_CIPIC_SUBJECT Read and validate one CIPIC SimpleFreeFieldHRIR file.
%   SUBJECT = LOAD_CIPIC_SUBJECT(SOFAPATH) uses MATLAB's SOFA parser only
%   for file interpretation. Rendering and cue calculations remain in
%   project-owned functions.

arguments
    sofaPath (1, 1) string
end

if ~isfile(sofaPath)
    error("ELEC5305:HRTF:FileNotFound", "SOFA file not found: %s", sofaPath);
end

sofa = sofaread(sofaPath);
hrir = double(sofa.Numerator);
sourcePositions = double(sofa.SourcePosition);
receiverPositions = double(sofa.ReceiverPosition);
fs = double(sofa.SamplingRate);
delay = double(sofa.Delay);

if ndims(hrir) ~= 3 || size(hrir, 2) ~= 2
    error("ELEC5305:HRTF:InvalidHRIRShape", ...
        "Expected an M-by-2-by-N HRIR array; received %s.", mat2str(size(hrir)));
end
if isempty(hrir) || any(~isfinite(hrir), "all")
    error("ELEC5305:HRTF:InvalidHRIRValues", "HRIR data must be nonempty and finite.");
end
if ~isscalar(fs) || ~isfinite(fs) || fs <= 0
    error("ELEC5305:HRTF:InvalidSampleRate", "Sampling rate must be a positive finite scalar.");
end
if size(sourcePositions, 1) ~= size(hrir, 1) || size(sourcePositions, 2) < 3
    error("ELEC5305:HRTF:InvalidSourcePositions", ...
        "SourcePosition must have one three-coordinate row per measurement.");
end
if any(~isfinite(sourcePositions), "all")
    error("ELEC5305:HRTF:InvalidSourcePositions", "SourcePosition contains nonfinite values.");
end
if ~strcmpi(string(sofa.SourcePositionType), "spherical")
    error("ELEC5305:HRTF:UnsupportedCoordinates", ...
        "This experiment requires spherical SourcePosition metadata, not %s.", ...
        string(sofa.SourcePositionType));
end
if size(receiverPositions, 1) ~= 2 || size(receiverPositions, 2) ~= 3 || ...
        any(~isfinite(receiverPositions), "all")
    error("ELEC5305:HRTF:InvalidReceivers", ...
        "Expected two finite Cartesian receiver positions.");
end
if any(~isfinite(delay), "all")
    error("ELEC5305:HRTF:InvalidDelay", "SOFA delay metadata contains nonfinite values.");
end

% SOFA uses a listener-centred right-handed frame: +x forward, +y left,
% +z up. The CIPIC conversion places receiver 1 at +y and receiver 2 at
% -y, so the file order is [left, right]. Refuse an ambiguous/reversed file.
if ~(receiverPositions(1, 2) > 0 && receiverPositions(2, 2) < 0)
    error("ELEC5305:HRTF:ReceiverOrder", ...
        "Receiver positions do not establish the expected [left, right] ordering.");
end

subject = struct();
subject.sofa_path = char(sofaPath);
subject.fs = fs;
subject.hrir = hrir;
subject.source_positions = sourcePositions(:, 1:3);
subject.source_position_type = char(sofa.SourcePositionType);
subject.source_position_units = char(string(sofa.SourcePositionUnits));
subject.receiver_positions = receiverPositions;
subject.receiver_position_type = char(sofa.ReceiverPositionType);
subject.receiver_position_units = char(string(sofa.ReceiverPositionUnits));
subject.receiver_order = ["left", "right"];
subject.listener_view = double(sofa.ListenerView);
subject.listener_up = double(sofa.ListenerUp);
subject.delay = delay;
subject.delay_interpretation = "Data.Delay in samples; zero for both receivers in subject_003";
subject.sofa_convention = char(string(sofa.SOFAConventions));
subject.sofa_convention_version = char(string(sofa.SOFAConventionsVersion));
subject.data_type = char(string(sofa.DataType));
subject.database_name = char(string(sofa.DatabaseName));
subject.listener_short_name = char(string(sofa.ListenerShortName));
subject.title = char(string(sofa.Title));
subject.origin = char(string(sofa.Origin));
subject.date_created = char(string(sofa.DateCreated));
subject.date_modified = char(string(sofa.DateModified));
end

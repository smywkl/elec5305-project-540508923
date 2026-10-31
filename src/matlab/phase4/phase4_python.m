function executable=phase4_python()
%PHASE4_PYTHON Resolve the existing Python runtime without machine-specific paths.
executable=getenv('ELEC5305_PYTHON');
if ~isempty(executable)
    assert(isfile(executable),'ELEC5305:Import:Python', ...
        'ELEC5305_PYTHON must name an existing Python executable.');
    return;
end
prefix=getenv('CONDA_PREFIX');
if ~isempty(prefix)
    executable=fullfile(prefix,'python.exe');
    if isfile(executable), return; end
end
[status,locations]=system('where python');
if status==0
    candidates=splitlines(strtrim(locations));
    for k=1:numel(candidates)
        if isfile(candidates{k}), executable=candidates{k}; return; end
    end
end
error('ELEC5305:Import:Python', ...
    'Set ELEC5305_PYTHON or PythonExecutable to the existing elec5305 Python.');
end

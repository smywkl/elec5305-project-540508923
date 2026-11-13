function executable=phase4_python(explicit)
%PHASE4_PYTHON Prefer the project environment over an unrelated PATH Python.
arguments
    explicit (1,:) char = ''
end
if isempty(explicit), explicit=getenv('ELEC5305_PYTHON'); end
if ~isempty(explicit)
    candidates={explicit};
else
    candidates={};
    prefix=getenv('CONDA_PREFIX');
    conda=getenv('CONDA_EXE');
    pathPython=where_executable('python');
    condaPaths=[{conda}; where_executable('conda'); pathPython];
    for k=1:numel(condaPaths)
        if isempty(condaPaths{k}), continue; end
        folder=fileparts(condaPaths{k});
        candidates=[candidates; {fullfile(folder,'envs','elec5305','python.exe'); ...
            fullfile(fileparts(folder),'envs','elec5305','python.exe')}]; %#ok<AGROW>
    end
    if ~isempty(prefix)
        candidates=[{fullfile(prefix,'python.exe')}; candidates];
    end
    candidates=unique([candidates; pathPython],'stable');
end

failures={};
for k=1:numel(candidates)
    executable=candidates{k};
    if ~isfile(executable), continue; end
    psi=System.Diagnostics.ProcessStartInfo;
    psi.FileName=executable;
    psi.Arguments='-B -c "import demucs.apply, numpy, soundfile, torch, torchaudio, safetensors, yaml"';
    psi.UseShellExecute=false;
    psi.CreateNoWindow=true;
    psi.RedirectStandardError=true;
    try
        process=System.Diagnostics.Process.Start(psi);
        cleanup=onCleanup(@() process.Dispose());
        diagnostic=strtrim(char(process.StandardError.ReadToEnd()));
        process.WaitForExit();
        code=process.ExitCode;
        clear cleanup;
        if code==0
            fprintf('PHASE4_PYTHON %s\n',executable);
            return;
        end
        failures{end+1}=sprintf('%s (exit %d)\n%s',executable,code,diagnostic); %#ok<AGROW>
    catch ME
        clear cleanup;
        failures{end+1}=sprintf('%s: %s',executable,ME.message); %#ok<AGROW>
    end
end
if ~isempty(explicit) && ~isfile(explicit), failures={['File not found: ' explicit]}; end
error('ELEC5305:Import:Python', ...
    ['No usable Python environment. Set PythonExecutable or ELEC5305_PYTHON to the ' ...
    'project Python with PyTorch and Demucs.\n%s'],strjoin(failures,newline));
end

function paths=where_executable(name)
[status,locations]=system(['where ' name ' 2>NUL']);
paths=cell(0,1);
if status==0, paths=splitlines(strtrim(locations)); end
end

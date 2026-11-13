function launch_spatial_studio(options)
%LAUNCH_SPATIAL_STUDIO Start Spatial Studio from the MATLAB Command Window.
arguments
    options.PythonExecutable (1,:) char = ''
    options.Driver (1,:) char = 'auto'
    options.Device (1,:) char = ''
end
root=fileparts(mfilename('fullpath'));
oldPath=path;
cleanup=onCleanup(@() path(oldPath)); %#ok<NASGU>
addpath(fullfile(root,'scripts','matlab','phase4'));
phase4_music('PythonExecutable',options.PythonExecutable, ...
    'Driver',options.Driver,'Device',options.Device);
end

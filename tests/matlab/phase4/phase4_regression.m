function phase4_regression(outputDir)
%PHASE4_REGRESSION Run independent offline checks with existing validated caches.
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
oldPath=path; cleanup=onCleanup(@() path(oldPath)); %#ok<NASGU>
addpath(fileparts(mfilename('fullpath')),fullfile(root,'src','matlab','phase4'));
checks={@phase4_validate,@phase4_four_validate,@phase4_studio_validate, ...
    @phase4_motion_validate,@phase4_export_validate};
names={'single','four','studio','motion','export'};
for k=1:numel(checks)
    checks{k}(fullfile(outputDir,names{k}));
end
fprintf('PHASE4_OFFLINE_REGRESSION_PASS\n');
end

function phase4_music(varargin)
%PHASE4_MUSIC Start Spatial Studio independently of the initial working directory.
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
oldPath=path; cleanup=onCleanup(@() path(oldPath)); %#ok<NASGU>
addpath(fullfile(root,'src','matlab','phase4'));
phase4_four_realtime('CustomMusic',true,varargin{:});
end

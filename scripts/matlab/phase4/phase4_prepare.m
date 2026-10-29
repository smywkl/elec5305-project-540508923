function data = phase4_prepare()
%PHASE4_PREPARE All disk access, provenance checks and HRIR selection precede playback.
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
old=path; cleanup=onCleanup(@() path(old)); %#ok<NASGU>
for folder=["hrtf","oracle","comparison"]
    addpath(fullfile(root,'src','matlab','phase2',folder));
end
data.fs=44100;
data.subject=load_cipic_subject(fullfile(root,'data','hrtf','cipic','subject_003.sofa'));
assert(data.subject.fs==data.fs && all(data.subject.delay==0,'all'));
% Use the existing development-track cache; never perform inference.
track="Swinging Steaks - Lost My Way";
base=fullfile(root,'outputs','evaluation','source_separation_comparison','G_pretrained_HTDemucs_FT');
estimate=load_estimated_excerpt(fullfile(base,'listening',track), ...
    fullfile(base,'song_results',track,'result.json'),fullfile(base,'metadata.json'), ...
    fullfile(root,'data','musdb18hq','train',track,'mixture.wav'),track,30,12,data.fs);
data.mono=estimate.mono.vocals;
data.input=struct('track',track,'stem','vocals','start_seconds',30,'duration_seconds',12, ...
    'path',estimate.source_paths.vocals,'model','pretrained HTDemucs-FT', ...
    'fingerprint',estimate.phase1_metadata.configuration_fingerprint, ...
    'input_peak',max(abs(data.mono)),'frames',numel(data.mono), ...
    'cache_sha256',estimate.phase1_result.listening_outputs.vocals.sha256);
% Discover the actual measured front horizontal grid, then require exact lookup.
p=data.subject.source_positions;
a=mod(-p(:,1)+180,360)-180;
data.angles=sort(unique(a(abs(p(:,2))<1e-9 & abs(a)<=80+1e-9))).';
L=size(data.subject.hrir,3); data.bank=zeros(L,2,numel(data.angles));
for k=1:numel(data.angles)
    m=find_hrir_direction(data.subject,data.angles(k),0);
    assert(m.exact_match && abs(m.actual_elevation_deg)<1e-9);
    data.bank(:,:,k)=[m.left_hrir,m.right_hrir];
end
assert(data.angles(1)==-80 && data.angles(end)==80 && any(data.angles==0));
% One fixed gain for every direction. L1 bound also covers convex crossfades.
bound=max(sum(abs(data.bank),1),[],'all')*max(abs(data.mono));
data.gain=min(0.25,0.5/max(bound,eps));
% Fade excerpt endpoints before repeated playback, without changing source files.
n=round(.02*data.fs); envelope=(0:n-1)'/(n-1);
data.mono(1:n)=data.mono(1:n).*envelope;
data.mono(end-n+1:end)=data.mono(end-n+1:end).*flipud(envelope);
data.mono=data.gain*data.mono;
data.fade_samples=n; data.root=root;
end

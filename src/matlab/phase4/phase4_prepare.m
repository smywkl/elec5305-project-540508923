function data = phase4_prepare(mode)
%PHASE4_PREPARE All disk access, provenance checks and HRIR selection precede playback.
arguments
    mode (1,:) char {mustBeMember(mode,{'single','four','bank'})} = 'single'
end
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
old=path; cleanup=onCleanup(@() path(old)); %#ok<NASGU>
for folder=["hrtf","oracle","comparison"]
    addpath(fullfile(root,'src','matlab','phase2',folder));
end
data.fs=44100;
data.subject=load_cipic_subject(fullfile(root,'data','hrtf','cipic','subject_003.sofa'));
assert(data.subject.fs==data.fs && all(data.subject.delay==0,'all'));
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
data.fade_samples=round(.02*data.fs); data.root=root;
if strcmp(mode,'bank'), return; end
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
% One fixed gain for every direction. L1 bound also covers convex crossfades.
bound=max(sum(abs(data.bank),1),[],'all')*max(abs(data.mono));
data.gain=min(0.25,0.5/max(bound,eps));
% Fade excerpt endpoints before repeated playback, without changing source files.
n=round(.02*data.fs); envelope=(0:n-1)'/(n-1);
data.mono(1:n)=data.mono(1:n).*envelope;
data.mono(end-n+1:end)=data.mono(end-n+1:end).*flipud(envelope);
data.mono=data.gain*data.mono;
data.fade_samples=n; data.root=root;
if strcmp(mode,'four')
    data.stem_names={'vocals','drums','bass','other'};
    data.stems=zeros(estimate.frame_count,4);
    inputs=repmat(data.input,1,4);
    for s=1:4
        name=data.stem_names{s}; x=estimate.mono.(name);
        assert(numel(x)==estimate.frame_count && all(isfinite(x)));
        inputs(s).stem=name; inputs(s).path=estimate.source_paths.(name);
        inputs(s).cache_sha256=estimate.phase1_result.listening_outputs.(name).sha256;
        inputs(s).input_peak=max(abs(x));
        x(1:n)=x(1:n).*envelope;
        x(end-n+1:end)=x(end-n+1:end).*flipud(envelope);
        data.stems(:,s)=x;
    end
    % Sum of per-source worst-case bounds covers every direction, gate and fade.
    data.mix_bound_before_gain=max(sum(abs(data.bank),1),[],'all')*sum([inputs.input_peak]);
    data.gain=min(.25,.5/max(data.mix_bound_before_gain,eps));
    data.input=inputs;
    data.alignment=struct('sample_rate',estimate.sample_rate_hz,'frames',estimate.frame_count, ...
        'first_frame',estimate.start_frame_matlab_1_based, ...
        'last_frame',estimate.end_frame_matlab_1_based_inclusive, ...
        'full_track_frames',estimate.full_track_frames,'downmix','0.5*(left+right)', ...
        'resampling',false,'trimming',false);
end
end

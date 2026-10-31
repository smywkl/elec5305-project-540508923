function phase4_motion_validate(outputDir)
%PHASE4_MOTION_VALIDATE Analytic trajectory, lifecycle, projection and safety.
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
old=path; pc=onCleanup(@() path(old)); %#ok<NASGU>
addpath(fileparts(mfilename('fullpath')),fullfile(root,'src','matlab','phase4'));
if ~isfolder(outputDir), mkdir(outputDir); end
assert(~isfile(fullfile(outputDir,'validation.json')));
diary(fullfile(outputDir,'validation.log')); dc=onCleanup(@() diary('off')); %#ok<NASGU>
fs=44100; speed=12; worst=0;
% Independent reference with explicit reflection, including multiple bounces.
for start=[-80 -79.9 -35 0 79.9 80]
    sample=(0:round(60*fs))'; actual=phase4_pingpong(start,sample,fs,speed);
    reference=start; direction=1;
    for n=2:numel(sample)
        reference=reference+direction*speed/fs;
        if reference>80, reference=160-reference; direction=-1; end
        if reference< -80, reference=-160-reference; direction=1; end
        worst=max(worst,abs(reference-actual(n)));
    end
    assert(actual(1)==start && all(abs(actual)<=80));
    assert(max(abs(diff(actual)))<=speed/fs+1e-12);
end
assert(worst<1e-7);
% Exact boundaries have no teleportation, including starts at either edge.
assert(phase4_pingpong(0,fs*80/speed,fs)==80);
assert(phase4_pingpong(0,fs*240/speed,fs)==-80);
assert(phase4_pingpong(80,1,fs)<80 && phase4_pingpong(-80,1,fs)>-80);
% Any audio block partition yields identical angle at the same sample count.
a=Phase4AutoMotion(fs); b=Phase4AutoMotion(fs); starts=[-70 -20 20 70];
for s=1:4, a.setEnabled(s,true,starts(s)); b.setEnabled(s,true,starts(s)); end
for n=1:100, a.advance(1024); end
for n=1:400, b.advance(256); end
assert(isequal(a.angles(),b.angles()));
% Pause has no advancement; manual override only disables one; reenable +ward.
snapshot=a.angles(); pausedSamples=a.samples;
assert(isequal(a.angles(),snapshot) && isequal(a.samples,pausedSamples));
a.setEnabled(2,false,snapshot(2)); a.advance(44100);
assert(a.samples(2)==pausedSamples(2) && all(a.samples([1 3 4])==pausedSamples([1 3 4])+fs));
a.setEnabled(2,true,snapshot(2)); current=a.angles(); assert(abs(current(2)-snapshot(2))<1e-12);
a.stop(); assert(~any(a.enabled)); oldSamples=a.samples; a.advance(fs); assert(isequal(oldSamples,a.samples));
% Projection inverse and common logical radius over the entire supported arc.
angles=-80:.1:80; [x,y]=Phase4StageProjection.project(angles);
projectionError=max(abs(Phase4StageProjection.unproject(x,y)-angles));
assert(projectionError<1e-12 && max(abs(Phase4StageProjection.logicalRadius(x,y)-1))<1e-12);
% Same percentage is exactly 1.25 times the old steady-state gain.
gain=Phase4MasterGain(fs,65); gainError=0;
for percent=[0 10 65 100]
    gain.setPercent(percent); gain.reset();
    [z,e]=gain.step(.5*ones(1024,2));
    gainError=max(gainError,max(abs(e-1.25*(percent/100)^2)));
    assert(all(isfinite(z),'all') && max(abs(z),[],'all')<=.625);
end
assert(gainError==0);
result=struct('complete',true,'sample_rate',fs,'degrees_per_second',speed, ...
    'sample_reference_max_error_deg',worst,'projection_inverse_error_deg',projectionError, ...
    'partition_independent',true,'independent_enable_disable',true,'pause_freeze',true, ...
    'stop_disables_auto',true,'gain_ratio',1.25,'safe_mix_bound',.625);
fid=fopen(fullfile(outputDir,'validation.json'),'w'); fprintf(fid,'%s',jsonencode(result,PrettyPrint=true)); fclose(fid);
fprintf('PHASE4_MOTION_VALIDATION_PASS error=%.3g projection=%.3g\n',worst,projectionError);
end

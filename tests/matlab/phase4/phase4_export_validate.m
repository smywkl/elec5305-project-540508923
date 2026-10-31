function phase4_export_validate(outputDir)
%PHASE4_EXPORT_VALIDATE Cache-only full-song and independent static references.
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
old=path; pc=onCleanup(@() path(old)); %#ok<NASGU>
addpath(fileparts(mfilename('fullpath')),fullfile(root,'src','matlab','phase4'));
if ~isfolder(outputDir), mkdir(outputDir); end
assert(~isfile(fullfile(outputDir,'validation.json')));
diary(fullfile(outputDir,'validation.log')); dc=onCleanup(@() diary('off')); %#ok<NASGU>
for name={'Phase4WavExport','Phase4StudioView','phase4_four_realtime','phase4_export_validate'}
    messages=checkcode(which(name{1}),'-id'); assert(~any(strcmp({messages.id},'PARSE')));
end
% Select an existing complete full-song cache, never launch Python/inference.
files=dir(fullfile(root,'outputs','phase4','user_music_cache','*','attempt_*','completion.json'));
frames=zeros(size(files));
for k=1:numel(files)
    r=jsondecode(fileread(fullfile(files(k).folder,files(k).name))); frames(k)=r.frames;
end
[~,idx]=max(frames); assert(~isempty(idx) && frames(idx)>12*44100,'A complete full-song user cache is required.');
cache=files(idx).folder; r=jsondecode(fileread(fullfile(cache,'completion.json')));
result=struct('record',r,'cache_dir',cache,'cache_hit',true);
d=Phase4MusicImport.loadStems(phase4_prepare('bank'),result);
live=Phase4Mixer(d); master=Phase4MasterGain(d.fs,65); motion=Phase4AutoMotion(d.fs);
angles=[-63 -17 22 58];
for s=1:4, live.setTarget(s,angles(s)); motion.setEnabled(s,true,angles(s)); end
motion.advance(44100); live.reset(); live.step(d.stems(1:1024,:));
snapshot=Phase4WavExport.snapshot(live,master,motion); before=state(live,master,motion);
[audio,report]=Phase4WavExport.render(d,snapshot); assert(isequaln(before,state(live,master,motion)));
assert(isequal(snapshot.angles,angles) && all(snapshot.auto_enabled_at_click));
% Independent MATLAB filter() reference, not Phase4FIR/Mixer.
N=size(d.stems,1); reference=zeros(N,2);
for s=1:4
    x=d.stems(:,s); take=min(d.fade_samples,N); x(1:take)=x(1:take).*(1:take)'/d.fade_samples;
    [~,direction]=min(abs(d.angles-angles(s)));
    for ear=1:2
        reference(:,ear)=reference(:,ear)+d.gain*report.safety_gain*master.current*filter(d.bank(:,ear,direction),1,x);
    end
end
referenceError=max(abs(audio-reference),[],'all'); assert(referenceError<1e-12);
% Entire duration matches first-pass realtime core with the exact startup fade.
realtime=Phase4Mixer(d);
for s=1:4, realtime.setTarget(s,angles(s)); end
realtime.reset(); rtMaster=Phase4MasterGain(d.fs,65); realtimeError=0;
for first=1:1024:N
    last=min(first+1023,N); x=d.stems(first:last,:).*min((first:last)'/d.fade_samples,1);
    y=rtMaster.step(realtime.step(x));
    realtimeError=max(realtimeError,max(abs(y-audio(first:last,:)),[],'all'));
end
assert(realtimeError<1e-12 && report.safety_gain==1);
file=fullfile(outputDir,'cached_full_song_spatial.wav'); report=Phase4WavExport.write(file,audio,report);
assert(report.frames==r.frames && report.duration_seconds==r.frames/44100);
% Preserve live FIR histories/transitions/gates/volume/Auto across repeat renders.
[~,loudest]=max(sum(abs(d.stems),2)); first=max(1,min(N-4096,loudest-2048));
short=d; short.stems=d.stems(first:first+4096,:); settings=snapshot; routingError=0;
[base,~]=Phase4WavExport.render(short,settings);
for m=0:15
    for solo=0:15
        settings.muted=logical(bitget(m,1:4)); settings.solo=logical(bitget(solo,1:4));
        [y,meta]=Phase4WavExport.render(short,settings); ref=zeros(size(y));
        for s=find(meta.audible)
            x=short.stems(:,s).*min((1:size(y,1))'/short.fade_samples,1);
            [~,direction]=min(abs(short.angles-settings.angles(s)));
            for ear=1:2
                ref(:,ear)=ref(:,ear)+short.gain*master.current*filter(short.bank(:,ear,direction),1,x);
            end
        end
        routingError=max(routingError,max(abs(y-ref),[],'all'));
        if ~any(meta.audible), assert(all(y==0,'all')); end
    end
end
assert(routingError<1e-12 && isequaln(before,state(live,master,motion)));
settings=snapshot; settings.volume_percent=0; silent=Phase4WavExport.render(short,settings); assert(all(silent==0,'all'));
settings.volume_percent=100; loud=Phase4WavExport.render(short,settings);
assert(max(abs(loud-base/(.65^2)),[],'all')<1e-12);
% Check actual 4.3b signal against 4.3a's previous steady gain at 65%.
oldGain=.65^2; newGain=master.current;
sameMix=Phase4Mixer(short); sameMix.reset(); testMix=sameMix.step(short.stems(1:1024,:));
gainSignalError=max(abs(testMix*newGain-testMix*oldGain*1.25),[],'all');
assert(newGain==1.25*oldGain && gainSignalError<1e-15);
% Conservative common scaling for an intentionally hot offline-only input.
hot=short;
hotFactor=max(1000,10/(short.gain*max(sum(abs(short.bank),1),[],'all')*sum(max(abs(short.stems),[],1))));
hot.stems=short.stems*hotFactor;
[safe,safety]=Phase4WavExport.render(hot,snapshot);
assert(safety.safety_gain<1 && max(abs(safe),[],'all')<.98);
assert(max(abs(safe-base*(hotFactor*safety.safety_gain)),[],'all')<1e-12);
% Existing output is unchanged without explicit consent; invalid output recovers.
hash=Phase4MusicImport.sha256(file); rejected=false;
try, Phase4WavExport.write(file,audio,report); catch ME, rejected=strcmp(ME.identifier,'ELEC5305:Export:Exists'); end
assert(rejected && strcmp(hash,Phase4MusicImport.sha256(file)));
failed=false;
try, Phase4WavExport.write(fullfile(outputDir,'missing','bad.wav'),audio,report); catch ME, failed=strcmp(ME.identifier,'ELEC5305:Export:Directory'); end
assert(failed);
[repeat,~]=Phase4WavExport.render(short,snapshot);
assert(isequal(repeat,base) && isequaln(before,state(live,master,motion)));
% Snapshot remains fixed even after subsequent live angles and Auto advance.
motion.advance(44100); live.setTarget(1,80);
assert(isequal(snapshot.angles,angles));
result=struct('complete',true,'cache_dir',cache,'source_record',r, ...
    'full_song',report,'static_filter_reference_error',referenceError,'realtime_core_error',realtimeError, ...
    'mute_solo_cases',256,'routing_error',routingError,'all_muted_silent',true,'zero_volume_silent',true, ...
    'live_state_unchanged_across_exports',true,'auto_snapshot_static',true, ...
    'gain_audit',struct('old_65',oldGain,'current_65',newGain,'amplitude_ratio',newGain/oldGain, ...
    'change_db',20*log10(newGain/oldGain),'actual_signal_error',gainSignalError), ...
    'hot_input_safety_gain',safety.safety_gain,'overwrite_refused_without_consent',rejected, ...
    'failure_recovered',failed);
fid=fopen(fullfile(outputDir,'validation.json'),'w'); fprintf(fid,'%s',jsonencode(result,PrettyPrint=true)); fclose(fid);
fprintf('PHASE4_EXPORT_VALIDATION_PASS frames=%d seconds=%.6f peak=%.9g reference=%.3g realtime=%.3g\n', ...
    report.frames,report.duration_seconds,report.written_peak,referenceError,realtimeError);
end

function value=state(engine,master,motion)
value=struct('targets',engine.targets,'muted',engine.muted,'solo',engine.solo, ...
    'gate',engine.gate,'selected',engine.selectedAngles,'master_current',master.current, ...
    'master_percent',master.percent,'auto',motion.enabled,'origins',motion.origins,'samples',motion.samples);
for s=1:4
    e=engine.engines{s}; value.fir(s)=struct('history',e.history,'current',e.current, ...
        'target',e.target,'remaining',e.remaining,'index',e.index);
end
end

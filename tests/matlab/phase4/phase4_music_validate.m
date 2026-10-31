function phase4_music_validate(outputDir,fixtureDir)
%PHASE4_MUSIC_VALIDATE Engineering integration with tiny existing demo excerpts.
% Reuse existing fixtures/caches when supplied. No scientific results are written.
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
if nargin<2 || isempty(fixtureDir), fixtureDir=outputDir; end
old=path;
addpath(fileparts(mfilename('fullpath')),fullfile(root,'src','matlab','phase4'), ...
    fullfile(root,'scripts','matlab','phase4'));
job=Phase4MusicImport(root);
cleanup=onCleanup(@() cleanup_import(job,old)); %#ok<NASGU>
if ~isfolder(outputDir), mkdir(outputDir); end
assert(~isfile(fullfile(outputDir,'validation.json')),'Refusing to overwrite validation.');
for file={'phase4_four_realtime.m','phase4_prepare.m', ...
        fullfile(root,'src','matlab','phase4','Phase4MusicImport.m')}
    messages=checkcode(which(file{1}),'-id');
    assert(~any(strcmp({messages.id},'PARSE')),'MATLAB parse error.');
end
source=fullfile(root,'data','demo','test_song.wav');
[x,fs]=audioread(source,[1 110250]); % 2.5 s development excerpt, never a product limit.
wav=fullfile(fixtureDir,'自定义 mono 32k.wav');
mp3=fullfile(fixtureDir,'自定义 stereo 48k.mp3');
if strcmp(fixtureDir,outputDir)
    audiowrite(wav,resample(.7*mean(x,2),32000,fs),32000,'BitsPerSample',24);
    audiowrite(mp3,resample(.7*x(1:66150,:),48000,fs),48000);
else
    assert(isfile(wav) && isfile(mp3),'Expected existing development fixtures.');
end
bad=fullfile(outputDir,'broken.wav'); fid=fopen(bad,'w'); fprintf(fid,'not audio'); fclose(fid);
% Run real worker failure separately; then verify that the same UI importer can recover.
python=phase4_python();
failed=false;
try
    job.start(wav,fullfile(root,'does-not-exist-python.exe'));
catch ME
    failed=strcmp(ME.identifier,'ELEC5305:Import:Python');
end
assert(failed);
% Verify the product does not silently select the old 12 s excerpt.
job.start(source,python);
whole=jsondecode(fileread(fullfile(job.jobDir,'request.json'))); job.cancel();
assert(whole.preparation.prepared_frames==audioinfo(source).TotalSamples && ...
    whole.preparation.prepared_frames>12*44100);
% Near-full-scale resampling overshoot uses one common input gain, not clipping.
hot=fullfile(outputDir,'resample_overshoot.wav');
t=(0:31999)'/32000; audiowrite(hot,.99*sign(sin(2*pi*3000*t)),32000);
job.start(hot,python);
hotRequest=jsondecode(fileread(fullfile(job.jobDir,'request.json'))); job.cancel();
[hotAudio,hotFs]=audioread(hotRequest.prepared_path);
assert(hotFs==44100 && size(hotAudio,2)==2 && all(isfinite(hotAudio),'all') && ...
    max(abs(hotAudio),[],'all')<=1 && hotRequest.preparation.shared_input_gain<1);
% A valid Python executable with an intentionally invalid request exercises exit/log recovery.
jobs=fullfile(root,'outputs','phase4','import_jobs'); if ~isfolder(jobs), mkdir(jobs); end
failureDir=tempname(jobs); mkdir(failureDir);
request=fullfile(failureDir,'request.json'); fid=fopen(request,'w'); fprintf(fid,'{}'); fclose(fid);
job.launch(request,python);
timer=tic;
while true
    assert(toc(timer)<180,'Worker failure test timed out.'); pause(.1);
    try
        [done,~]=job.poll();
        assert(~done,'Invalid worker request unexpectedly succeeded.');
    catch ME
        workerFailed=strcmp(ME.identifier,'ELEC5305:Import:Worker');
        if ~workerFailed, rethrow(ME); end
        break;
    end
end
assert(workerFailed);
r=jsondecode(fileread(fullfile(failureDir,'result.json'))); assert(strcmp(r.status,'error'));
% The very same importer recovers from a nonzero worker exit.
job.start(wav,python); timer=tic;
while true
    assert(toc(timer)<600,'Recovery import timed out.'); pause(.1);
    [done,recovered]=job.poll(); if done, break; end
end
assert(strcmp(recovered.status,'complete'));
% File error -> WAV -> MP3 -> same WAV (cache), including replacement during playback.
phase4_music('OutputDir',fullfile(outputDir,'ui'), 'AutoTest',true, ...
    'ImportTestFiles',{bad,wav,mp3,wav},'ImportTestExpectedErrors',[true false false false]);
ui=jsondecode(fileread(fullfile(outputDir,'ui','summary.json')));
assert(ui.complete && numel(ui.imports)==3 && ui.imports(3).cache_hit);
assert(ui.imports(1).frames==110250 && ui.imports(2).frames>0);
assert(ui.expected_import_errors==1 && ui.sessions==3 && ui.device_releases==3);
result=struct('status','pass','sample_rate',44100,'order',{{'vocals','drums','bass','other'}}, ...
    'wav_input',audioinfo(wav),'mp3_input',audioinfo(mp3), ...
    'ui_summary',ui,'worker_failure_result',r,'missing_python_recovered',failed, ...
    'full_track_preparation_frames',whole.preparation.prepared_frames, ...
    'overshoot_shared_input_gain',hotRequest.preparation.shared_input_gain, ...
    'scope','Engineering integration; actual device playback, no subjective listening assertion');
fid=fopen(fullfile(outputDir,'validation.json'),'w');
fprintf(fid,'%s',jsonencode(result,PrettyPrint=true)); fclose(fid);
fprintf('PHASE4_MUSIC_VALIDATION_PASS\n');
delete(job); clear cleanup;
end

function cleanup_import(job,oldPath)
if isvalid(job), delete(job); end
path(oldPath);
end

function phase4_progress_validate(outputDir,showUI)
%PHASE4_PROGRESS_VALIDATE Actual first-time FT WAV/MP3 progress and cache hit.
if nargin<2, showUI=false; end
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
old=path; pc=onCleanup(@() path(old)); %#ok<NASGU>
addpath(fileparts(mfilename('fullpath')),fullfile(root,'scripts','matlab','phase4'), ...
    fullfile(root,'src','matlab','phase4'));
if ~isfolder(outputDir), mkdir(outputDir); end
assert(~isfile(fullfile(outputDir,'validation.json')));
[x,fs]=audioread(fullfile(root,'data','demo','test_song.wav'),[1 132300]);
wav=fullfile(outputDir,'progress_first.wav'); mp3=fullfile(outputDir,'progress_first.mp3');
[~,runName]=fileparts(outputDir);
audiowrite(wav,.613*x,fs,'BitsPerSample',24,'Title',['Progress test ' runName]);
audiowrite(mp3,.597*x(1:97020,:),fs,'Title',['Progress test ' runName]);
phase4_music('OutputDir',fullfile(outputDir,'ui'),'AutoTest',true,'ShowUI',showUI, ...
    'ImportTestFiles',{wav,mp3,wav},'ImportTestExpectedErrors',[false false false]);
ui=jsondecode(fileread(fullfile(outputDir,'ui','summary.json')));
assert(ui.complete && numel(ui.imports)==3 && ui.imports(3).cache_hit);
assert(~ui.imports(1).cache_hit && ~ui.imports(2).cache_hit);
assert(ui.import_progress.ui_updates>0 && ui.import_progress.determinate_updates>0 && ...
    ~ui.import_progress.visible_at_end);
counts=zeros(3,1);
for k=1:3
    lines=splitlines(strtrim(fileread(fullfile(ui.imports(k).progress_job,'progress_events.jsonl'))));
    percentages=[]; models=[];
    for n=1:numel(lines)
        state=jsondecode(lines{n});
        if isfield(state,'model')
            percentages(end+1)=state.percent; models(end+1)=state.model; %#ok<AGROW>
            assert(state.completed_segments<=state.segments);
        end
    end
    counts(k)=numel(percentages);
    if k<3
        assert(~isempty(percentages) && all(diff(percentages)>=0) && percentages(end)==100);
        assert(isequal(unique(models),1:4));
    else
        assert(isempty(percentages),'A cache hit must not report segment inference.');
    end
end
result=struct('complete',true,'wav_first_inference',true,'mp3_first_inference',true, ...
    'real_callback_records',counts,'cache_hit_has_no_inference',true,'ui_summary',ui);
fid=fopen(fullfile(outputDir,'validation.json'),'w'); fprintf(fid,'%s',jsonencode(result,PrettyPrint=true)); fclose(fid);
fprintf('PHASE4_PROGRESS_VALIDATION_PASS callbacks=%s\n',mat2str(counts'));
end

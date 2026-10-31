function phase2_regression(outputDir)
%PHASE2_REGRESSION Run the retained synthetic DSP tests without scientific reruns.
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
if ~isfolder(outputDir), mkdir(outputDir); end
oldPath=path; cleanup=onCleanup(@() path(oldPath)); %#ok<NASGU>
diary(fullfile(outputDir,'regression.log')); dc=onCleanup(@() diary('off')); %#ok<NASGU>
files=dir(fullfile(root,'tests','matlab','phase2','test_*.m'));
for k=1:numel(files)
    runIsolated(fullfile(files(k).folder,files(k).name));
end
records=struct('file',{},'id',{},'line',{},'message',{});
folders={'src','scripts','tests'};
checked=0;
for k=1:numel(folders)
    sources=dir(fullfile(root,folders{k},'**','*.m'));
    for j=1:numel(sources)
        file=fullfile(sources(j).folder,sources(j).name);
        messages=checkcode(file,'-id'); checked=checked+1;
        assert(~any(strcmp({messages.id},'PARSE')),'MATLAB parse error: %s',file);
        for n=1:numel(messages)
            records(end+1)=struct('file',file,'id',messages(n).id, ...
                'line',messages(n).line,'message',messages(n).message); %#ok<AGROW>
        end
    end
end
result=struct('status','PASS','synthetic_test_scripts',{ {files.name} }, ...
    'matlab_sources_checked',checked,'code_analyzer_messages',records, ...
    'scope','Synthetic regression and static parsing only; no frozen result writes or inference.');
fid=fopen(fullfile(outputDir,'validation.json'),'w');
fprintf(fid,'%s',jsonencode(result,PrettyPrint=true)); fclose(fid);
fprintf('PHASE2_SYNTHETIC_REGRESSION_PASS scripts=%d parsed=%d\n',numel(files),checked);
end

function runIsolated(file)
run(file);
end

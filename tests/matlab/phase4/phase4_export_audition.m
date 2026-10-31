function phase4_export_audition(outputDir,file)
%PHASE4_EXPORT_AUDITION Read back and send an unaltered 8 s excerpt to WASAPI.
if ~isfolder(outputDir), mkdir(outputDir); end
assert(~isfile(fullfile(outputDir,'audition.json')) && isfile(file));
diary(fullfile(outputDir,'audition.log')); dc=onCleanup(@() diary('off')); %#ok<NASGU>
meta=audioinfo(file); assert(meta.SampleRate==44100 && meta.NumChannels==2 && meta.BitsPerSample==24);
count=min(meta.TotalSamples,8*meta.SampleRate); [audio,fs]=audioread(file,[1 count]);
assert(all(isfinite(audio),'all') && max(abs(audio),[],'all')<1);
B=1024; writer=audioDeviceWriter('SampleRate',fs,'Driver','WASAPI','BufferSize',B);
cleanup=onCleanup(@() release(writer)); %#ok<NASGU>
setup(writer,zeros(B,2)); startup=0; underrun=0;
for k=1:8, startup=startup+double(writer(zeros(B,2))); end
device=info(writer);
for first=1:B:count
    last=min(first+B-1,count); y=zeros(B,2); y(1:last-first+1,:)=audio(first:last,:);
    underrun=underrun+double(writer(y));
end
for k=1:4, startup=startup+double(writer(zeros(B,2))); end
release(writer);
result=struct('complete',true,'output_file',file,'file_info',meta,'audition_frames',count, ...
    'audition_seconds',count/fs,'sample_rate',fs,'channel_order','left,right','device',device, ...
    'gain',1,'peak',max(abs(audio),[],'all'),'all_samples_finite',true, ...
    'underrun_samples',underrun,'startup_drain_underrun_samples',startup, ...
    'scope','Actual unaltered WAV device playback; subjective headphone judgement remains with the author.');
fid=fopen(fullfile(outputDir,'audition.json'),'w'); fprintf(fid,'%s',jsonencode(result,PrettyPrint=true)); fclose(fid);
fprintf('PHASE4_EXPORT_AUDITION_PASS seconds=%.6f peak=%.9g underrun=%d\n',count/fs,result.peak,underrun);
end

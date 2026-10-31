function phase4_four_realtime(options)
%PHASE4_FOUR_REALTIME Cached four-stem audition with one device and shared clock.
arguments
    options.OutputDir (1,:) char = ''
    options.FrameSize (1,1) double {mustBeMember(options.FrameSize,[256 512 1024])} = 1024
    options.Driver (1,:) char = 'WASAPI'
    options.Device (1,:) char = ''
    options.AutoTest (1,1) logical = false
    options.ShowUI (1,1) logical = false
    options.MotionTest (1,1) logical = false
    options.ExportTest (1,1) logical = false
    options.CustomMusic (1,1) logical = false
    options.PythonExecutable (1,:) char = ''
    options.ImportTestFiles cell = {}
    options.ImportTestExpectedErrors logical = false(1,0)
end
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
oldPath=path;
addpath(fileparts(mfilename('fullpath')),fullfile(root,'src','matlab','phase4'));
importer=Phase4MusicImport(root);
pathCleanup=onCleanup(@() cleanup_import(importer,oldPath)); %#ok<NASGU>
if isempty(options.OutputDir)
    options.OutputDir=fullfile(root,'outputs','phase4',char(datetime('now',Format='yyyyMMdd_HHmmss_SSS')));
end
out=options.OutputDir; if ~isfolder(out), mkdir(out); end
assert(~isfile(fullfile(out,'summary.json')),'Refusing to overwrite a completed run.');
diary(fullfile(out,'stream.log')); diaryCleanup=onCleanup(@() diary('off')); %#ok<NASGU>
if options.CustomMusic
    d=phase4_prepare('bank'); d.stems=zeros(1,4); d.gain=.25;
    d.input=struct(); d.alignment=struct(); d.mix_bound_before_gain=0;
    d.stem_names={'vocals','drums','bass','other'};
else
    d=phase4_prepare('four');
end
fs=d.fs; B=options.FrameSize; N=size(d.stems,1);
if isempty(options.PythonExecutable)
    if options.CustomMusic, options.PythonExecutable=phase4_python(); end
end
pendingFile=''; importing=false; readyMusic=~options.CustomMusic;
musicState='Ready'; songName='Phase 4.1b development excerpt'; lastError='';
if options.CustomMusic, songName='Choose a WAV or MP3 with Load Music'; musicState='Ready - no song'; end
imports=struct([]); importIndex=0; importPlayAt=Inf;
testAttempt=0; importErrors=0;
engine=Phase4Mixer(d);
w=audioDeviceWriter('SampleRate',fs,'Driver',options.Driver,'BufferSize',B);
if ~isempty(options.Device), w.Device=options.Device; end
writerCleanup=onCleanup(@() release(w)); %#ok<NASGU>
fprintf('PHASE4_FOUR_STREAM %s fs=%d B=%d gain=%.12g\n',version,fs,B,d.gain);
clock=tic; cursor=1; playing=false; paused=false; closing=false; ending=false;
stopKind=''; opened=false; fadeIn=0; fadeOut=0; tailLeft=0;
sessions=0; releases=0; startupUnderrun=0; totalUnderrun=0; deviceInfo=struct();
sequence=zeros(1,4); parameterTime=nan(1,4); appliedSequence=zeros(1,4);
rows=zeros(30000,34); row=0; events=zeros(10000,6); event=0;
lifecycle=zeros(1000,4); life=0; dirty=true; nextUI=0;
previousReturn=NaN; previousStart=NaN; previousOutput=zeros(1,2);
autoAction=0; autoMove=-1; autoControl=0; failure=[];
volumeEvents=zeros(10000,3); volumeEvent=0; volumeFrames=zeros(30000,3);
motion=Phase4AutoMotion(fs); motionFrames=zeros(30000,12);
importUIFrames=0; importUIRealFrames=0; importStart=NaN; nextImportUI=0;
testPauseSamples=[];
pendingExport=[]; exportBusy=false; exportRecords=struct([]); exportCount=0; nextExportUI=0;
exportTestAction=0; exportTestAt=Inf; exportOutcome='';
view=Phase4StudioView(~options.AutoTest || options.ShowUI,options.CustomMusic);
f=view.figure; uiCleanup=onCleanup(@() delete(view)); %#ok<NASGU>
master=Phase4MasterGain(fs,65);
view.onAngle=@setAngle; view.onControl=@setControl; view.onVolume=@setVolume; view.onAuto=@setAuto;
f.CloseRequestFcn=@(~,~) requestStop('close');
sliders=view.sliders; mutes=view.mutes; solos=view.solos;
playButton=view.playButton; pauseButton=view.pauseButton;
stopButton=view.stopButton; loadButton=view.loadButton;
playButton.ButtonPushedFcn=@(~,~) playNow();
pauseButton.ButtonPushedFcn=@(~,~) requestStop('pause');
stopButton.ButtonPushedFcn=@(~,~) requestStop('stop');
loadButton.ButtonPushedFcn=@(~,~) chooseMusic();
view.exportButton.ButtonPushedFcn=@(~,~) chooseExport();
refreshUI(); drawnow; pause(.1); drawnow;
% Whole-window exportapp can stall on dark desktop components in R2026a.
% Capture actual UI externally; no screenshot/export work in the audio loop.
appStart=toc(clock); wallStart=tic; cpuStart=cputime;
try
    while isvalid(f) && ~closing
        drawTick=tic; drawnow limitrate; drawSeconds=toc(drawTick);
        if closing, break; end
        if options.AutoTest && isempty(options.ImportTestFiles)
            if options.ExportTest, driveExportTest(toc(clock)-appStart);
            elseif options.MotionTest, driveMotionTest(toc(clock)-appStart); else, driveTest(toc(clock)-appStart); end
        end
        if ~isempty(pendingExport) && ~playing && ~opened
            performExport();
        end
        if ~isempty(pendingFile) && ~playing && ~opened
            file=pendingFile; pendingFile=''; readyMusic=false; paused=false; cursor=1;
            musicState='Loading'; importStart=toc(clock); dirty=true; refreshUI(); drawnow;
            try
                importer.start(file,options.PythonExecutable);
                songName=importer.songName; importing=true; musicState='Separating';
            catch ME
                importError(ME);
            end
            dirty=true;
        end
        if importing
            try
                [done,result]=importer.poll();
                if done
                    if ~isempty(options.ImportTestFiles)
                        assert(~options.ImportTestExpectedErrors(testAttempt),'Unexpected import success.');
                    end
                    d=Phase4MusicImport.loadStems(d,result); N=size(d.stems,1);
                    engine=Phase4Mixer(d); cursor=1; paused=false; ending=false;
                    stopKind=''; fadeIn=0; fadeOut=0; tailLeft=0;
                    motion=Phase4AutoMotion(fs);
                    sequence=zeros(1,4); appliedSequence=sequence; parameterTime=nan(1,4);
                    for k=1:4
                        sliders(k).Value=engine.targets(k); mutes(k).Value=false; solos(k).Value=false; view.autos(k).Value=false;
                    end
                    importing=false; readyMusic=true; musicState='Ready'; lastError='';
                    view.setImportProgress(false,struct());
                    importIndex=importIndex+1;
                    imports(importIndex).song=songName; imports(importIndex).cache_hit=result.cache_hit;
                    imports(importIndex).cache_dir=result.cache_dir; imports(importIndex).frames=N;
                    imports(importIndex).progress_job=importer.jobDir;
                    imports(importIndex).sample_rate=fs; imports(importIndex).cursor=cursor;
                    imports(importIndex).reset_controls=~any(engine.muted | engine.solo);
                    fprintf('IMPORT_READY %s frames=%d cache_hit=%d\n',songName,N,result.cache_hit);
                    dirty=true;
                    if ~isempty(options.ImportTestFiles), importPlayAt=toc(clock); playNow(); end
                end
            catch ME
                importError(ME);
            end
        end
        if ~isempty(options.ImportTestFiles), driveImportTest(); end
        if ~playing
            if importing && toc(clock)>=nextImportUI
                refreshUI(); nextImportUI=toc(clock)+.1;
            elseif dirty, refreshUI(); end
            pause(.005); continue;
        end
        if ~opened
            engine.reset(); refreshUI(); drawnow; pause(.05); drawnow;
            % Complete Play-state layout before starting the device clock.
            setup(w,zeros(B,2));
            for warm=1:ceil(.15*fs/B)
                engine.step(zeros(B,4)); startupUnderrun=startupUnderrun+double(w(zeros(B,2)));
            end
            engine.reset(); master.reset(); sessions=sessions+1; opened=true; fadeIn=d.fade_samples;
            ending=false; appliedSequence=sequence; previousOutput=zeros(1,2);
            previousReturn=NaN; previousStart=NaN;
            deviceInfo=info(w); fprintf('SESSION=%d DEVICE=%s\n',sessions,w.Device);
            recordLife(1); dirty=true; nextUI=toc(clock)+.1;
        end
        if ~isempty(stopKind) && ~ending
            ending=true; fadeOut=d.fade_samples; tailLeft=size(d.bank,1)-1;
        end
        tick=tic; t0=toc(clock); startCursor=cursor;
        x=zeros(B,4);
        if ~ending || fadeOut>0
            count=B; if ending, count=min(B,fadeOut); end
            indices=mod(cursor-1+(0:count-1),N)+1;
            x(1:count,:)=d.stems(indices,:); cursor=mod(cursor-1+count,N)+1;
            if ending
                x(1:count,:)=x(1:count,:).*max(0,(fadeOut-(1:count)')/d.fade_samples);
                fadeOut=fadeOut-count; tailLeft=tailLeft-(B-count);
            end
        else
            tailLeft=tailLeft-B;
        end
        if fadeIn>0 && ~ending
            count=min(B,fadeIn);
            x(1:count,:)=x(1:count,:).*(d.fade_samples-fadeIn+(1:count)')/d.fade_samples;
            fadeIn=fadeIn-count;
        end
        if ~ending
            autoAngles=motion.angles();
            for k=find(motion.enabled), setAngle(k,autoAngles(k),4); end
        end
        beforeAngles=engine.selectedAngles;
        y=master.step(engine.step(x)); dspSeconds=toc(tick); ready=toc(clock);
        if any(beforeAngles~=engine.selectedAngles), dirty=true; end
        latency=nan(1,4); changed=sequence~=appliedSequence;
        latency(changed)=1000*(ready-parameterTime(changed)); appliedSequence=sequence;
        writerTick=tic; underrun=double(w(y)); writerSeconds=toc(writerTick); returned=toc(clock);
        totalUnderrun=totalUnderrun+underrun;
        row=row+1;
        volumeFrames(row,:)=[master.percent,master.current,playing];
        motionFrames(row,:)=[motion.samples,engine.targets,motion.enabled];
        if ~ending, motion.advance(B); end
        rows(row,:)=[sessions,t0,startCursor,drawSeconds,dspSeconds,writerSeconds, ...
            t0-previousReturn,t0-previousStart,underrun,max(abs(y),[],'all'), ...
            max(abs(y(1,:)-previousOutput)),ending,engine.targets,engine.selectedAngles, ...
            sequence,latency,engine.audible(),sum(beforeAngles~=engine.selectedAngles),0];
        previousReturn=returned; previousStart=t0; previousOutput=y(end,:);
        if toc(clock)>=nextUI
            uiTick=tic; refreshUI(); rows(row,34)=toc(uiTick); nextUI=toc(clock)+.1;
        end
        if ending && fadeOut==0 && tailLeft<=0
            for drain=1:4, startupUnderrun=startupUnderrun+double(w(zeros(B,2))); end
            release(w); releases=releases+1; opened=false; playing=false;
            if strcmp(stopKind,'pause')
                paused=true; recordLife(2);
            else
                cursor=1; paused=false; recordLife(3);
            end
            closing=strcmp(stopKind,'close'); stopKind=''; dirty=true;
        end
    end
    if ~isempty(options.ImportTestFiles)
        assert(testAttempt==numel(options.ImportTestFiles) && ...
            importErrors==nnz(options.ImportTestExpectedErrors) && ...
            sessions==numel(imports) && releases==sessions && closing && cursor==1);
        assert(all([imports.reset_controls]) && all([imports.cursor]==1));
    end
    if options.AutoTest && isempty(options.ImportTestFiles) && ~options.ExportTest
        assert(autoAction==6 && sessions==3 && releases==3 && closing && cursor==1);
        assert(nnz(lifecycle(1:life,2)==2)==1 && nnz(lifecycle(1:life,2)==3)==2);
        if ~options.MotionTest, assert(all(sequence>20),'All four ValueChanging callbacks must run.'); end
    end
    if options.ExportTest
        assert(exportTestAction==10 && sessions==5 && releases==5 && closing);
        assert(isequal({exportRecords.status},{'complete','error','cancelled','complete'}));
    end
catch ME
    failure=ME; fprintf('STREAM_ERROR %s: %s\n',ME.identifier,ME.message);
end
release(w); if opened, releases=releases+1; end
base={'session','start_s','source_cursor','drawnow_s','dsp_s','writer_s','gap_after_writer_s', ...
    'start_interval_s','underrun_samples','peak','boundary_step','ending'};
namesCSV=[base,strcat('target_',d.stem_names),strcat('selected_',d.stem_names), ...
    strcat('sequence_',d.stem_names),strcat('callback_ready_ms_',d.stem_names), ...
    strcat('audible_',d.stem_names),{'directions_changed','ui_update_s'}];
tableFrames=array2table(rows(1:row,:),'VariableNames',namesCSV);
writetable(array2table(motionFrames(1:row,:),'VariableNames', ...
    [strcat('samples_',d.stem_names),strcat('angle_',d.stem_names),strcat('auto_',d.stem_names)]),fullfile(out,'motion_frames.csv'));
writetable(array2table(volumeFrames(1:row,:),'VariableNames', ...
    {'percent','applied_gain_end','playing'}),fullfile(out,'volume_frames.csv'));
writetable(array2table(volumeEvents(1:volumeEvent,:),'VariableNames', ...
    {'time_s','percent','playing'}),fullfile(out,'volume_events.csv'));
writetable(tableFrames,fullfile(out,'frames.csv'));
writetable(array2table(events(1:event,:),'VariableNames', ...
    {'time_s','kind_1_angle_2_mute_3_solo_4_auto','stem','value','sequence','source_1_changing_2_changed_3_drag'}), ...
    fullfile(out,'parameter_events.csv'));
writetable(array2table(lifecycle(1:life,:),'VariableNames', ...
    {'time_s','kind_1_open_2_pause_3_stop','session','cursor'}),fullfile(out,'lifecycle.csv'));
summary=struct('version',version,'timestamp',char(datetime('now',TimeZone='Australia/Sydney')), ...
    'sample_rate',fs,'frame_size',B,'frame_ms',1000*B/fs,'driver',options.Driver, ...
    'device',w.Device,'device_info',deviceInfo,'input',d.input,'alignment',d.alignment, ...
    'gain',d.gain,'conservative_mix_bound',d.gain*d.mix_bound_before_gain, ...
    'directions',d.angles,'hrir_samples',size(d.bank,1),'crossfade_samples',d.fade_samples, ...
    'underrun_samples',sum(tableFrames.underrun_samples), ...
    'underrun_events',nnz(tableFrames.underrun_samples), ...
    'startup_and_drain_underrun_samples',startupUnderrun,'sessions',sessions,'device_releases',releases, ...
    'rendered_frames',row*B,'channel_order','left,right','all_samples_finite',isempty(failure), ...
    'peak',max([0;tableFrames.peak]),'process_cpu_seconds',cputime-cpuStart, ...
    'wall_seconds',toc(wallStart),'auto_test',options.AutoTest, ...
    'ui_visible',~options.AutoTest || options.ShowUI,'complete',isempty(failure), ...
    'latency_scope','Callback to frame ready; excludes event queue, hardware buffers and acoustic latency.', ...
    'pause_policy','Fade out and release; resume cursor with reset history and fade in.');
summary.master_volume=struct('default_percent',65,'final_percent',master.percent, ...
    'mapping','1.25*(percent/100)^2','max_gain',master.maxGain,'full_scale_slew_ms',40, ...
    'events_while_playing',nnz(volumeEvents(1:volumeEvent,3)));
summary.spatial_ui=struct('radius',1,'limits',[-80 80], ...
    'axes_interactions_disabled',isempty(view.axes.Interactions), ...
    'toolbar_hidden',strcmp(view.axes.Toolbar.Visible,'off'), ...
    'final_targets',engine.targets,'axes_limits',[view.axes.XLim view.axes.YLim], ...
    'marker_radii',arrayfun(@(h) Phase4StageProjection.logicalRadius(h.XData,h.YData),view.markers), ...
    'projection_depth_scale',Phase4StageProjection.depthScale);
summary.auto_motion=struct('degrees_per_second',motion.speed,'enabled',motion.enabled, ...
    'samples',motion.samples,'clock','successfully written normal audio frames; excludes warmup/fade/drain', ...
    'stop_policy','disable all Auto, hold angles; re-enable starts here toward positive');
summary.import_progress=struct('ui_updates',importUIFrames,'determinate_updates',importUIRealFrames, ...
    'visible_at_end',strcmp(view.importTrack.Visible,'on'));
summary.exports=exportRecords;
summary.custom_music=options.CustomMusic; summary.imports=imports;
summary.last_import_error=lastError;
summary.expected_import_errors=importErrors;
for field={'drawnow_s','dsp_s','writer_s','gap_after_writer_s','start_interval_s','ui_update_s'}
    v=sort(tableFrames.(field{1})); v=v(isfinite(v));
    if ~isempty(v)
        summary.timing.(field{1})=struct('mean_ms',1000*mean(v), ...
            'p99_ms',1000*v(max(1,ceil(.99*numel(v)))),'max_ms',1000*max(v));
    end
end
fid=fopen(fullfile(out,'summary.json'),'w'); fprintf(fid,'%s',jsonencode(summary,PrettyPrint=true)); fclose(fid);
fprintf('PHASE4_FOUR_FINISHED frames=%d underrun_samples=%d peak=%.9g sessions=%d releases=%d\n', ...
    row,summary.underrun_samples,summary.peak,sessions,releases);
% UI callback closures can defer onCleanup destruction beyond the caller's
% path restoration. Break those references and delete the worker explicitly.
delete(view); delete(importer); clear uiCleanup pathCleanup;
if ~isempty(failure), rethrow(failure); end
if options.AutoTest
    fprintf('PHASE4_FOUR_UI_TEST_PASS\n');
end

    function setAngle(s,angle,source)
        if exportBusy, return; end
        if source~=4 && motion.enabled(s)
            motion.setEnabled(s,false,engine.targets(s)); view.autos(s).Value=false;
            recordEvent(4,s,0,source); dirty=true;
        end
        if engine.targets(s)==angle, return; end
        engine.setTarget(s,angle); dirty=true;
        if source~=4
            sequence(s)=sequence(s)+1; parameterTime(s)=toc(clock);
            recordEvent(1,s,angle,source);
        end
    end
    function setAuto(s,value)
        if exportBusy, return; end
        motion.setEnabled(s,value,engine.targets(s));
        view.autos(s).Value=motion.enabled(s); recordEvent(4,s,double(value),2); dirty=true;
    end
    function stopAuto()
        motion.stop();
        for k=1:4, view.autos(k).Value=false; end
        dirty=true;
    end
    function setVolume(value)
        if exportBusy, return; end
        master.setPercent(value); volumeEvent=volumeEvent+1;
        volumeEvents(volumeEvent,:)=[toc(clock),master.percent,playing];
    end
    function setControl(s,kind,value)
        if exportBusy, return; end
        if kind==1, engine.setMute(s,value); else, engine.setSolo(s,value); end
        recordEvent(kind+1,s,double(value),2); dirty=true;
    end
    function recordEvent(kind,s,value,source)
        event=event+1; events(event,:)=[toc(clock),kind,s,value,sequence(s),source];
    end
    function recordLife(kind)
        life=life+1; lifecycle(life,:)=[toc(clock),kind,sessions,cursor];
    end
    function playNow()
        if exportBusy || playing || ~readyMusic || importing || ~isempty(pendingFile), return; end
        if ~paused, cursor=1; end
        playing=true; stopKind=''; dirty=true;
    end
    function requestStop(kind)
        if exportBusy && ~playing && ~opened
            if strcmp(kind,'close'), closing=true; end
            return;
        end
        if ~strcmp(kind,'pause'), stopAuto(); end
        if playing
            % Closing must not be lost to a queued Pause/Stop callback.
            if ~strcmp(stopKind,'close'), stopKind=kind; end
        elseif strcmp(kind,'close')
            closing=true;
        elseif strcmp(kind,'stop')
            cursor=1; paused=false; dirty=true;
        end
    end
    function refreshUI()
        if dirty, view.updateAngles(engine.targets,engine.selectedAngles); end
        if playing, state='Playing'; elseif paused, state='Paused'; else, state='Stopped / ready'; end
        if options.CustomMusic && readyMusic && ~playing && ~paused, state='Ready'; end
        if ending && playing, state='Fading / releasing'; end
        if options.CustomMusic && (~readyMusic || importing || ~isempty(pendingFile)), state=musicState; end
        busy=importing || ~isempty(pendingFile) || strcmp(musicState,'Loading');
        if importing
            importState=importer.progress(); state=importState.stage;
        else
            importState=struct('stage','Loading audio','elapsed_seconds',max(0,toc(clock)-importStart), ...
                'indeterminate',true,'percent',NaN);
        end
        importState.elapsed_seconds=max(0,toc(clock)-importStart); % Includes decoding and worker startup.
        view.setImportProgress(busy,importState);
        if busy
            importUIFrames=importUIFrames+1;
            if ~importState.indeterminate, importUIRealFrames=importUIRealFrames+1; end
        end
        view.status.Text=state;
        view.status.Tooltip=sprintf('%d samples | underrun %d | %s',B,totalUnderrun,lastError);
        view.songLabel.Text=songName; view.songLabel.Tooltip=songName;
        view.setProgress((cursor-1)/max(1,N));
        view.timeLabel.Text=sprintf('%s / %s',formatTime((cursor-1)/fs),formatTime(N*readyMusic/fs));
        playButton.Enable=matlab.lang.OnOffSwitchState(~playing && readyMusic && ~importing && isempty(pendingFile));
        pauseButton.Enable=matlab.lang.OnOffSwitchState(playing);
        loadButton.Enable=matlab.lang.OnOffSwitchState(~importing && isempty(pendingFile));
        view.exportButton.Enable=matlab.lang.OnOffSwitchState(readyMusic && ~importing && isempty(pendingFile) && ~exportBusy);
        if exportBusy, view.setExportBusy(true); end
        dirty=false;
    end
    function chooseMusic()
        if exportBusy || importing || ~isempty(pendingFile), return; end
        [file,folder]=uigetfile({'*.wav;*.mp3','Music (*.wav, *.mp3)'},'Load Music');
        if isequal(file,0), return; end
        queueMusic(fullfile(folder,file));
    end
    function queueMusic(file)
        pendingFile=file; musicState='Loading'; dirty=true; lastError='';
        requestStop('import');
    end
    function importError(ME)
        importer.cancel(); importing=false; readyMusic=false; musicState='Error';
        view.setImportProgress(false,struct());
        lastError=ME.message; dirty=true;
        fprintf('IMPORT_ERROR %s: %s\n',ME.identifier,ME.message);
        if ~isempty(options.ImportTestFiles)
            assert(strcmp(view.importTrack.Visible,'off'),'Error must hide import progress.');
            assert(options.ImportTestExpectedErrors(testAttempt),'Unexpected import failure: %s',ME.message);
            importErrors=importErrors+1;
        end
    end
    function driveImportTest()
        if importing || ~isempty(pendingFile) || ~isempty(stopKind), return; end
        if testAttempt==0 || (~playing && ~readyMusic)
            nextTestImport();
        elseif playing && toc(clock)-importPlayAt>1.5
            view.volume(35+20*testAttempt);
            % Exercise controls with live audio, then import while playing.
            for k=1:4
                sliders(k).ValueChangingFcn(sliders(k),struct('Value',20*(-1)^k));
                mutes(k).Value=true; mutes(k).ValueChangedFcn(mutes(k),[]);
                solos(k).Value=true; solos(k).ValueChangedFcn(solos(k),[]);
            end
            if testAttempt<numel(options.ImportTestFiles)
                nextTestImport();
            else
                requestStop('close');
            end
        end
    end
    function nextTestImport()
        testAttempt=testAttempt+1;
        assert(testAttempt<=numel(options.ImportTestFiles),'Test must end with a valid import.');
        queueMusic(options.ImportTestFiles{testAttempt});
    end
    function chooseExport(testPath)
        if ~readyMusic || importing || ~isempty(pendingFile) || exportBusy, return; end
        if nargin<1, testPath='__native_dialog__'; end
        pendingExport=struct('settings',Phase4WavExport.snapshot(engine,master,motion), ...
            'request_time_s',toc(clock),'test_path',testPath,'song_name',songName);
        if playing, requestStop('pause'); end
        exportBusy=true; exportOutcome=''; view.setExportBusy(true);
        view.exportLabel.Text='Preparing export: playback pauses; Auto is frozen.';
        dirty=true;
    end
    function performExport()
        request=pendingExport; pendingExport=[];
        entry=struct('status','cancelled','snapshot',request.settings,'request_time_s',request.request_time_s, ...
            'output_path','','message','','report',struct());
        beforeTargets=engine.targets; beforeAuto=motion.enabled; beforeSamples=motion.samples;
        try
            overwrite=false;
            if strcmp(request.test_path,'__native_dialog__')
                [~,stemName]=fileparts(request.song_name);
                [file,folder]=uiputfile({'*.wav','24-bit stereo WAV (*.wav)'},'Export static binaural WAV', ...
                    [stemName '_spatial.wav']);
                if isequal(file,0), file=''; else
                    file=fullfile(folder,file);
                    if isfile(file)
                        % Require an explicit application decision as well as the
                        % native dialog. Existence alone never grants replacement.
                        answer=uiconfirm(f,['Replace existing WAV? ' file],'Confirm WAV replacement', ...
                            'Options',{'Replace','Cancel'},'DefaultOption',2,'CancelOption',2);
                        overwrite=strcmp(answer,'Replace');
                        if ~overwrite, file=''; end
                    end
                end
            else
                file=request.test_path; % Automated tests never open blocking dialogs.
            end
            if ~isempty(file)
                entry.output_path=file; nextExportUI=0;
                [audio,report]=Phase4WavExport.render(d,request.settings,@exportProgress);
                report=Phase4WavExport.write(file,audio,report,overwrite,@exportProgress);
                entry.status='complete'; entry.report=report;
                view.exportLabel.Text=['Export complete: ' file];
                view.exportLabel.Tooltip=sprintf('%s | 44.1 kHz / stereo / 24-bit | safety gain %.9g',file,report.safety_gain);
                fprintf('EXPORT_COMPLETE path=%s frames=%d peak=%.9g safety=%.9g\n',file,report.frames,report.written_peak,report.safety_gain);
            else
                view.exportLabel.Text='Export cancelled'; view.exportLabel.Tooltip='No output file created.';
            end
        catch ME
            if strcmp(ME.identifier,'ELEC5305:Export:Cancelled')
                entry.status='cancelled'; view.exportLabel.Text='Export cancelled';
            else
                entry.status='error'; entry.message=ME.message;
                view.exportLabel.Text=['Export failed: ' ME.message]; view.exportLabel.Tooltip=ME.message;
                fprintf('EXPORT_ERROR %s: %s\n',ME.identifier,ME.message);
            end
        end
        assert(isequal(engine.targets,beforeTargets) && isequal(motion.enabled,beforeAuto) && ...
            isequal(motion.samples,beforeSamples),'Export changed live angles/Auto clocks.');
        exportCount=exportCount+1;
        if exportCount==1, exportRecords=entry; else, exportRecords(exportCount)=entry; end
        exportOutcome=entry.status;
        fid=fopen(fullfile(out,'exports.json'),'w');
        if fid>=0, fprintf(fid,'%s',jsonencode(exportRecords,PrettyPrint=true)); fclose(fid); end
        exportBusy=false; view.setImportProgress(false,struct()); view.setExportBusy(false);
        % Resynchronize guarded/queued controls once, outside the audio clock.
        for k=1:4
            mutes(k).Value=engine.muted(k); solos(k).Value=engine.solo(k); view.autos(k).Value=motion.enabled(k);
        end
        view.volumeSlider.Value=master.percent; view.volumeLabel.Text=sprintf('%.0f%%',master.percent);
        dirty=true; refreshUI(); exportTestAt=toc(clock);
    end
    function exportProgress(fraction,stage)
        if toc(clock)>=nextExportUI || strcmp(stage,'Export complete')
            view.setExportProgress(fraction,stage); drawnow limitrate;
            nextExportUI=toc(clock)+.1;
        end
        if closing && ~strcmp(stage,'Export complete'), error('ELEC5305:Export:Cancelled','Application closed during export.'); end
    end
    function driveExportTest(t)
        if exportBusy, return; end
        switch exportTestAction
            case 0
                for k=1:4, setAuto(k,true); end
                playNow(); exportTestAction=1;
            case 1
                if t<3, return; end
                chooseExport(fullfile(out,'ui_static_1.wav')); exportTestAction=2;
            case 2
                assert(strcmp(exportOutcome,'complete') && paused);
                assert(isequal(exportRecords(1).snapshot.angles,engine.targets));
                playNow(); exportTestAction=3;
            case 3
                if toc(clock)-exportTestAt<2, return; end
                chooseExport(fullfile(out,'missing_folder','failure.wav')); exportTestAction=4;
            case 4
                assert(strcmp(exportOutcome,'error') && ~exportBusy); playNow(); exportTestAction=5;
            case 5
                if toc(clock)-exportTestAt<2, return; end
                chooseExport(''); exportTestAction=6;
            case 6
                assert(strcmp(exportOutcome,'cancelled')); playNow(); exportTestAction=7;
            case 7
                if toc(clock)-exportTestAt<2, return; end
                chooseExport(fullfile(out,'ui_static_2.wav')); exportTestAction=8;
            case 8
                assert(strcmp(exportOutcome,'complete')); playNow(); exportTestAction=9;
            case 9
                if toc(clock)-exportTestAt<2, return; end
                requestStop('close'); exportTestAction=10;
        end
    end
    function driveMotionTest(t)
        times=[0 14 15 28 29 57];
        if autoAction<numel(times) && t>=times(autoAction+1)
            autoAction=autoAction+1;
            switch autoAction
                case {1,3,5}
                    if autoAction==3, assert(isequal(motion.samples,testPauseSamples),'Pause advanced Auto clocks.'); end
                    if autoAction~=3
                        for k=1:4
                            if autoAction==1, a=[-70 -20 20 70]; setAngle(k,a(k),2); end
                            view.auto(k,true);
                        end
                    end
                    playNow();
                case 2, testPauseSamples=motion.samples; requestStop('pause');
                case 4, requestStop('stop');
                case 6, requestStop('close');
            end
        end
        step=floor(t/.2);
        if step~=autoMove
            autoMove=step; view.volume(65+35*sin(t*.4));
        end
        if autoControl==0 && t>5
            setAngle(2,engine.targets(2),3); assert(~motion.enabled(2)); autoControl=1;
        elseif autoControl==1 && t>6
            view.auto(2,true); autoControl=2;
        elseif autoControl==2 && t>8
            setControl(1,1,true); setControl(3,2,true); autoControl=3;
        elseif autoControl==3 && t>10
            setControl(1,1,false); setControl(3,2,false); autoControl=4;
        end
    end
    function driveTest(t)
        times=[0 10 11 20 21 38];
        if autoAction<numel(times) && t>=times(autoAction+1)
            autoAction=autoAction+1;
            switch autoAction
                case {1,3,5}, playButton.ButtonPushedFcn(playButton,[]);
                case 2, pauseButton.ButtonPushedFcn(pauseButton,[]);
                case 4, stopButton.ButtonPushedFcn(stopButton,[]);
                case 6, f.CloseRequestFcn(f,[]);
            end
        end
        step=floor(t/.04);
        if step~=autoMove
            autoMove=step;
            view.volume(50+50*sin(t*.7));
            for k=1:4
                if t<4, angle=engine.targets(k);
                elseif t<10, angle=75*sin((t-4)*.5+(k-1)*pi/2);
                elseif t<20, angle=(60+5*k)*(-1)^(step+k);
                else, angle=[-55 -20 20 55]; angle=angle(k); end
                sliders(k).Value=angle;
                sliders(k).ValueChangingFcn(sliders(k),struct('Value',angle));
            end
        end
        controlTimes=[3 5 7 12 14 16 18];
        if autoControl<numel(controlTimes) && t>=controlTimes(autoControl+1)
            autoControl=autoControl+1;
            switch autoControl
                case 1, mutes(2).Value=true; mutes(2).ValueChangedFcn(mutes(2),[]);
                case 2, solos(1).Value=true; solos(1).ValueChangedFcn(solos(1),[]);
                case 3, mutes(2).Value=false; mutes(2).ValueChangedFcn(mutes(2),[]);
                case 4, solos(3).Value=true; solos(3).ValueChangedFcn(solos(3),[]);
                case 5, mutes(1).Value=true; mutes(1).ValueChangedFcn(mutes(1),[]);
                case 6, solos(1).Value=false; solos(1).ValueChangedFcn(solos(1),[]);
                case 7
                    for k=1:4
                        mutes(k).Value=false; mutes(k).ValueChangedFcn(mutes(k),[]);
                        solos(k).Value=false; solos(k).ValueChangedFcn(solos(k),[]);
                    end
            end
        end
    end
end

function cleanup_import(importer,oldPath)
if isvalid(importer), delete(importer); end
path(oldPath);
end

function value=formatTime(seconds)
value=sprintf('%d:%02d',floor(seconds/60),floor(mod(seconds,60)));
end

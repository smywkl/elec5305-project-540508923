function phase4_four_realtime(options)
%PHASE4_FOUR_REALTIME Cached four-stem audition with one device and shared clock.
arguments
    options.OutputDir (1,:) char = ''
    options.FrameSize (1,1) double {mustBeMember(options.FrameSize,[256 512 1024])} = 1024
    options.Driver (1,:) char = 'WASAPI'
    options.Device (1,:) char = ''
    options.AutoTest (1,1) logical = false
    options.ShowUI (1,1) logical = false
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
    options.PythonExecutable=getenv('ELEC5305_PYTHON');
    if isempty(options.PythonExecutable)
        options.PythonExecutable=fullfile('D:','anaconda','envs','elec5305','python.exe');
    end
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
view=Phase4StudioView(~options.AutoTest || options.ShowUI,options.CustomMusic);
f=view.figure; uiCleanup=onCleanup(@() delete(view)); %#ok<NASGU>
master=Phase4MasterGain(fs,65);
view.onAngle=@setAngle; view.onControl=@setControl; view.onVolume=@setVolume;
f.CloseRequestFcn=@(~,~) requestStop('close');
sliders=view.sliders; mutes=view.mutes; solos=view.solos;
playButton=view.playButton; pauseButton=view.pauseButton;
stopButton=view.stopButton; loadButton=view.loadButton;
playButton.ButtonPushedFcn=@(~,~) playNow();
pauseButton.ButtonPushedFcn=@(~,~) requestStop('pause');
stopButton.ButtonPushedFcn=@(~,~) requestStop('stop');
loadButton.ButtonPushedFcn=@(~,~) chooseMusic();
refreshUI(); drawnow; pause(.1); drawnow;
% Whole-window exportapp can stall on dark desktop components in R2026a.
% Capture actual UI externally; no screenshot/export work in the audio loop.
appStart=toc(clock); wallStart=tic; cpuStart=cputime;
try
    while isvalid(f) && ~closing
        drawTick=tic; drawnow limitrate; drawSeconds=toc(drawTick);
        if closing, break; end
        if options.AutoTest && isempty(options.ImportTestFiles), driveTest(toc(clock)-appStart); end
        if ~isempty(pendingFile) && ~playing && ~opened
            file=pendingFile; pendingFile=''; readyMusic=false; paused=false; cursor=1;
            musicState='Loading'; dirty=true; refreshUI(); drawnow;
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
                    sequence=zeros(1,4); appliedSequence=sequence; parameterTime=nan(1,4);
                    for k=1:4
                        sliders(k).Value=engine.targets(k); mutes(k).Value=false; solos(k).Value=false;
                    end
                    importing=false; readyMusic=true; musicState='Ready'; lastError='';
                    importIndex=importIndex+1;
                    imports(importIndex).song=songName; imports(importIndex).cache_hit=result.cache_hit;
                    imports(importIndex).cache_dir=result.cache_dir; imports(importIndex).frames=N;
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
            if dirty, refreshUI(); end
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
        beforeAngles=engine.selectedAngles;
        y=master.step(engine.step(x)); dspSeconds=toc(tick); ready=toc(clock);
        if any(beforeAngles~=engine.selectedAngles), dirty=true; end
        latency=nan(1,4); changed=sequence~=appliedSequence;
        latency(changed)=1000*(ready-parameterTime(changed)); appliedSequence=sequence;
        writerTick=tic; underrun=double(w(y)); writerSeconds=toc(writerTick); returned=toc(clock);
        totalUnderrun=totalUnderrun+underrun;
        row=row+1;
        volumeFrames(row,:)=[master.percent,master.current,playing];
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
    if options.AutoTest && isempty(options.ImportTestFiles)
        assert(autoAction==6 && sessions==3 && releases==3 && closing && cursor==1);
        assert(nnz(lifecycle(1:life,2)==2)==1 && nnz(lifecycle(1:life,2)==3)==2);
        assert(all(sequence>20),'All four ValueChanging callbacks must run.');
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
writetable(array2table(volumeFrames(1:row,:),'VariableNames', ...
    {'percent','applied_gain_end','playing'}),fullfile(out,'volume_frames.csv'));
writetable(array2table(volumeEvents(1:volumeEvent,:),'VariableNames', ...
    {'time_s','percent','playing'}),fullfile(out,'volume_events.csv'));
writetable(tableFrames,fullfile(out,'frames.csv'));
writetable(array2table(events(1:event,:),'VariableNames', ...
    {'time_s','kind_1_angle_2_mute_3_solo','stem','value','sequence','source_1_changing_2_changed_3_drag'}), ...
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
    'mapping','(percent/100)^2','max_gain',1,'full_scale_slew_ms',40, ...
    'events_while_playing',nnz(volumeEvents(1:volumeEvent,3)));
summary.spatial_ui=struct('radius',1,'limits',[-80 80], ...
    'axes_interactions_disabled',isempty(view.axes.Interactions), ...
    'toolbar_hidden',strcmp(view.axes.Toolbar.Visible,'off'), ...
    'final_targets',engine.targets,'axes_limits',[view.axes.XLim view.axes.YLim], ...
    'marker_radii',arrayfun(@(h) hypot(h.XData,h.YData),view.markers));
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
        if engine.targets(s)==angle, return; end
        engine.setTarget(s,angle); sequence(s)=sequence(s)+1; parameterTime(s)=toc(clock);
        recordEvent(1,s,angle,source); dirty=true;
    end
    function setVolume(value)
        master.setPercent(value); volumeEvent=volumeEvent+1;
        volumeEvents(volumeEvent,:)=[toc(clock),master.percent,playing];
    end
    function setControl(s,kind,value)
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
        if playing || ~readyMusic || importing || ~isempty(pendingFile), return; end
        if ~paused, cursor=1; end
        playing=true; stopKind=''; dirty=true;
    end
    function requestStop(kind)
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
        if ending && playing, state='Fading / releasing'; end
        if options.CustomMusic && (~readyMusic || importing || ~isempty(pendingFile)), state=musicState; end
        view.status.Text=state;
        view.status.Tooltip=sprintf('%d samples | underrun %d | %s',B,totalUnderrun,lastError);
        view.songLabel.Text=songName; view.songLabel.Tooltip=songName;
        view.setProgress((cursor-1)/max(1,N));
        view.timeLabel.Text=sprintf('%s / %s',formatTime((cursor-1)/fs),formatTime(N*readyMusic/fs));
        playButton.Enable=matlab.lang.OnOffSwitchState(~playing && readyMusic && ~importing && isempty(pendingFile));
        pauseButton.Enable=matlab.lang.OnOffSwitchState(playing);
        loadButton.Enable=matlab.lang.OnOffSwitchState(~importing && isempty(pendingFile));
        dirty=false;
    end
    function chooseMusic()
        if importing || ~isempty(pendingFile), return; end
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
        lastError=ME.message; dirty=true;
        fprintf('IMPORT_ERROR %s: %s\n',ME.identifier,ME.message);
        if ~isempty(options.ImportTestFiles)
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

function delete_valid(f)
if isvalid(f), delete(f); end
end

function cleanup_import(importer,oldPath)
if isvalid(importer), delete(importer); end
path(oldPath);
end

function value=formatTime(seconds)
value=sprintf('%d:%02d',floor(seconds/60),floor(mod(seconds,60)));
end

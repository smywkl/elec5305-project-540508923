function phase4_four_realtime(options)
%PHASE4_FOUR_REALTIME Cached four-stem audition with one device and shared clock.
arguments
    options.OutputDir (1,:) char = ''
    options.FrameSize (1,1) double {mustBeMember(options.FrameSize,[256 512 1024])} = 1024
    options.Driver (1,:) char = 'WASAPI'
    options.Device (1,:) char = ''
    options.AutoTest (1,1) logical = false
    options.ShowUI (1,1) logical = false
end
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
oldPath=path; pathCleanup=onCleanup(@() path(oldPath)); %#ok<NASGU>
addpath(fileparts(mfilename('fullpath')),fullfile(root,'src','matlab','phase4'));
if isempty(options.OutputDir)
    options.OutputDir=fullfile(root,'outputs','phase4',char(datetime('now',Format='yyyyMMdd_HHmmss_SSS')));
end
out=options.OutputDir; if ~isfolder(out), mkdir(out); end
assert(~isfile(fullfile(out,'summary.json')),'Refusing to overwrite a completed run.');
diary(fullfile(out,'stream.log')); diaryCleanup=onCleanup(@() diary('off')); %#ok<NASGU>
d=phase4_prepare('four'); fs=d.fs; B=options.FrameSize; N=size(d.stems,1);
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
f=uifigure('Name','ELEC5305 Phase 4.1b - four stems','Position',[80 80 1120 650], ...
    'Visible',matlab.lang.OnOffSwitchState(~options.AutoTest || options.ShowUI));
uiCleanup=onCleanup(@() delete_valid(f)); %#ok<NASGU>
f.CloseRequestFcn=@(~,~) requestStop('close');
uilabel(f,'Text','Four-stem binaural spatialisation','FontSize',21,'FontWeight','bold','Position',[30 600 700 32]);
uilabel(f,'Text','44.1 kHz | elevation 0 deg | headphones | Mute overrides Solo', ...
    'Position',[30 570 700 24]);
colours=[0 .45 .74;.85 .33 .10;.47 .67 .19;.49 .18 .56];
names={'Vocals','Drums','Bass','Other'};
sliders=gobjects(1,4); labels=gobjects(1,4); mutes=gobjects(1,4); solos=gobjects(1,4);
for s=1:4
    y=500-(s-1)*115;
    uilabel(f,'Text',names{s},'FontSize',17,'FontWeight','bold','FontColor',colours(s,:), ...
        'Position',[30 y 100 26]);
    labels(s)=uilabel(f,'Position',[140 y 340 26]);
    mutes(s)=uicheckbox(f,'Text','Mute','Position',[475 y 65 26], ...
        'ValueChangedFcn',@(h,~) setControl(s,1,h.Value));
    solos(s)=uicheckbox(f,'Text','Solo','Position',[545 y 60 26], ...
        'ValueChangedFcn',@(h,~) setControl(s,2,h.Value));
    sliders(s)=uislider(f,'Position',[50 y-24 525 3],'Limits',[-80 80], ...
        'MajorTicks',[-80 -40 0 40 80],'Value',engine.targets(s));
    sliders(s).ValueChangingFcn=@(~,e) setAngle(s,e.Value,1);
    sliders(s).ValueChangedFcn=@(h,~) setAngle(s,h.Value,2);
end
ax=uiaxes(f,'Position',[660 160 425 390]); hold(ax,'on');
theta=linspace(-80,80,161); plot(ax,sind(theta),cosd(theta),'Color',[.8 .8 .8]);
plot(ax,0,0,'ko','MarkerFaceColor',[.25 .25 .25],'MarkerSize',15);
text(ax,0,-.1,'Listener','HorizontalAlignment','center');
text(ax,-1.18,.1,'Left (-)'); text(ax,.68,.1,'Right (+)');
text(ax,0,1.22,'Front (0 deg)','HorizontalAlignment','center');
rays=gobjects(1,4); markers=gobjects(1,4);
for s=1:4
    rays(s)=plot(ax,[0 0],[0 1],'--o','Color',colours(s,:),'LineWidth',1,'MarkerSize',7,'MarkerIndices',2);
    markers(s)=plot(ax,0,1,'o','Color',colours(s,:),'MarkerFaceColor',colours(s,:),'MarkerSize',10);
end
legend(ax,markers,names,'Location','southoutside','NumColumns',2);
axis(ax,'equal'); xlim(ax,[-1.3 1.3]); ylim(ax,[-.2 1.35]); ax.XTick=[]; ax.YTick=[];
title(ax,'Filled: selected measured | open: target','FontSize',12);
uilabel(f,'Text','Source radii are offset for visibility; angle controls direction.', ...
    'Position',[655 115 450 28],'FontSize',11);
playButton=uibutton(f,'Text','Play','Position',[30 70 115 35],'ButtonPushedFcn',@(~,~) playNow());
pauseButton=uibutton(f,'Text','Pause','Position',[160 70 115 35],'ButtonPushedFcn',@(~,~) requestStop('pause'));
stopButton=uibutton(f,'Text','Stop','Position',[290 70 115 35],'ButtonPushedFcn',@(~,~) requestStop('stop'));
status=uilabel(f,'Position',[30 16 1060 36],'FontSize',13);
refreshUI(); drawnow; pause(.1); drawnow;
% Capture UI before audio starts; never export graphics in the audio loop.
exportapp(f,fullfile(out,'ui.png'));
appStart=toc(clock); wallStart=tic; cpuStart=cputime;
try
    while isvalid(f) && ~closing
        drawTick=tic; drawnow limitrate; drawSeconds=toc(drawTick);
        if options.AutoTest, driveTest(toc(clock)-appStart); end
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
            engine.reset(); sessions=sessions+1; opened=true; fadeIn=d.fade_samples;
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
        y=engine.step(x); dspSeconds=toc(tick); ready=toc(clock);
        if any(beforeAngles~=engine.selectedAngles), dirty=true; end
        latency=nan(1,4); changed=sequence~=appliedSequence;
        latency(changed)=1000*(ready-parameterTime(changed)); appliedSequence=sequence;
        writerTick=tic; underrun=double(w(y)); writerSeconds=toc(writerTick); returned=toc(clock);
        totalUnderrun=totalUnderrun+underrun;
        row=row+1;
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
    if options.AutoTest
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
writetable(tableFrames,fullfile(out,'frames.csv'));
writetable(array2table(events(1:event,:),'VariableNames', ...
    {'time_s','kind_1_angle_2_mute_3_solo','stem','value','sequence','source_1_changing_2_changed'}), ...
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
if ~isempty(failure), rethrow(failure); end
if options.AutoTest
    fprintf('PHASE4_FOUR_UI_TEST_PASS\n');
end

    function setAngle(s,angle,source)
        if engine.targets(s)==angle, return; end
        engine.setTarget(s,angle); sequence(s)=sequence(s)+1; parameterTime(s)=toc(clock);
        recordEvent(1,s,angle,source); dirty=true;
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
        if playing, return; end
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
        if dirty
            for k=1:4
                labels(k).Text=sprintf('Target %+.1f deg | selected %+.0f deg',engine.targets(k),engine.selectedAngles(k));
                radius=.82+.06*k;
                rays(k).XData=[0 radius*sind(engine.targets(k))];
                rays(k).YData=[0 radius*cosd(engine.targets(k))];
                markers(k).XData=radius*sind(engine.selectedAngles(k));
                markers(k).YData=radius*cosd(engine.selectedAngles(k));
            end
        end
        if playing, state='Playing'; elseif paused, state='Paused'; else, state='Stopped / ready'; end
        if ending && playing, state='Fading / releasing'; end
        status.Text=sprintf('%s | %d samples | underrun %d samples | source %.2f / 12 s', ...
            state,B,totalUnderrun,(cursor-1)/fs);
        playButton.Enable=matlab.lang.OnOffSwitchState(~playing);
        pauseButton.Enable=matlab.lang.OnOffSwitchState(playing);
        dirty=false;
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

function phase4_realtime(options)
%PHASE4_REALTIME Single cached vocal stem, measured horizontal HRIR audition.
% Run via invoke_phase4.ps1 -Mode play. Close the UI to finish the batch job.
arguments
    options.OutputDir (1,:) char = ''
    options.FrameSize (1,1) double {mustBeMember(options.FrameSize,[256 512 1024])} = 1024
    options.Driver (1,:) char = 'WASAPI'
    options.Device (1,:) char = ''
    options.AutoTest (1,1) logical = false
end
oldPath=path; pathCleanup=onCleanup(@() path(oldPath)); %#ok<NASGU>
addpath(fileparts(mfilename('fullpath')));
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
addpath(fullfile(root,'src','matlab','phase4'));
d=phase4_prepare(); fs=d.fs; B=options.FrameSize;
if isempty(options.OutputDir)
    options.OutputDir=fullfile(d.root,'outputs','phase4',char(datetime('now',Format='yyyyMMdd_HHmmss_SSS')));
end
out=options.OutputDir; if ~isfolder(out), mkdir(out); end
diary(fullfile(out,'stream.log')); diaryCleanup=onCleanup(@() diary('off')); %#ok<NASGU>
fprintf('PHASE4_STREAM %s %s fs=%d B=%d frame_ms=%.6f\n',version,options.Driver,fs,B,1000*B/fs);
w=audioDeviceWriter('SampleRate',fs,'Driver',options.Driver,'BufferSize',B);
if ~isempty(options.Device), w.Device=options.Device; end
writerCleanup=onCleanup(@() release(w)); %#ok<NASGU>
clock=tic; target=0; sequence=0; parameterTime=NaN; appliedSequence=0;
playing=false; paused=false; stopKind=''; closing=false; cursor=1;
engine=[]; fadeOut=0; fadeIn=0; tailLeft=0; ending=false; lastDeviceInfo=struct();
rows=zeros(30000,14); row=0; events=zeros(10000,4); event=0; previousOutput=zeros(1,2);
sessions=0; startupUnderrun=0; autoAction=0; autoMove=-1;
f=uifigure('Name','ELEC5305 Phase 4 - one stem HRTF','Position',[120 100 700 560]);
uiCleanup=onCleanup(@() delete_valid(f)); %#ok<NASGU>
f.CloseRequestFcn=@(~,~) requestStop('close');
ax=uiaxes(f,'Position',[160 190 390 320]);
theta=linspace(-80,80,161); plot(ax,sind(theta),cosd(theta),'Color',[.65 .65 .65]); hold(ax,'on');
plot(ax,0,0,'ko',MarkerFaceColor=[.3 .3 .3],MarkerSize=18);
ray=plot(ax,[0 0],[0 1],'-o','LineWidth',3,'Color',[0 .45 .74]);
text(ax,-1,0,'Left (-)'); text(ax,.65,0,'Right (+)'); text(ax,-.15,1.12,'Front');
axis(ax,'equal'); xlim(ax,[-1.25 1.25]); ylim(ax,[-.15 1.3]);
ax.XTick=[]; ax.YTick=[]; title(ax,'Listener at centre; elevation 0 deg');
label=uilabel(f,'Position',[45 495 630 30],'Text','Target +0.0 deg | selected +0 deg');
slider=uislider(f,'Position',[75 160 550 3],'Limits',[-80 80],'Value',0,'MajorTicks',[-80 -40 0 40 80]);
slider.ValueChangingFcn=@(~,e) setAngle(e.Value,1);
slider.ValueChangedFcn=@(s,~) setAngle(s.Value,2);
playButton=uibutton(f,'Text','Play','Position',[70 70 100 35],'ButtonPushedFcn',@(~,~) playNow());
uibutton(f,'Text','Pause','Position',[185 70 100 35],'ButtonPushedFcn',@(~,~) requestStop('pause'));
uibutton(f,'Text','Stop','Position',[300 70 100 35],'ButtonPushedFcn',@(~,~) requestStop('stop'));
status=uilabel(f,'Position',[40 15 650 35],'Text','Ready | vocals, 44.1 kHz | use headphones');
drawnow; pause(.1); drawnow; % Finish expensive first layout before opening the audio stream.
appStart=toc(clock); cpuStart=cputime; wallStart=tic;
failure=[];
try
    while isvalid(f) && ~closing
        drawnow limitrate;
        if options.AutoTest, driveTest(toc(clock)-appStart); end
        if ~playing, pause(.005); continue; end
        if isempty(engine)
            [~,idx]=min(abs(d.angles-target)); engine=Phase4FIR(d.bank,idx,d.fade_samples);
            setup(w,zeros(B,2));
            % Warm driver/JIT with silence; report these underruns separately.
            for warm=1:ceil(.15*fs/B)
                engine.step(zeros(B,1),d.bank,idx); % Warm FIR/JIT before measured audio.
                startupUnderrun=startupUnderrun+double(w(zeros(B,2)));
            end
            sessions=sessions+1; fprintf('SESSION=%d DEVICE=%s\n',sessions,w.Device);
            lastDeviceInfo=info(w); disp(lastDeviceInfo); fadeIn=d.fade_samples;
            ending=false; appliedSequence=sequence; previousOutput=zeros(1,2);
            if options.AutoTest && sessions==1, appStart=toc(clock); end
        end
        if ~isempty(stopKind) && ~ending
            ending=true; fadeOut=d.fade_samples; tailLeft=size(d.bank,1)-1;
        end
        tick=tic; t0=toc(clock);
        [~,idx]=min(abs(d.angles-target));
        x=zeros(B,1);
        if ~ending || fadeOut>0
            count=B; if ending, count=min(B,fadeOut); end
            % Endpoint fades make the repeating 12-second excerpt continuous.
            indices=mod(cursor-1+(0:count-1),numel(d.mono))+1;
            x(1:count)=d.mono(indices); cursor=mod(cursor-1+count,numel(d.mono))+1;
            if ending
                x(1:count)=x(1:count).*max(0,(fadeOut-(1:count)')/d.fade_samples);
                fadeOut=fadeOut-count;
                tailLeft=tailLeft-(B-count);
            end
        else
            tailLeft=tailLeft-B;
        end
        if fadeIn>0 && ~ending
            count=min(B,fadeIn);
            x(1:count)=x(1:count).*(d.fade_samples-fadeIn+(1:count)')/d.fade_samples;
            fadeIn=fadeIn-count;
        end
        directionChanged=idx~=engine.index;
        y=engine.step(x,d.bank,idx);
        assert(all(isfinite(y),'all') && size(y,2)==2 && max(abs(y),[],'all')<1,'Audio integrity gate failed');
        ready=toc(clock); dspSeconds=toc(tick); latency=NaN;
        if sequence~=appliedSequence
            latency=1000*(ready-parameterTime); appliedSequence=sequence;
        end
        % numUnderrun is integer: cast before horizontal concatenation, or MATLAB
        % would coerce timing, angles and peaks in the whole row to integers.
        underrun=double(w(y)); returned=toc(clock);
        row=row+1;
        rows(row,:)=[sessions,t0,dspSeconds,returned-t0,underrun,target,d.angles(idx),sequence,latency, ...
            max(abs(y),[],'all'),max(abs(diff(y)),[],'all'),ending, ...
            max(abs(y(1,:)-previousOutput)),double(directionChanged)];
        previousOutput=y(end,:);
        if mod(row,round(.25*fs/B))==0
            status.Text=sprintf('Playing | %d samples | underrun %d samples | %.1f s',B,sum(rows(1:row,5)),toc(wallStart));
        end
        if ending && fadeOut==0 && tailLeft<=0
            % Push enough silence to drain the configured software buffer before release.
            for drain=1:4, startupUnderrun=startupUnderrun+double(w(zeros(B,2))); end
            release(w); engine=[]; playing=false;
            if strcmp(stopKind,'pause')
                paused=true; status.Text='Paused | Play resumes after faded boundary';
            else
                cursor=1; paused=false; status.Text='Stopped | audio device released';
            end
            closing=strcmp(stopKind,'close'); stopKind=''; playButton.Enable='on';
        end
    end
catch ME
    failure=ME; fprintf('STREAM_ERROR %s: %s\n',ME.identifier,ME.message);
end
release(w);
names={'session','start_s','dsp_s','dsp_and_writer_s','underrun_samples','target_deg','selected_deg', ...
    'parameter_sequence','callback_to_ready_ms','peak','within_frame_max_step','ending', ...
    'boundary_step','direction_changed'};
writetable(array2table(rows(1:row,:),'VariableNames',names),fullfile(out,'frames.csv'));
writetable(array2table(events(1:event,:),'VariableNames',{'sequence','time_s','angle_deg','source'}),fullfile(out,'parameter_events.csv'));
summary=struct('version',version,'sample_rate',fs,'frame_size',B,'frame_ms',1000*B/fs, ...
    'driver',options.Driver,'device',w.Device,'device_info',lastDeviceInfo,'input',d.input, ...
    'gain',d.gain,'directions',d.angles,'hrir_samples',size(d.bank,1), ...
    'crossfade_samples',d.fade_samples,'underrun_samples',sum(rows(1:row,5)), ...
    'startup_and_drain_underrun_samples',startupUnderrun,'sessions',sessions, ...
    'rendered_frames',row*B,'channel_order','left,right','all_samples_finite',isempty(failure), ...
    'process_cpu_seconds',cputime-cpuStart,'wall_seconds',toc(wallStart),'auto_test',options.AutoTest, ...
    'complete',isempty(failure),'latency_scope','callback execution to first rendered output frame ready; excludes queued hardware audio');
fid=fopen(fullfile(out,'summary.json'),'w'); fprintf(fid,'%s',jsonencode(summary,PrettyPrint=true)); fclose(fid);
fprintf('PHASE4_STREAM_FINISHED frames=%d underrun_samples=%d\n',row,summary.underrun_samples);
if ~isempty(failure), rethrow(failure); end

    function setAngle(angle,source)
        target=max(-80,min(80,angle)); sequence=sequence+1; parameterTime=toc(clock);
        event=event+1; events(event,:)=[sequence,parameterTime,target,source];
        [~,selection]=min(abs(d.angles-target));
        label.Text=sprintf('Target %+.1f deg | selected %+.0f deg (measured)',target,d.angles(selection));
        ray.XData=[0 sind(target)]; ray.YData=[0 cosd(target)];
    end
    function playNow()
        if playing, return; end
        if ~paused, cursor=1; end
        playing=true; stopKind=''; playButton.Enable='off';
    end
    function requestStop(kind)
        if playing
            stopKind=kind;
        elseif strcmp(kind,'close')
            closing=true;
        elseif strcmp(kind,'stop')
            cursor=1; paused=false; status.Text='Stopped | audio device released';
        end
    end
    function driveTest(t)
        % Invoke the actual ValueChangingFcn during playback, without mouse-release events.
        times=[0 8 8.5 10 10.5 30 31];
        if autoAction<numel(times) && t>=times(autoAction+1)
            autoAction=autoAction+1;
            switch autoAction
                case {1,3,5}, playNow();
                case 2, requestStop('pause');
                case {4,6}, requestStop('stop');
                case 7, requestStop('close');
            end
        end
        step=floor(t/.04);
        if step~=autoMove && t<30
            autoMove=step;
            if t<3, angle=-65;
            elseif t<8, angle=-80+160*(t-3)/5;
            elseif t>=12 && t<16, angle=80*(-1)^step;
            else, angle=40; end
            slider.Value=angle; slider.ValueChangingFcn(slider,struct('Value',angle));
        end
    end
end

function delete_valid(f)
if isvalid(f), delete(f); end
end

function phase4_four_validate(outputDir)
%PHASE4_FOUR_VALIDATE Deterministic four-source DSP checks without a device.
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
oldPath=path; cleanupPath=onCleanup(@() path(oldPath)); %#ok<NASGU>
addpath(fileparts(mfilename('fullpath')),fullfile(root,'src','matlab','phase4'), ...
    fullfile(root,'src','matlab','phase2','hrtf'));
if ~isfolder(outputDir), mkdir(outputDir); end
assert(~isfile(fullfile(outputDir,'summary.json')),'Refusing to overwrite a completed run.');
diary(fullfile(outputDir,'validation.log')); cleanupDiary=onCleanup(@() diary('off')); %#ok<NASGU>
rng(5305); d=phase4_prepare('four'); single=phase4_prepare();
B=1024; N=size(d.stems,1); L=size(d.bank,1);
assert(isequal(size(d.stems),[529200 4]) && d.fs==44100 && d.fade_samples==882 && L==200);
assert(all([d.input.frames]==N) && all(isfinite(d.stems),'all'));
assert(d.alignment.first_frame==1323001 && d.alignment.last_frame==1852200);
assert(max(abs(d.stems(:,1)*single.gain-single.mono))<1e-15);
fprintf('ALIGNED fs=%d frames=%d channels=4 first=%d last=%d gain=%.12g bound=%.12g\n', ...
    d.fs,N,d.alignment.first_frame,d.alignment.last_frame,d.gain,d.gain*d.mix_bound_before_gain);

% Fixed four-source directions, complete tails, frozen static reference.
fixed=[-65 -20 15 55]; engine=Phase4Mixer(d); setTargets(engine,fixed); engine.reset();
z=[d.stems;zeros(L-1,4)]; z(end+1:ceil(size(z,1)/B)*B,:)=0;
reference=zeros(N+L-1,2);
for s=1:4
    idx=find(d.angles==fixed(s));
    reference=reference+d.gain*render_static_binaural(d.stems(:,s),d.bank(:,1,idx),d.bank(:,2,idx));
end
actual=zeros(size(z,1),2);
for n=1:B:size(z,1), actual(n:n+B-1,:)=engine.step(z(n:n+B-1,:)); end
staticError=max(abs(actual(1:size(reference,1),:)-reference),[],'all');
assert(staticError<1e-12 && max(abs(actual(size(reference,1)+1:end,:)),[],'all')<1e-12);
staticPeak=max(abs(actual),[],'all');

% Solo regression uses the original single-stem FIR with the same shared gain.
soloError=0;
for s=1:4
    engine=Phase4Mixer(d); setTargets(engine,fixed); engine.setSolo(s,true); engine.reset();
    idx=find(d.angles==fixed(s)); old=Phase4FIR(d.bank,idx,d.fade_samples);
    for n=1:B:size(z,1)
        frame=z(n:n+B-1,:); y=engine.step(frame);
        ref=old.step(d.gain*frame(:,s),d.bank,idx);
        soloError=max(soloError,max(abs(y-ref),[],'all'));
    end
end
assert(soloError<1e-12);

% Routing matrix: every combination of four Mute and four Solo flags.
frame=.01*randn(B,4); raw=zeros(B,2,4);
for s=1:4
    idx=find(d.angles==fixed(s)); e=Phase4FIR(d.bank,idx,d.fade_samples);
    raw(:,:,s)=e.step(frame(:,s),d.bank,idx);
end
routingError=0;
for m=0:15
    for so=0:15
        engine=Phase4Mixer(d); setTargets(engine,fixed);
        mute=logical(bitget(m,1:4)); solo=logical(bitget(so,1:4));
        for s=1:4, engine.setMute(s,mute(s)); engine.setSolo(s,solo(s)); end
        engine.reset(); [y,parts]=engine.step(frame);
        expected=~mute & (~any(solo) | solo);
        assert(isequal(engine.audible(),expected)); ref=zeros(B,2);
        for s=1:4
            ref=ref+d.gain*raw(:,:,s)*expected(s);
            assert(max(abs(parts(:,:,s)-raw(:,:,s)*expected(s)),[],'all')<1e-12);
        end
        routingError=max(routingError,max(abs(y-ref),[],'all'));
    end
end
assert(routingError<1e-12);

% Changing only one target must leave every other source and history unchanged.
isolationError=0;
for moving=1:4
    a=Phase4Mixer(d); b=Phase4Mixer(d);
    for k=1:20
        b.setTarget(moving,80*(-1)^k);
        frame=d.stems((k-1)*B+(1:B),:);
        [~,pa]=a.step(frame); [~,pb]=b.step(frame);
        for s=setdiff(1:4,moving)
            isolationError=max(isolationError,max(abs(pa(:,:,s)-pb(:,:,s)),[],'all'));
            assert(isequal(a.engines{s}.history,b.engines{s}.history));
            assert(isequal(a.engines{s}.current,b.engines{s}.current));
        end
    end
end
assert(isolationError==0);

% Slow and per-frame rapid retargeting against four separate original renderers.
metrics=zeros(3,8); dynamicError=0;
for mode=1:3
    engine=Phase4Mixer(d); refEngines=cell(1,4);
    for s=1:4
        idx=find(d.angles==engine.targets(s)); refEngines{s}=Phase4FIR(d.bank,idx,d.fade_samples);
    end
    count=ceil(N/B); times=zeros(count,1); peak=0; error=0;
    for k=1:count
        frame=zeros(B,4); first=(k-1)*B+1; take=min(B,N-first+1);
        frame(1:take,:)=d.stems(first:first+take-1,:);
        for s=1:4
            if mode==1, angle=fixed(s);
            elseif mode==2, angle=80*sin(2*pi*(k-1)/count+(s-1)*pi/2);
            else, angle=(60+5*s)*(-1)^(k+s); end
            engine.setTarget(s,angle);
        end
        tick=tic; y=engine.step(frame); times(k)=toc(tick); ref=zeros(B,2);
        for s=1:4
            [~,idx]=min(abs(d.angles-engine.targets(s)));
            ref=ref+d.gain*refEngines{s}.step(frame(:,s),d.bank,idx);
        end
        error=max(error,max(abs(y-ref),[],'all')); peak=max(peak,max(abs(y),[],'all'));
        assert(all(isfinite(y),'all') && isequal(size(y),[B 2]));
    end
    ordered=sort(times);
    metrics(mode,:)=[mode,B,1000*B/d.fs,1000*mean(times), ...
        1000*ordered(ceil(.99*count)),1000*max(times),peak,error];
    dynamicError=max(dynamicError,error);
end
assert(dynamicError<1e-12 && max(metrics(:,7))<1);

% Mute/Solo transitions and retargeting at B<fade length test persistent ramps.
small=256; engine=Phase4Mixer(d); referenceEngines=cell(1,4);
for s=1:4
    idx=find(d.angles==engine.targets(s)); referenceEngines{s}=Phase4FIR(d.bank,idx,d.fade_samples);
end
gates=ones(1,4); gateError=0;
for k=1:60
    if k==3, engine.setMute(2,true); end
    if k==8, engine.setSolo(1,true); end
    if k==12, engine.setSolo(3,true); end
    if k==18, engine.setMute(1,true); end
    if k==24, engine.setSolo(1,false); engine.setSolo(3,false); end
    if k==30, engine.setMute(1,false); engine.setMute(2,false); end
    for s=1:4, engine.setTarget(s,80*sin(k*.6+s)); end
    frame=d.stems((k-1)*small+(1:small),:); actual=engine.step(frame); ref=zeros(small,2);
    mask=double(engine.audible());
    for s=1:4
        [~,idx]=min(abs(d.angles-engine.targets(s)));
        part=referenceEngines{s}.step(frame(:,s),d.bank,idx);
        for n=1:small
            gates(s)=gates(s)+sign(mask(s)-gates(s))*min(1/d.fade_samples,abs(mask(s)-gates(s)));
            ref(n,:)=ref(n,:)+d.gain*gates(s)*part(n,:);
        end
        assert(max(abs(engine.engines{s}.history-referenceEngines{s}.history))==0);
    end
    gateError=max(gateError,max(abs(actual-ref),[],'all'));
end
assert(gateError<1e-12);

% Explicit channel-order impulse: distinct left and right tap positions.
test=d; test.bank=zeros(L,2,numel(d.angles)); test.bank(1,1,:)=.2; test.bank(3,2,:)=.1;
engine=Phase4Mixer(test); impulse=zeros(B,4); impulse(1,:)=[.1 .2 .3 .4];
y=engine.step(impulse); expected=zeros(B,2); expected(1,1)=d.gain*.2; expected(3,2)=d.gain*.1;
channelError=max(abs(y-expected),[],'all'); assert(channelError<1e-15);
for angle=[-80 80]
    idx=find(d.angles==angle); cues=compute_hrir_cues(d.bank(:,1,idx),d.bank(:,2,idx),d.fs);
    assert(sign(cues.itd_us)==sign(angle) && sign(cues.ild_db)==sign(angle));
end

t=array2table(metrics,'VariableNames',{'mode_1_fixed_2_slow_3_fast','frame_size', ...
    'frame_ms','mean_dsp_ms','p99_dsp_ms','max_dsp_ms','peak','independent_reference_error'});
disp(t); writetable(t,fullfile(outputDir,'offline_results.csv'));
summary=struct('complete',true,'version',version,'seed',5305,'sample_rate',d.fs,'frames_per_stem',N, ...
    'channel_order','left,right','all_samples_finite',true,'input',d.input,'alignment',d.alignment, ...
    'gain',d.gain,'hrir_subject','CIPIC subject_003','elevation_deg',0,'directions',d.angles, ...
    'hrir_samples',L,'crossfade_samples',d.fade_samples,'frame_size',B, ...
    'static_reference_error',staticError,'static_peak',staticPeak,'solo_regression_error',soloError, ...
    'mute_solo_cases',256,'routing_error',routingError,'isolation_error',isolationError, ...
    'dynamic_error',dynamicError,'gate_transition_error',gateError,'channel_order_error',channelError, ...
    'conservative_mix_bound',d.gain*d.mix_bound_before_gain);
fid=fopen(fullfile(outputDir,'summary.json'),'w'); fprintf(fid,'%s',jsonencode(summary,PrettyPrint=true)); fclose(fid);
fprintf('PHASE4_FOUR_VALIDATION_PASS static=%.3g solo=%.3g dynamic=%.3g gates=%.3g\n', ...
    staticError,soloError,dynamicError,gateError);
end

function setTargets(engine,angles)
for s=1:4, engine.setTarget(s,angles(s)); end
end

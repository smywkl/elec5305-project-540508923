function phase4_studio_validate(outputDir)
%PHASE4_STUDIO_VALIDATE Deterministic geometry, callback and master-gain checks.
root=fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
old=path; pc=onCleanup(@() path(old)); %#ok<NASGU>
addpath(fileparts(mfilename('fullpath')),fullfile(root,'src','matlab','phase4'));
if ~isfolder(outputDir), mkdir(outputDir); end
assert(~isfile(fullfile(outputDir,'validation.json')),'Refusing to overwrite a completed run.');
diary(fullfile(outputDir,'validation.log')); dc=onCleanup(@() diary('off')); %#ok<NASGU>
for file={'Phase4StudioView','Phase4MasterGain','phase4_four_realtime','phase4_studio_validate'}
    messages=checkcode(which(file{1}),'-id');
    assert(~any(strcmp({messages.id},'PARSE')),'MATLAB parse error.');
end
fprintf('STUDIO_TEST build\n');
v=Phase4StudioView(false,true); vc=onCleanup(@() delete(v)); %#ok<NASGU>
targets=[0 -45 0 45]; selected=[0 -45 0 45]; eventCount=zeros(1,4);
v.onAngle=@angleChanged;
limits=[v.axes.XLim v.axes.YLim v.axes.DataAspectRatio];
assert(isempty(v.axes.Interactions) && strcmp(v.axes.Toolbar.Visible,'off'));
assert(strcmp(v.axes.XLimMode,'manual') && strcmp(v.axes.YLimMode,'manual'));
% Background motion without a marker-down event does nothing.
before=targets; v.dragAt(1,0); v.figure.WindowButtonMotionFcn([],[]);
assert(isequal(before,targets) && v.dragging==0);
% All four coincide. Explicit stem selection must override graphics draw order.
targets(:)=0; v.updateAngles(targets,selected);
for s=1:4
    v.selectStem(s); before=targets;
    v.beginDrag(4,[]); assert(v.dragging==s);
    a=(-1)^s*(15+10*s); v.dragAt(sind(a),cosd(a)); v.endDrag();
    assert(abs(targets(s)-a)<1e-10 && isequal(targets(setdiff(1:4,s)),before(setdiff(1:4,s))));
    assert(abs(v.sliders(s).Value-a)<1e-10 && contains(v.labels(s).Text,sprintf('%+.1f',a)));
    assert(abs(hypot(v.markers(s).XData,v.markers(s).YData)-1)<1e-12);
    targets(:)=0; v.updateAngles(targets,selected);
end
% Clamp behind/outside positions, ignore listener singularity, release capture.
v.selectStem(2); v.beginDrag(1,[]); v.dragAt(1,-1); assert(targets(2)==80);
v.dragAt(-1,-1); assert(targets(2)==-80);
v.dragAt(0,0); assert(targets(2)==-80); v.endDrag();
v.dragAt(0,1); assert(targets(2)==-80);
% Slider changing callback uses the same target path and does not require release.
for s=1:4
    a=20*(-1)^s; v.sliders(s).ValueChangingFcn([],struct('Value',a));
    assert(targets(s)==a && v.sliders(s).Value==a);
    assert(abs(v.markers(s).XData-sind(a))<1e-12 && abs(v.markers(s).YData-cosd(a))<1e-12);
end
assert(isequal(limits,[v.axes.XLim v.axes.YLim v.axes.DataAspectRatio]));
fprintf('STUDIO_TEST geometry pass\n');
targets=[-50 -15 15 50]; v.updateAngles(targets,targets); drawnow;
exportgraphics(v.axes,fullfile(outputDir,'stage_geometry.png'),'Resolution',150);
fprintf('STUDIO_TEST gain checks\n');
% A reference sample-by-sample ramp, rapid retargets, zero/unity and B<ramp.
fs=44100; error=0; maxSlew=0; peak=0; output=[];
for B=[256 1024]
    gain=Phase4MasterGain(fs,65); current=(.65)^2; previous=current;
    percent=[0 100 25 90 0 0 0 0 0 0 0 0 100 100 100 100 100 100 100 100];
    for k=1:numel(percent)
        gain.setPercent(percent(k)); target=(percent(k)/100)^2;
        t=((k-1)*B+(0:B-1))'/fs;
        x=[.49*sin(2*pi*440*t),.31*cos(2*pi*630*t)];
        [y,envelope]=gain.step(x); reference=zeros(B,1);
        for n=1:B
            current=current+sign(target-current)*min(1/round(.04*fs),abs(target-current));
            reference(n)=current;
        end
        error=max(error,max(abs(y-x.*reference),[],'all'));
        maxSlew=max(maxSlew,max(abs(diff([previous;envelope])))); previous=envelope(end);
        assert(all(envelope>=0 & envelope<=1) && all(isfinite(y),'all') && size(y,2)==2);
        peak=max(peak,max(abs(y),[],'all'));
        if B==1024, output=[output;y]; end %#ok<AGROW>
    end
    assert(gain.current==1);
end
assert(error<1e-12 && maxSlew<=1/1764+1e-14 && peak<.5);
audiowrite(fullfile(outputDir,'master_sweep.wav'),output,fs,'BitsPerSample',24);
result=struct('complete',true,'version',version,'geometry_radius',1,'directions',[-80 80], ...
    'all_four_independent',all(eventCount>0),'overlap_selection',true,'slider_sync',true, ...
    'background_noop',true,'axes_locked',true,'master_reference_error',error, ...
    'max_gain_step',maxSlew,'gain_step_bound',1/1764,'peak',peak,'sample_rate',fs, ...
    'channels',2,'channel_order','left,right','frames',size(output,1), ...
    'duration_seconds',size(output,1)/fs,'all_samples_finite',all(isfinite(output),'all'), ...
    'clipped_samples',nnz(abs(output)>=1),'gain_mapping','(percent/100)^2', ...
    'scope','Deterministic callbacks and signal checks; physical mouse/device validated separately.');
fid=fopen(fullfile(outputDir,'validation.json'),'w'); fprintf(fid,'%s',jsonencode(result,PrettyPrint=true)); fclose(fid);
fprintf('PHASE4_STUDIO_VALIDATION_PASS gain_error=%.3g peak=%.4f\n',error,peak);
delete(v); clear vc;
    function angleChanged(s,a,~)
        targets(s)=a; eventCount(s)=eventCount(s)+1;
    end
end

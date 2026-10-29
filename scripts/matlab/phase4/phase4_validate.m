function phase4_validate(outputDir)
%PHASE4_VALIDATE Bounded offline tests; no playback or old result writes.
if ~isfolder(outputDir), mkdir(outputDir); end
diary(fullfile(outputDir,'validation.log')); diaryCleanup=onCleanup(@() diary('off')); %#ok<NASGU>
old=path; cleanup=onCleanup(@() path(old)); %#ok<NASGU>
addpath(fileparts(mfilename('fullpath'))); d=phase4_prepare();
addpath(fullfile(d.root,'src','matlab','phase2','hrtf'));
fprintf('INPUT %s %s frames=%d fs=%d gain=%.12g\n',d.input.track,d.input.stem,numel(d.mono),d.fs,d.gain);
fprintf('MEASURED_GRID=%s\n',mat2str(d.angles));
% Exercise installed interpolation API without using it in the audition path.
ir=interpolateHRTF(d.subject.hrir,d.subject.source_positions(:,1:2),[0 0],Algorithm='nearest');
[~,centre]=min(abs(d.angles));
assert(max(abs(reshape(ir,2,[]).'-d.bank(:,:,centre)),[],'all')<1e-12);
for angle=[-80 80]
    idx=find(d.angles==angle); cues=compute_hrir_cues(d.bank(:,1,idx),d.bank(:,2,idx),d.fs);
    fprintf('ANGLE=%g ITD_us=%g ILD_R_over_L_dB=%g\n',angle,cues.itd_us,cues.ild_db);
    assert(sign(cues.itd_us)==sign(angle) && sign(cues.ild_db)==sign(angle));
end
rng(5305); x=.01*randn(4097,1); L=size(d.bank,1); results=[];
for B=[256 512 1024]
    maxError=0;
    % All exact directions and full convolution tail must match frozen static renderer.
    for idx=1:numel(d.angles)
        e=Phase4FIR(d.bank,idx,d.fade_samples);
        z=[x;zeros(L-1,1)]; z(end+1:ceil(numel(z)/B)*B)=0;
        y=zeros(numel(z),2);
        for n=1:B:numel(z), y(n:n+B-1,:)=e.step(z(n:n+B-1),d.bank,idx); end
        ref=render_static_binaural(x,d.bank(:,1,idx),d.bank(:,2,idx));
        err=max(abs(y(1:size(ref,1),:)-ref),[],'all'); maxError=max(maxError,err);
        assert(err<1e-12 && max(abs(y(size(ref,1)+1:end,:)),[],'all')<1e-12);
    end
    % Rapid retargeting: independent sample-domain LTV reference, sharing input history.
    e=Phase4FIR(d.bank,centre,d.fade_samples); history=zeros(L-1,1);
    h=d.bank(:,:,centre); target=h; remaining=0; previous=centre;
    maxDynamicError=0; smooth=[]; hard=[];
    for k=1:40
        if mod(k,2), idx=1; else, idx=numel(d.angles); end
        frame=.01*ones(B,1); ext=[history;frame];
        if idx~=previous, target=d.bank(:,:,idx); remaining=d.fade_samples; previous=idx; end
        reference=zeros(B,2); hardFrame=zeros(B,2);
        startH=h;
        for n=1:B
            if remaining>0, alpha=min(n/remaining,1); else, alpha=0; end
            hn=(1-alpha)*startH+alpha*target;
            reference(n,:)=ext(n+L-1:-1:n).'*hn;
            hardFrame(n,:)=ext(n+L-1:-1:n).'*d.bank(:,:,idx);
        end
        if remaining>0, h=hn; remaining=max(0,remaining-B); end
        actual=e.step(frame,d.bank,idx);
        maxDynamicError=max(maxDynamicError,max(abs(actual-reference),[],'all'));
        history=ext(end-L+2:end); smooth=[smooth;actual]; hard=[hard;hardFrame]; %#ok<AGROW>
    end
    assert(maxDynamicError<1e-12);
    edges=B+1:B:size(smooth,1);
    smoothJump=max(abs(smooth(edges,:)-smooth(edges-1,:)),[],'all');
    hardJump=max(abs(hard(edges,:)-hard(edges-1,:)),[],'all');
    assert(smoothJump<hardJump);
    for mode=1:3
        e=Phase4FIR(d.bank,centre,d.fade_samples); times=zeros(ceil(numel(d.mono)/B),1);
        peak=0;
        for k=1:numel(times)
            if mode==1, a=0;
            elseif mode==2, a=-80+160*(k-1)/(numel(times)-1);
            else, a=80*(-1)^floor(k/3); end
            [~,idx]=min(abs(d.angles-a));
            frame=zeros(B,1); first=(k-1)*B+1; count=min(B,numel(d.mono)-first+1);
            frame(1:count)=d.mono(first:first+count-1);
            timer=tic; y=e.step(frame,d.bank,idx); times(k)=toc(timer);
            assert(all(isfinite(y),'all') && size(y,2)==2); peak=max(peak,max(abs(y),[],'all'));
        end
        assert(peak<1);
        results=[results; B mode B/d.fs*1000 mean(times)*1000 prctile(times,99)*1000 ...
            max(times)*1000 mean(times)/(B/d.fs) peak maxError maxDynamicError smoothJump hardJump]; %#ok<AGROW>
    end
end
names={'frame_size','trajectory_1_static_2_slow_3_fast','frame_ms','mean_dsp_ms','p99_dsp_ms', ...
    'max_dsp_ms','dsp_rtf','peak','static_error','dynamic_error','smooth_boundary_jump','hard_boundary_jump'};
t=array2table(results,'VariableNames',names); disp(t); writetable(t,fullfile(outputDir,'offline_results.csv'));
fid=fopen(fullfile(outputDir,'input.json'),'w'); fprintf(fid,'%s',jsonencode(d.input,PrettyPrint=true)); fclose(fid);
% Existing synthetic regression entry point only; it does not touch scientific outputs.
run(fullfile(d.root,'tests','matlab','phase2','test_phase2_7_error_interaction.m'));
fprintf('PHASE4_VALIDATION_PASS\n');
end

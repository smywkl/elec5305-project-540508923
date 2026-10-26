function result = phase3_2b_run_cross_subject(mode, outputRoot)
%PHASE3_2B_RUN_CROSS_SUBJECT Gated orchestration of frozen scientific helpers.
arguments
    mode (1,1) string {mustBeMember(mode,["run","test"])} = "run"
    outputRoot (1,1) string = ""
end
repoRoot = string(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
oldPath = path;
cleanupPath = onCleanup(@() path(oldPath)); %#ok<NASGU>
for folder = ["hrtf","spatial","oracle","comparison"]
    addpath(fullfile(repoRoot,"src","matlab","phase2",folder));
end
cfg = contract(repoRoot);
if mode == "test"
    wrapper_test(cfg);
    result = cfg;
    return;
end
overall = tic;
if outputRoot == ""
    outputRoot = fullfile(repoRoot,"outputs","phase3","phase3_2b_cross_subject_20261026");
end
outputRoot = string(java.io.File(char(outputRoot)).getCanonicalPath());
allowedRoot = string(java.io.File(char(fullfile(repoRoot,"outputs","phase3"))).getCanonicalPath());
assert(startsWith(outputRoot, allowedRoot + filesep), 'Dedicated Phase 3 run required');
preflightPath = fullfile(outputRoot,"preflight.json");
p = jsondecode(fileread(preflightPath));
signature = string(p.signature);
preflightHash = file_hash(preflightPath);
for hi = 1:numel(p.hash_records)
    entry = p.hash_records(hi);
    assert(file_hash(fullfile(repoRoot,string(entry.path))) == string(entry.sha256), ...
        'Code/protocol/reference hash mismatch: %s', entry.path);
end
fprintf('MATLAB_VERSION=%s ARCH=%s PREFDIR=%s\n',version,computer('arch'),prefdir);
disp(ver);
testTimer = tic;
run_test(fullfile(repoRoot,"tests","matlab","phase2","test_phase2_7_error_interaction.m"));
run_test(fullfile(repoRoot,"tests","matlab","phase2","test_phase2_10_robustness_controls.m"));
wrapper_test(cfg);
testSeconds = toc(testTimer);
manifest = jsondecode(fileread(fullfile(repoRoot,"config","phase2","final_test_manifest.json")));
subjects = cell(3,1);
subjectRecords = cell(3,1);
for si = 1:3
    entry = p.subjects(si);
    assert(string(entry.subject_id) == cfg.subjects(si));
    assert(file_hash(fullfile(repoRoot,string(entry.path))) == string(entry.sha256));
    subject = load_cipic_subject(fullfile(repoRoot,string(entry.path)));
    subjectRecords{si} = subject_gate(subject,cfg.subjects(si),cfg.angles);
    subjects{si} = subject;
end
% Gate A verifies availability/alignment of every input before any scientific
% render. Byte identities were checked by the Python preflight; cache hashes
% and decoded samples are also checked by the existing loader at each song.
for ti = 1:10
    track = manifest.selected_tracks(ti);
    assert(track.rank == ti);
    gtDir = fullfile(repoRoot,string(track.dataset_relative_path));
    cacheDir = fullfile(repoRoot,"outputs","phase2","phase2_5_final","cache","htdemucs_ft",string(track.track_name_original));
    marker = jsondecode(fileread(fullfile(cacheDir,"completion.json")));
    for stem = ["mixture",cfg.stems]
        info = audioinfo(fullfile(gtDir,stem+".wav"));
        assert(info.SampleRate == 44100 && info.NumChannels == 2 && info.TotalSamples == marker.mixture_frame_count);
        assert(info.TotalSamples >= 2646000);
    end
    for stem = cfg.stems
        info = audioinfo(fullfile(cacheDir,stem+".wav"));
        assert(info.SampleRate == 44100 && info.NumChannels == 2 && info.TotalSamples == marker.mixture_frame_count && info.BitsPerSample == 32);
    end
end
gateASeconds = toc(overall);
write_json(fullfile(outputRoot,"gate_a.json"),struct('status',"PASS", ...
    'signature',signature,'test_seconds',testSeconds,'matlab_preflight_seconds',gateASeconds, ...
    'subjects',vertcat(subjectRecords{:}),'audio_metadata_files',90));
fprintf('GATE_A_PASS tests_seconds=%.6f\n',testSeconds);
allTables = cell(3,1);
loadSeconds = zeros(3,10);
evaluationSeconds = zeros(3,10);
scienceTimer = tic;
for si = 1:3
    subjectId = cfg.subjects(si);
    blocks = cell(10,1);
    for ti = 1:10
        track = manifest.selected_tracks(ti);
        trackName = string(track.track_name_original);
        trackRoot = fullfile(outputRoot,"tracks",subjectId,compose('%02d',ti));
        if isfolder(trackRoot)
            mark = jsondecode(fileread(fullfile(trackRoot,"completion.json")));
            assert(string(mark.signature) == signature && string(mark.status) == "COMPLETE", 'Incompatible resume');
            assert(string(mark.preflight_sha256) == preflightHash);
            for fi = 1:numel(mark.files)
                entry = mark.files(fi);
                assert(file_hash(fullfile(trackRoot,string(entry.path))) == string(entry.sha256), 'Completed output hash mismatch');
            end
            block = read_block(trackRoot);
            validate_block(block,cfg,subjectId,ti,trackName,p.schemas);
            loadSeconds(si,ti) = mark.load_seconds;
            evaluationSeconds(si,ti) = mark.evaluation_seconds;
            fprintf('RESUME %s rank=%d\n',subjectId,ti);
        else
            fprintf('EVALUATE %s rank=%d track=%s\n',subjectId,ti,trackName);
            timer = tic;
            gt = load_musdb_gt_excerpt(fullfile(repoRoot,string(track.dataset_relative_path)),30,30,44100);
            cacheDir = fullfile(repoRoot,"outputs","phase2","phase2_5_final","cache","htdemucs_ft",trackName);
            estimate = load_final_cached_excerpt(cacheDir,fullfile(cacheDir,"completion.json"),trackName,30,30,44100);
            assert(gt.frame_count == 1323000 && estimate.frame_count == gt.frame_count);
            assert(gt.start_frame_matlab_1_based == 1323001 && estimate.start_frame_matlab_1_based == 1323001);
            assert(gt.end_frame_matlab_1_based_inclusive == 2646000 && estimate.end_frame_matlab_1_based_inclusive == 2646000);
            loadSeconds(si,ti) = toc(timer);
            timer = tic;
            [block,audit] = evaluate_track(gt.mono,estimate.mono,subjects{si},cfg,subjectId,ti,trackName,1323000);
            evaluationSeconds(si,ti) = toc(timer);
            validate_block(block,cfg,subjectId,ti,trackName,p.schemas);
            parent = fileparts(trackRoot);
            if ~isfolder(parent), mkdir(parent); end
            stage = trackRoot + ".partial_" + string(java.util.UUID.randomUUID());
            mkdir(stage);
            fields = fieldnames(block);
            files = repmat(struct('path',"",'sha256',""),5,1);
            for k = 1:4
                filename = string(fields{k})+".csv";
                writetable(block.(fields{k}),fullfile(stage,filename));
                files(k) = struct('path',filename,'sha256',file_hash(fullfile(stage,filename)));
            end
            write_json(fullfile(stage,"validation.json"),audit);
            files(5) = struct('path',"validation.json",'sha256',file_hash(fullfile(stage,"validation.json")));
            mark = struct('status',"COMPLETE",'signature',signature,'preflight_sha256',preflightHash, ...
                'subject_id',subjectId,'rank',ti,'track',trackName,'files',files, ...
                'load_seconds',loadSeconds(si,ti),'evaluation_seconds',evaluationSeconds(si,ti));
            write_json(fullfile(stage,"completion.json"),mark);
            assert(~isfolder(trackRoot));
            [ok,msg] = movefile(stage,trackRoot);
            assert(ok,msg);
            clear gt estimate;
        end
        blocks{ti} = block;
    end
    allTables{si} = combine_blocks(blocks);
    if si == 1
        regression = baseline_regression(allTables{1},repoRoot,p.baseline_paths);
        write_json(fullfile(outputRoot,"baseline_regression.json"),regression);
        fprintf('GATE_B_PASS cases=30 max_scaled_error=%.17g\n',regression.max_scaled_difference);
    end
end
tables = combine_blocks(allTables);
metricsRoot = fullfile(outputRoot,"metrics");
if ~isfolder(metricsRoot), mkdir(metricsRoot); end
names = fieldnames(tables);
expectedCounts = [90,90,360,540];
for k = 1:4
    assert(height(tables.(names{k})) == expectedCounts(k));
    target = fullfile(metricsRoot,string(names{k})+".csv");
    if isfile(target)
        prior = readtable(target,'TextType','string');
        compare_tables(tables.(names{k}),prior,{});
    else
        writetable(tables.(names{k}),target);
    end
end
result = struct('status',"PASS",'signature',signature,'evaluation_units',90, ...
    'test_seconds',testSeconds,'gate_a_seconds',gateASeconds,'scientific_wall_seconds',toc(scienceTimer), ...
    'load_seconds',loadSeconds,'evaluation_seconds',evaluationSeconds, ...
    'total_load_seconds',sum(loadSeconds,'all'),'total_evaluation_seconds',sum(evaluationSeconds,'all'), ...
    'matlab_invocation_seconds',toc(overall),'matlab_version',version,'architecture',computer('arch'));
write_json(fullfile(outputRoot,"matlab_complete.json"),result);
fprintf('GATE_C_PASS cases=90\nPHASE3_2B_MATLAB_COMPLETE\n');
end

function cfg = contract(repoRoot)
protocol = jsondecode(fileread(fullfile(repoRoot,"config","phase2","static_experiment_protocol.json")));
mechanism = jsondecode(fileread(fullfile(repoRoot,"config","phase2","mechanism_analysis_protocol.json")));
cfg = struct('subjects',["subject_003","subject_008","subject_009"], ...
    'stems',["bass","vocals","drums","other"],'conditions',["colocated","moderate","wide"], ...
    'assignments',[0 0 0 0;-30 -10 10 30;-80 -30 30 80], ...
    'angles',[-80 -30 -10 0 10 30 80],'stft',protocol.stft);
assert(isequal(string(protocol.source_representation.canonical_source_order(:)).',cfg.stems));
assert(isequal(string(mechanism.frozen_inputs.source_order(:)).',cfg.stems));
assert(protocol.excerpt.frames == 1323000 && protocol.excerpt.sample_rate_hz == 44100);
assert(protocol.hrtf.elevation_deg == 0 && protocol.hrtf.maximum_direction_mismatch_deg == 1);
assert(protocol.stft.window_length_samples == 1024 && protocol.stft.hop_size_samples == 256 && protocol.stft.fft_size == 1024 && string(protocol.stft.window_type) == "periodic Hann");
for k = 1:3
    assert(string(protocol.spatial_conditions(k).condition) == cfg.conditions(k));
    assert(isequal(double(protocol.spatial_conditions(k).azimuths_deg(:)).',cfg.assignments(k,:)));
    assert(isequal(string(protocol.spatial_conditions(k).source_order(:)).',cfg.stems));
    assert(string(mechanism.frozen_inputs.canonical_conditions(k).condition) == cfg.conditions(k));
    assert(isequal(double(mechanism.frozen_inputs.canonical_conditions(k).azimuths_deg(:)).',cfg.assignments(k,:)));
end
end

function record = subject_gate(subject,subjectId,angles)
assert(subject.fs == 44100 && isequal(size(subject.hrir),[1250 2 200]));
assert(isequal(subject.receiver_order,["left","right"]));
assert(isequal(subject.receiver_positions,[0 .09 0;0 -.09 0]));
assert(isequal(subject.listener_view,[1 0 0]) && isequal(subject.listener_up,[0 0 1]));
assert(string(subject.source_position_type) == "spherical" && string(subject.receiver_position_type) == "cartesian");
assert(replace(erase(string(subject.source_position_units)," "),"metre","meter") == "degree,degree,meter");
assert(replace(string(subject.receiver_position_units),"metre","meter") == "meter");
assert(string(subject.listener_short_name) == subjectId && string(subject.database_name) == "CIPIC");
assert(string(subject.sofa_convention) == "SimpleFreeFieldHRIR" && string(subject.sofa_convention_version) == "1.0" && string(subject.data_type) == "FIR");
assert(all(isfinite(subject.delay),'all') && all(subject.delay == 0,'all'));
indices = zeros(1,7);
for k = 1:7
    match = exact_direction(subject,angles(k));
    indices(k) = match.measurement_index;
end
record = struct('subject_id',subjectId,'sample_rate_hz',subject.fs,'hrir_size',size(subject.hrir), ...
    'delay',subject.delay,'delay_interpretation',"Zero Data.Delay verified for this subject; no compensation applied", ...
    'project_azimuths_deg',angles,'indices_1based',indices,'status',"PASS");
end

function match = exact_direction(subject,angle)
positions = subject.source_positions;
target = mod(-angle,360);
candidates = find(abs(mod(positions(:,1)-target+180,360)-180) <= 1e-9 & abs(positions(:,2)) <= 1e-9);
assert(numel(candidates) == 1,'Exactly one measured direction required');
match = find_hrir_direction(subject,angle,0);
assert(match.exact_match && match.angular_mismatch_deg == 0 && match.measurement_index == candidates(1));
assert(abs(match.actual_distance_m-1) <= 1e-12);
assert(all(isfinite([match.left_hrir;match.right_hrir])) && sum(match.left_hrir.^2)>0 && sum(match.right_hrir.^2)>0);
end

function [block,audit] = evaluate_track(gt,estimate,subject,cfg,subjectId,rank,trackName,inputFrames)
errors = struct();
status = strings(4,1);
for j = 1:4
    stem = cfg.stems(j);
    assert(numel(gt.(stem)) == inputFrames && numel(estimate.(stem)) == inputFrames);
    errors.(stem) = estimate.(stem)-gt.(stem);
    status(j) = "ACTIVE";
    if sum(gt.(stem).^2) == 0, status(j) = "INACTIVE_REFERENCE"; end
end
if rank == 4
    assert(trackName == "Skelpolu - Resurrection" && status(2) == "INACTIVE_REFERENCE" && sum(estimate.vocals.^2)>0);
else
    assert(all(status == "ACTIVE"));
end
mr = cell(3,1); dr = cell(3,1); cr = cell(12,1); pr = cell(18,1); audits = cell(3,1);
for ci = 1:3
    name = cfg.conditions(ci); angles = cfg.assignments(ci,:);
    e = compute_rendered_error_components(errors,subject,name,angles,0,1);
    [oracle,ol,od] = render_stem_mix(gt,subject,name,angles,0,1);
    [estimated,el,ed] = render_stem_mix(estimate,subject,name,angles,0,1);
    expectedFrames = inputFrames+size(subject.hrir,3)-1;
    assert(isa(oracle,'double') && isa(estimated,'double') && isa(e.decomposed_residual,'double'));
    assert(isequal(size(oracle),size(estimated),size(e.decomposed_residual),[expectedFrames 2]));
    assert(all(isfinite(oracle),'all') && all(isfinite(estimated),'all'));
    assert(isequal(ol,el,e.lookups));
    assert(all([ol.angular_mismatch_deg] == 0));
    for j = 1:4
        match = exact_direction(subject,angles(j));
        assert(ol(j).measurement_index == match.measurement_index && string(ol(j).stem) == cfg.stems(j));
    end
    residual = estimated-oracle;
    directEnergy = sum(residual.^2,'all');
    assert(directEnergy > 0);
    directRelerr = sqrt(sum((residual-e.decomposed_residual).^2,'all')/directEnergy);
    assert(directRelerr <= 1e-10 && e.energy_identity_relerr <= 1e-10);
    mr{ci} = struct('subject_id',subjectId,'rank',rank,'track',trackName,'condition',name, ...
        'A_individual_error_energy',e.A_individual_error_energy,'T_total_error_energy',e.T_total_error_energy, ...
        'I_interaction_energy',e.I_interaction_energy,'error_retention_ratio',e.error_retention_ratio, ...
        'cancellation_gain_db',e.cancellation_gain_db,'direct_decomposition_relerr',directRelerr, ...
        'energy_identity_relerr',e.energy_identity_relerr,'sample_rate_hz',44100, ...
        'input_frames',inputFrames,'rendered_frames',expectedFrames);
    d = struct('subject_id',subjectId,'rank',rank,'track',trackName,'condition',name);
    metrics = compute_binaural_comparison_metrics(oracle,estimated,44100,cfg.stft);
    for field = string(fieldnames(metrics)).', d.(field) = metrics.(field); end
    d.oracle_raw_peak = od.raw_peak; d.estimated_raw_peak = ed.raw_peak;
    d.frames = expectedFrames; d.sample_rate_hz = 44100;
    dr{ci} = d;
    for j = 1:4
        cr{(ci-1)*4+j} = struct('subject_id',subjectId,'rank',rank,'track',trackName,'condition',name, ...
            'stem',cfg.stems(j),'reference_status',status(j),'rendered_error_energy',e.component_energy(j));
    end
    for j = 1:6
        pr{(ci-1)*6+j} = struct('subject_id',subjectId,'rank',rank,'track',trackName,'condition',name, ...
            'stem_i',e.pair_stem_i(j),'stem_j',e.pair_stem_j(j), ...
            'interaction_energy',e.pair_interaction_energy(j),'normalized_interaction',e.pair_normalized_interaction(j), ...
            'cosine_alignment',e.pair_cosine_alignment(j),'cosine_status',e.pair_cosine_status(j));
    end
    audits{ci} = struct('condition',name,'input_frames',inputFrames,'rendered_frames',expectedFrames, ...
        'sample_rate_hz',44100,'channel_order',["left","right"],'finite_double',true, ...
        'oracle_peak',od.raw_peak,'estimated_peak',ed.raw_peak,'residual_peak',max(abs(residual),[],'all'), ...
        'oracle_headroom_db',-20*log10(od.raw_peak),'estimated_headroom_db',-20*log10(ed.raw_peak), ...
        'oracle_clipping_risk',od.raw_peak>1,'estimated_clipping_risk',ed.raw_peak>1, ...
        'direct_decomposition_relerr',directRelerr,'energy_identity_relerr',e.energy_identity_relerr,'lookups',ol);
end
block = struct('mechanism',struct2table(vertcat(mr{:})),'downstream',struct2table(vertcat(dr{:})), ...
    'components',struct2table(vertcat(cr{:})),'pairs',struct2table(vertcat(pr{:})));
audit = struct('status',"PASS",'subject_id',subjectId,'rank',rank,'track',trackName,'conditions',vertcat(audits{:}));
end

function validate_block(block,cfg,subjectId,rank,trackName,schemas)
names = fieldnames(block); counts = [3 3 12 18];
for k = 1:4
    t = block.(names{k});
    assert(height(t) == counts(k));
    assert(isequal(string(t.Properties.VariableNames),["subject_id",string(schemas.(names{k})(:)).']));
    assert(all(string(t.subject_id) == subjectId) && all(t.rank == rank) && all(string(t.track) == trackName));
    perCondition = counts(k)/3;
    assert(isequal(string(t.condition),repelem(cfg.conditions.',perCondition)));
    for col = string(t.Properties.VariableNames)
        values = t.(col);
        if isnumeric(values) && col ~= "cosine_alignment", assert(all(isfinite(values),'all')); end
    end
end
assert(isequal(string(block.components.stem),repmat(cfg.stems.',3,1)));
assert(all(block.mechanism.A_individual_error_energy>0) && all(block.mechanism.T_total_error_energy>0));
assert(all(block.mechanism.direct_decomposition_relerr<=1e-10) && all(block.mechanism.energy_identity_relerr<=1e-10));
end

function output = combine_blocks(blocks)
output = blocks{1}; names = fieldnames(output);
for j = 1:numel(names)
    cells = cellfun(@(b)b.(names{j}),blocks,'UniformOutput',false);
    output.(names{j}) = vertcat(cells{:});
end
end

function block = read_block(folder)
block = struct();
for name = ["mechanism","downstream","components","pairs"]
    block.(name) = readtable(fullfile(folder,name+".csv"),'TextType','string');
end
end

function report = baseline_regression(block,repoRoot,paths)
names = fieldnames(block); reports = cell(4,1);
for k = 1:4
    current = removevars(block.(names{k}),'subject_id');
    baseline = readtable(fullfile(repoRoot,string(paths.(names{k}))),'TextType','string');
    keys = {'rank','track','condition'};
    if names{k} == "components", keys = [keys,{'stem'}]; end
    if names{k} == "pairs", keys = [keys,{'stem_i','stem_j'}]; end
    reports{k} = compare_tables(current,baseline,keys);
    reports{k}.table = names{k};
end
report = struct('status',"PASS",'cases',30,'tolerance',"abs(new-old) <= 1e-10*max(1,abs(old))", ...
    'tables',vertcat(reports{:}),'max_scaled_difference',max(cellfun(@(r)r.max_scaled_difference,reports)));
end

function report = compare_tables(current,baseline,keys)
assert(height(current) == height(baseline) && isequal(current.Properties.VariableNames,baseline.Properties.VariableNames),'Baseline schema/rows');
if ~isempty(keys)
    current = sortrows(current,keys); baseline = sortrows(baseline,keys);
    assert(height(unique(current(:,keys),'rows')) == height(current));
    assert(isequal(current(:,keys),baseline(:,keys)),'Baseline keys');
end
columns = {};
for field = string(current.Properties.VariableNames)
    a = current.(field); b = baseline.(field);
    if isnumeric(a)
        assert(all(isfinite(a)) && all(isfinite(b)),'Nonfinite regression value');
        if ismember(field,["rank","sample_rate_hz","frames","input_frames","rendered_frames"])
            assert(isequal(a,b),'Discrete regression mismatch');
        end
        difference = abs(a-b); scaled = difference./max(1,abs(b));
        assert(all(scaled<=1e-10),'003 regression failed: %s',field);
        relative = zeros(size(a)); nz = b~=0;
        relative(nz) = difference(nz)./abs(b(nz));
        columns{end+1} = struct('column',field,'max_absolute_difference',max(difference), ...
            'max_relative_difference_nonzero_baseline',max(relative), ...
            'max_absolute_difference_at_zero_baseline',max([0;difference(~nz)]), ...
            'max_scaled_difference',max(scaled)); %#ok<AGROW>
    else
        assert(isequal(string(a),string(b)),'Discrete/text regression mismatch');
    end
end
columns = vertcat(columns{:});
report = struct('rows',height(current),'max_absolute_difference',max([columns.max_absolute_difference]), ...
    'max_relative_difference_nonzero_baseline',max([columns.max_relative_difference_nonzero_baseline]), ...
    'max_scaled_difference',max([columns.max_scaled_difference]),'columns',columns);
end

function wrapper_test(cfg)
assert(isequal(cfg.subjects,["subject_003","subject_008","subject_009"]));
assert(isequal(cfg.stems,["bass","vocals","drums","other"]));
assert(isequal(cfg.conditions,["colocated","moderate","wide"]));
subject = struct('hrir',zeros(7,2,3),'source_positions',[mod(-cfg.angles(:),360),zeros(7,1),ones(7,1)],'receiver_order',["left","right"]);
for k = 1:7
    subject.hrir(k,1,:) = [1+.03*k,.1,-.02]; subject.hrir(k,2,:) = [.8+.01*k,-.1,.02];
    match = exact_direction(subject,cfg.angles(k)); assert(match.measurement_index == k);
end
duplicate = subject; duplicate.source_positions(2,:) = duplicate.source_positions(1,:);
failed = false; try, exact_direction(duplicate,cfg.angles(1)); catch, failed = true; end
assert(failed,'Duplicate direction must be rejected');
failed = false; try, exact_direction(subject,5); catch, failed = true; end
assert(failed,'Nearest-only direction must be rejected');
n = (0:2047).'; gt = struct(); estimate = struct();
for k = 1:4
    stem = cfg.stems(k); gt.(stem) = .1*cos((k+1)*n/40);
    estimate.(stem) = gt.(stem)+.01*sin((k+2)*n/31);
end
[block,audit] = evaluate_track(gt,estimate,subject,cfg,"synthetic",1,"synthetic",2048);
assert(height(block.mechanism)==3 && height(block.downstream)==3 && height(block.components)==12 && height(block.pairs)==18);
assert(isequal(block.mechanism.condition,cfg.conditions.'));
assert(isequal(block.components.stem,repmat(cfg.stems.',3,1)));
assert(all([audit.conditions.direct_decomposition_relerr]<=1e-10));
fprintf('PHASE3_2B_WRAPPER_SYNTHETIC_PASS\n');
end

function run_test(file)
run(file);
end

function value = file_hash(file)
fid = fopen(file,'rb'); assert(fid>=0,'Cannot open %s',file);
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
digest = java.security.MessageDigest.getInstance('SHA-256');
while true
    bytes = fread(fid,1024*1024,'*uint8'); if isempty(bytes), break; end
    digest.update(bytes);
end
value = string(lower(reshape(dec2hex(typecast(digest.digest(),'uint8'),2).',1,[])));
end

function write_json(file,value)
temporary = file + ".tmp";
fid = fopen(temporary,'w'); assert(fid>=0);
fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true)); fclose(fid);
[ok,msg] = movefile(temporary,file,'f'); assert(ok,msg);
end

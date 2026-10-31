classdef Phase4MusicImport < handle
    %PHASE4MUSICIMPORT MATLAB decoding and a polled, shell-free Python worker.
    properties (SetAccess=private)
        root
        jobDir = ''
        process = []
        songName = ''
        sourceInfo
        started
        progressState
    end
    methods
        function obj=Phase4MusicImport(root), obj.root=root; end
        function start(obj,file,python)
            assert(isempty(obj.process),'An import is already running.');
            [~,name,ext]=fileparts(file);
            assert(ismember(lower(ext),{'.wav','.mp3'}), ...
                'ELEC5305:Import:Format','Choose a WAV or MP3 file.');
            assert(isfile(file),'ELEC5305:Import:Missing','Audio file does not exist.');
            assert(isfile(python),'ELEC5305:Import:Python', ...
                'Python environment not found. Set PythonExecutable to the existing elec5305 Python.');
            obj.songName=[name ext]; obj.sourceInfo=audioinfo(file);
            info=obj.sourceInfo;
            assert(ismember(info.NumChannels,[1 2]) && info.TotalSamples>=2 && ...
                info.SampleRate>0,'ELEC5305:Import:Audio', ...
                'Audio must be nonempty mono or stereo. Multichannel files are not supported.');
            [audio,fs]=audioread(file);
            assert(size(audio,2)==info.NumChannels && all(isfinite(audio),'all'), ...
                'ELEC5305:Import:Audio','Audio decoder returned invalid samples.');
            originalHash=Phase4MusicImport.sha256(file);
            if size(audio,2)==1, audio=[audio audio]; end
            if fs~=44100, audio=resample(audio,44100,fs); end
            assert(all(isfinite(audio),'all'),'ELEC5305:Import:Range','Nonfinite resampled audio.');
            % Resampling can overshoot unity. One documented common input gain
            % avoids PCM clipping without changing relative channels/stem gains.
            peak=max(abs(audio),[],'all'); inputGain=1;
            if peak>1, inputGain=(1-1e-7)/peak; audio=audio*inputGain; end
            jobs=fullfile(obj.root,'outputs','phase4','import_jobs');
            if ~isfolder(jobs), mkdir(jobs); end
            obj.jobDir=tempname(jobs); mkdir(obj.jobDir);
            prepared=fullfile(obj.jobDir,'input.wav');
            audiowrite(prepared,audio,44100,'BitsPerSample',32);
            request=struct('song_name',obj.songName,'original_path',file, ...
                'original_sha256',originalHash,'prepared_path',prepared, ...
                'preparation',struct('matlab_release',version('-release'), ...
                'source_sample_rate',fs,'source_channels',info.NumChannels, ...
                'source_frames',size_from_info(info),'prepared_frames',size(audio,1), ...
                'sample_rate',44100,'channels',2,'bits',32));
            if inputGain~=1, request.preparation.shared_input_gain=inputGain; end
            requestFile=fullfile(obj.jobDir,'request.json');
            fid=fopen(requestFile,'w','n','UTF-8');
            assert(fid>=0,'Cannot write import request.');
            fprintf(fid,'%s',jsonencode(request)); fclose(fid);
            obj.launch(requestFile,python);
        end
        function launch(obj,requestFile,python)
            % Also permits direct process/result-contract validation with a private request.
            assert(isempty(obj.process),'An import is already running.');
            obj.jobDir=fileparts(requestFile);
            assert(ispc,'ELEC5305:Import:Platform','The process launcher currently supports Windows.');
            psi=System.Diagnostics.ProcessStartInfo;
            psi.FileName=python; psi.UseShellExecute=false; psi.CreateNoWindow=true;
            psi.WorkingDirectory=obj.root;
            worker=fullfile(obj.root,'scripts','python','phase4','separate_music_progress.py');
            % These are generated file paths, not interpolated user arguments.
            psi.Arguments=sprintf('-B "%s" --request "%s"',worker,requestFile);
            obj.started=tic;
            obj.progressState=struct('stage','Starting worker / checking cache', ...
                'indeterminate',true,'percent',NaN);
            obj.process=System.Diagnostics.Process.Start(psi);
        end
        function state=progress(obj)
            state=obj.progressState;
            files=dir(fullfile(obj.jobDir,'progress_*.json'));
            if ~isempty(files)
                [~,order]=sort({files.name}); file=fullfile(obj.jobDir,files(order(end)).name);
                try
                    next=jsondecode(fileread(file));
                    if isfield(next,'stage') && isfield(next,'indeterminate') && isfield(next,'percent')
                        obj.progressState=next; state=next;
                    end
                catch
                    % Atomic replacement can briefly race Windows readers.
                    % Keep the last valid state, never manufacture a percent.
                end
            end
            state.elapsed_seconds=toc(obj.started);
        end
        function [done,result]=poll(obj)
            done=~isempty(obj.process) && obj.process.HasExited; result=[];
            if ~done, return; end
            code=obj.process.ExitCode; obj.process.Dispose(); obj.process=[];
            file=fullfile(obj.jobDir,'result.json');
            assert(isfile(file),'ELEC5305:Import:Worker', ...
                'Python exited (%d) without a result. Check %s',code,fullfile(obj.jobDir,'python.log'));
            result=jsondecode(fileread(file));
            assert(code==0 && strcmp(result.status,'complete'),'ELEC5305:Import:Worker', ...
                'Separation failed. %s Log: %s',message_or_empty(result),fullfile(obj.jobDir,'python.log'));
        end
        function cancel(obj)
            if isempty(obj.process), return; end
            if ~obj.process.HasExited, obj.process.Kill(); obj.process.WaitForExit(5000); end
            obj.process.Dispose(); obj.process=[];
        end
        function delete(obj), obj.cancel(); end
    end
    methods (Static)
        function d=loadStems(d,result)
            r=result.record; names={'vocals','drums','bass','other'};
            assert(strcmp(r.status,'complete') && strcmp(r.model,'htdemucs_ft') && ...
                isequal(string(r.source_order(:)),string(names(:))) && r.frames>=2 && ...
                r.sample_rate==d.fs && r.channels==2 && r.all_finite, ...
                'ELEC5305:Import:Cache','Invalid separation completion record.');
            d.stems=zeros(r.frames,4); inputs=struct([]);
            for s=1:4
                file=fullfile(result.cache_dir,[names{s} '.wav']);
                assert(strcmpi(Phase4MusicImport.sha256(file),r.stems.(names{s}).sha256), ...
                    'ELEC5305:Import:Cache','Stem hash mismatch: %s',file);
                info=audioinfo(file); [x,fs]=audioread(file);
                assert(fs==d.fs && size(x,1)==r.frames && size(x,2)==2 && ...
                    info.BitsPerSample==32 && all(isfinite(x),'all'), ...
                    'ELEC5305:Import:Cache','Invalid stem format or samples: %s',file);
                x=mean(x,2); d.stems(:,s)=x;
                inputs(s).stem=names{s}; inputs(s).path=file;
                inputs(s).frames=r.frames; inputs(s).input_peak=max(abs(x));
                inputs(s).model=r.model; inputs(s).cache_sha256=r.stems.(names{s}).sha256;
            end
            d.stem_names=names; d.input=inputs;
            d.mix_bound_before_gain=max(sum(abs(d.bank),1),[],'all')*sum([inputs.input_peak]);
            d.gain=min(.25,.5/max(d.mix_bound_before_gain,eps));
            n=min(d.fade_samples,floor(r.frames/2)); envelope=(0:n-1)'/max(1,n-1);
            d.stems(1:n,:)=d.stems(1:n,:).*envelope;
            d.stems(end-n+1:end,:)=d.stems(end-n+1:end,:).*flipud(envelope);
            d.alignment=struct('sample_rate',d.fs,'frames',r.frames, ...
                'downmix','0.5*(left+right)','shared_timeline',true, ...
                'cache_key',r.cache_key,'cache_hit',result.cache_hit);
        end
        function hash=sha256(file)
            digest=java.security.MessageDigest.getInstance('SHA-256');
            fid=fopen(file,'rb'); assert(fid>=0,'Cannot read file: %s',file);
            cleanup=onCleanup(@() fclose(fid)); %#ok<NASGU>
            while ~feof(fid), digest.update(fread(fid,1048576,'*uint8')); end
            hash=lower(reshape(dec2hex(typecast(digest.digest(),'uint8'),2).',1,[]));
        end
    end
end

function n=size_from_info(info), n=info.TotalSamples; end
function msg=message_or_empty(result)
msg=''; if isfield(result,'message'), msg=result.message; end
end

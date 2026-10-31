classdef Phase4WavExport
    % Static one-pass export. No writer, live handle, separator or Auto clock.
    methods (Static)
        function settings=snapshot(engine,master,motion)
            settings=struct('angles',engine.targets,'muted',engine.muted, ...
                'solo',engine.solo,'volume_percent',master.percent, ...
                'auto_enabled_at_click',motion.enabled,'auto_policy','static click-time angles');
        end
        function [audio,record]=render(d,settings,progress)
            if nargin<3, progress=@(~,~) []; end
            assert(d.fs==44100 && size(d.stems,2)==4 && size(d.stems,1)>=2);
            assert(all(isfinite(d.stems),'all') && all(isfinite(d.bank),'all') && ...
                isscalar(d.gain) && isfinite(d.gain) && d.gain>0);
            assert(isequal(size(settings.angles),[1 4]) && all(isfinite(settings.angles)) && ...
                all(abs(settings.angles)<=80) && isequal(size(settings.muted),[1 4]) && isequal(size(settings.solo),[1 4]));
            master=Phase4MasterGain(d.fs,settings.volume_percent); master.reset();
            audible=~logical(settings.muted) & (~any(settings.solo) | logical(settings.solo));
            peaks=max(abs(d.stems),[],1);
            preMasterBound=d.gain*max(sum(abs(d.bank),1),[],'all')*sum(peaks(audible));
            % One shared conservative factor protects both the unchanged mixer
            % integrity gate and the final PCM signal. Never hard-clip samples.
            safety=min([1,.98/max(preMasterBound,eps),.98/max(preMasterBound*master.current,eps)]);
            local=d; local.gain=d.gain*safety; mixer=Phase4Mixer(local);
            for s=1:4
                mixer.setTarget(s,settings.angles(s));
                mixer.setMute(s,settings.muted(s)); mixer.setSolo(s,settings.solo(s));
            end
            mixer.reset(); % Fresh histories and static gates/HRIRs from sample 1.
            N=size(d.stems,1); B=1024; audio=zeros(N,2); progress(0,'Rendering');
            for first=1:B:N
                last=min(first+B-1,N); x=d.stems(first:last,:);
                % Match the existing realtime Play-from-start input fade.
                ramp=min((first:last)'/d.fade_samples,1); x=x.*ramp;
                audio(first:last,:)=master.step(mixer.step(x));
                progress(last/N,'Rendering');
            end
            peak=max(abs(audio),[],'all');
            assert(all(isfinite(audio),'all') && peak<1);
            record=struct('status','rendered','version',version, ...
                'timestamp',char(datetime('now',TimeZone='Australia/Sydney')), ...
                'settings',settings,'selected_angles',mixer.selectedAngles,'audible',audible, ...
                'sample_rate',d.fs,'channels',2,'channel_order','left,right','frames',N, ...
                'duration_seconds',N/d.fs,'bits_per_sample',24,'block_size',B, ...
                'master_gain',master.current,'master_mapping','1.25*(percent/100)^2', ...
                'original_mix_gain',d.gain,'safety_gain',safety,'effective_mix_gain',local.gain, ...
                'pre_safety_bound',preMasterBound*master.current, ...
                'conservative_output_bound',preMasterBound*master.current*safety, ...
                'render_peak',peak,'all_samples_finite',true,'clipped_samples',0, ...
                'hrtf','CIPIC subject_003, elevation 0, nearest measured azimuth', ...
                'hrir_samples',size(d.bank,1),'start_policy','song beginning; same Play input fade', ...
                'end_policy','exact input frames; causal FIR tail beyond song duration omitted', ...
                'input',d.input,'alignment',d.alignment);
        end
        function record=write(file,audio,record,overwriteConfirmed,progress)
            if nargin<4, overwriteConfirmed=false; end
            if nargin<5, progress=@(~,~) []; end
            [folder,~,extension]=fileparts(file);
            assert(strcmpi(extension,'.wav'),'ELEC5305:Export:Extension','Choose a .wav output file.');
            if isempty(folder), folder=pwd; file=fullfile(folder,file); end
            assert(isfolder(folder),'ELEC5305:Export:Directory','Output folder does not exist.');
            assert(~isfile(file) || overwriteConfirmed,'ELEC5305:Export:Exists','Output already exists; explicit overwrite confirmation is required.');
            assert(isequal(size(audio),[record.frames 2]) && all(isfinite(audio),'all') && ...
                max(abs(audio),[],'all')<1,'ELEC5305:Export:Integrity','Invalid final export samples.');
            temporary=[tempname(folder) '.wav']; cleanup=onCleanup(@() removeTemporary(temporary)); %#ok<NASGU>
            progress(NaN,'Writing 24-bit WAV');
            audiowrite(temporary,audio,record.sample_rate,'BitsPerSample',24);
            info=audioinfo(temporary);
            assert(info.SampleRate==44100 && info.NumChannels==2 && info.BitsPerSample==24 && ...
                info.TotalSamples==record.frames,'ELEC5305:Export:Format','Written WAV format mismatch.');
            peak=0; error=0; clipped=0; B=65536;
            for first=1:B:record.frames
                last=min(first+B-1,record.frames);
                [check,fs]=audioread(temporary,[first last]);
                assert(fs==44100 && all(isfinite(check),'all'));
                peak=max(peak,max(abs(check),[],'all')); clipped=clipped+nnz(abs(check)>=1);
                error=max(error,max(abs(check-audio(first:last,:)),[],'all'));
                progress(last/record.frames,'Verifying WAV');
            end
            assert(clipped==0 && error<=2^-23+1e-14,'ELEC5305:Export:PCM','WAV clipping or excessive PCM quantization error.');
            progress(NaN,'Saving WAV');
            % Java move without REPLACE refuses a raced-in existing file.
            % REPLACE is used only after the UI's native overwrite confirmation.
            options=javaArray('java.nio.file.CopyOption',double(overwriteConfirmed));
            if overwriteConfirmed, options(1)=java.nio.file.StandardCopyOption.REPLACE_EXISTING; end
            source=java.io.File(temporary); target=java.io.File(file);
            java.nio.file.Files.move(source.toPath(),target.toPath(),options);
            record.status='complete'; record.output_path=file;
            record.written_peak=peak; record.quantization_max_error=error;
            record.clipped_samples=clipped; record.overwrite_confirmed=overwriteConfirmed;
            progress(1,'Export complete');
        end
    end
end

function removeTemporary(file)
% Only the unique scratch file owned by this export is eligible for cleanup.
if isfile(file), delete(file); end
end

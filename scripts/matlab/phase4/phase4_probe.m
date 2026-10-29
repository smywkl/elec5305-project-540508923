function phase4_probe(outputDir)
%PHASE4_PROBE Read-only runtime/device audit and isolated graphics smoke.
if ~isfolder(outputDir), mkdir(outputDir); end
diary(fullfile(outputDir,'probe.log')); cleanup = onCleanup(@() diary('off')); %#ok<NASGU>
fprintf('VERSION=%s ARCH=%s PREFDIR=%s\n',version,computer('arch'),prefdir);
assert(sum((1:10).^2)==385);
env.version=version; env.arch=computer('arch'); env.toolboxes=ver;
names={'audioDeviceWriter','interpolateHRTF','uislider','sofaread'};
for k=1:numel(names)
    env.functions.(names{k})=which(names{k});
    fprintf('%s=%s\n',names{k},which(names{k}));
end
f=figure('Visible','off'); plot(0:10,(0:10).^2); title('Phase 4 runtime smoke');
xlabel('Input'); ylabel('Squared value'); exportgraphics(f,fullfile(outputDir,'smoke.png')); close(f);
f=uifigure('Visible','off'); s=uislider(f); env.ValueChangingFcn=isprop(s,'ValueChangingFcn'); delete(f);
drivers={'DirectSound','WASAPI','ASIO'};
for k=1:numel(drivers)
    d=drivers{k}; w=[];
    try
        w=audioDeviceWriter('Driver',d,'SampleRate',44100);
        env.devices.(d)=getAudioDevices(w);
        fprintf('DRIVER %s: %s\n',d,strjoin(string(env.devices.(d)),' | '));
        release(w);
    catch ME
        env.device_errors.(d)=struct('identifier',ME.identifier,'message',ME.message);
        fprintf('DRIVER %s ERROR %s: %s\n',d,ME.identifier,ME.message);
        if ~isempty(w), release(w); end
    end
end
fid=fopen(fullfile(outputDir,'environment.json'),'w'); fprintf(fid,'%s',jsonencode(env,PrettyPrint=true)); fclose(fid);
fprintf('PHASE4_PROBE_PASS\n');
end

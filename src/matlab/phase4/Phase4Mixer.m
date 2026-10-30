classdef Phase4Mixer < handle
    %PHASE4MIXER Four independent Phase4FIR states; one fixed-gain stereo sum.
    % Mute dominates Solo; any Solo enables only soloed, unmuted sources.
    % All FIRs run while muted. Output gates ramp over 20 ms; no normalization.
    properties (SetAccess=private)
        engines
        bank
        angles
        fadeSamples
        gain
        targets = [0 -45 0 45]
        selectedAngles
        muted = false(1,4)
        solo = false(1,4)
        gate
    end
    methods
        function obj=Phase4Mixer(d)
            obj.bank=d.bank; obj.angles=d.angles;
            obj.fadeSamples=d.fade_samples; obj.gain=d.gain;
            obj.reset();
        end
        function setTarget(obj,s,angle)
            assert(ismember(s,1:4) && isscalar(angle) && isfinite(angle));
            obj.targets(s)=max(-80,min(80,angle));
        end
        function setMute(obj,s,value), obj.muted(s)=logical(value); end
        function setSolo(obj,s,value), obj.solo(s)=logical(value); end
        function mask=audible(obj)
            mask=~obj.muted & (~any(obj.solo) | obj.solo);
        end
        function reset(obj)
            obj.engines=cell(1,4); obj.selectedAngles=zeros(1,4);
            for s=1:4
                [~,idx]=min(abs(obj.angles-obj.targets(s)));
                obj.engines{s}=Phase4FIR(obj.bank,idx,obj.fadeSamples);
                obj.selectedAngles(s)=obj.angles(idx);
            end
            obj.gate=double(obj.audible());
        end
        function [mix,stereo]=step(obj,x)
            assert(size(x,2)==4 && all(isfinite(x),'all'));
            N=size(x,1); mix=zeros(N,2);
            if nargout>1, stereo=zeros(N,2,4); end
            mask=double(obj.audible());
            for s=1:4
                [~,idx]=min(abs(obj.angles-obj.targets(s)));
                y=obj.engines{s}.step(x(:,s),obj.bank,idx);
                obj.selectedAngles(s)=obj.angles(idx);
                delta=mask(s)-obj.gate(s);
                envelope=obj.gate(s)+sign(delta)*min((1:N)'/obj.fadeSamples,abs(delta));
                obj.gate(s)=envelope(end);
                y=y.*envelope;
                if nargout>1, stereo(:,:,s)=y; end
                mix=mix+y;
            end
            mix=obj.gain*mix;
            assert(size(mix,2)==2 && all(isfinite(mix),'all') && max(abs(mix),[],'all')<1, ...
                'ELEC5305:Phase4:Integrity','Mix must be finite, stereo [left,right], and unclipped.');
        end
    end
end

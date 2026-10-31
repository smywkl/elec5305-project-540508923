classdef Phase4MasterGain < handle
    % One post-mix gain envelope; never changes the four FIR states.
    % 25% gain increase over 4.3a, with the same 40 ms full-scale slew.
    properties (Constant)
        maxGain = 1.25
    end
    properties (SetAccess=private)
        percent
        current
        rampSamples
    end
    methods
        function obj=Phase4MasterGain(fs,percent)
            obj.rampSamples=round(.04*fs);
            obj.setPercent(percent); obj.reset();
        end
        function setPercent(obj,value)
            assert(isscalar(value) && isfinite(value));
            obj.percent=max(0,min(100,value));
        end
        function reset(obj)
            % Playback already has its existing input fade-in.
            obj.current=obj.maxGain*(obj.percent/100)^2;
        end
        function [y,envelope]=step(obj,x)
            target=obj.maxGain*(obj.percent/100)^2; delta=target-obj.current;
            envelope=obj.current+sign(delta)*min(obj.maxGain*(1:size(x,1))'/obj.rampSamples,abs(delta));
            obj.current=envelope(end); y=x.*envelope;
            assert(all(isfinite(y),'all') && max(abs(y),[],'all')<1, ...
                'ELEC5305:Phase4:MasterIntegrity','Final stereo mix must be finite and unclipped.');
        end
    end
end

classdef Phase4MasterGain < handle
    % One post-mix attenuation envelope; never changes the four FIR states.
    % Quadratic 0..100% mapping, unity ceiling, 40 ms full-scale slew.
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
            obj.current=(obj.percent/100)^2;
        end
        function [y,envelope]=step(obj,x)
            target=(obj.percent/100)^2; delta=target-obj.current;
            envelope=obj.current+sign(delta)*min((1:size(x,1))'/obj.rampSamples,abs(delta));
            obj.current=envelope(end); y=x.*envelope;
        end
    end
end

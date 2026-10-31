classdef Phase4AutoMotion < handle
    % Independent per-source sample clocks; no FIR or UI ownership.
    properties (SetAccess=private)
        enabled = false(1,4)
        origins = zeros(1,4)
        samples = zeros(1,4)
        fs
        speed = 12
    end
    methods
        function obj=Phase4AutoMotion(fs), obj.fs=fs; end
        function setEnabled(obj,s,value,currentAngle)
            value=logical(value);
            if value && ~obj.enabled(s)
                obj.origins(s)=currentAngle; obj.samples(s)=0;
            end
            obj.enabled(s)=value;
        end
        function values=angles(obj)
            values=zeros(1,4);
            for s=1:4
                values(s)=phase4_pingpong(obj.origins(s),obj.samples(s),obj.fs,obj.speed);
            end
        end
        function advance(obj,count)
            obj.samples(obj.enabled)=obj.samples(obj.enabled)+count;
        end
        function stop(obj)
            % Hold current direction; Stop unchecks Auto. Recheck starts here.
            obj.enabled(:)=false;
        end
    end
end

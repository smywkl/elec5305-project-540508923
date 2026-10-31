classdef Phase4StageProjection
    % Elliptical ground-plane view from behind/above the listener.
    % Only graphics use this projection; audio still receives azimuth only.
    properties (Constant)
        depthScale = .58
    end
    methods (Static)
        function [x,y]=project(angle,radius)
            if nargin<2, radius=1; end
            x=radius.*sind(angle); y=Phase4StageProjection.depthScale*radius.*cosd(angle);
        end
        function angle=unproject(x,y)
            angle=max(-80,min(80,atan2d(x,y/Phase4StageProjection.depthScale)));
        end
        function radius=logicalRadius(x,y)
            radius=hypot(x,y/Phase4StageProjection.depthScale);
        end
    end
end

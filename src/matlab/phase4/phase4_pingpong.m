function angle=phase4_pingpong(startAngle,samples,fs,speed)
%PHASE4_PINGPONG Sample-clock triangular azimuth, initially toward +80 deg.
% Pure function for realtime and future offline use. Samples may be a vector.
arguments
    startAngle (1,1) double {mustBeFinite,mustBeInRange(startAngle,-80,80)}
    samples double {mustBeFinite,mustBeNonnegative}
    fs (1,1) double {mustBePositive}
    speed (1,1) double {mustBePositive} = 12
end
angle=80-abs(mod(startAngle+80+speed*samples/fs,320)-160);
end

classdef Phase4FIR < handle
    %PHASE4FIR Stateful direct FIR with shared input history and output crossfade.
    % No STFT/windows/OLA. New filters see the complete L-1 sample history.
    properties (SetAccess=private)
        history
        current
        target
        remaining=0
        fadeSamples
        index
    end
    methods
        function obj=Phase4FIR(bank,index,fadeSamples)
            obj.current=bank(:,:,index); obj.target=obj.current;
            obj.history=zeros(size(bank,1)-1,1);
            obj.index=index; obj.fadeSamples=fadeSamples;
        end
        function y=step(obj,x,bank,index)
            if index~=obj.index
                obj.target=bank(:,:,index); obj.index=index;
                obj.remaining=obj.fadeSamples;
            end
            extended=[obj.history;x(:)]; N=numel(x);
            y0=zeros(N,2);
            for ear=1:2, y0(:,ear)=conv(extended,obj.current(:,ear),'valid'); end
            if obj.remaining>0
                y1=zeros(N,2);
                for ear=1:2, y1(:,ear)=conv(extended,obj.target(:,ear),'valid'); end
                alpha=min((1:N)'/obj.remaining,1);
                y=(1-alpha).*y0+alpha.*y1;
                obj.current=(1-alpha(end))*obj.current+alpha(end)*obj.target;
                obj.remaining=max(0,obj.remaining-N);
            else
                y=y0;
            end
            obj.history=extended(end-numel(obj.history)+1:end);
        end
    end
end

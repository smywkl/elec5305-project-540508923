classdef Phase4StudioView < handle
    % Spatial Studio presentation and pointer handling; no audio processing.
    properties
        figure
        sliders
        labels
        mutes
        solos
        sourceButtons
        axes
        rays
        markers
        selectionRing
        playButton
        pauseButton
        stopButton
        loadButton
        songLabel
        status
        volumeSlider
        volumeLabel
        progress
        progressFill
        timeLabel
        onAngle = []
        onControl = []
        onVolume = []
    end
    properties (SetAccess=private)
        selected = 1
        dragging = 0
        targets = [0 -45 0 45]
        colours = [.30 .65 1;1 .57 .25;.35 .82 .57;.73 .52 1]
    end
    methods
        function obj=Phase4StudioView(visible,customMusic)
            bg=[.055 .071 .10]; panel=[.085 .105 .145]; fg=[.91 .94 .99]; muted=[.57 .64 .74];
            f=uifigure('Name','ELEC5305 | Spatial Studio','Position',[80 60 1180 780], ...
                'AutoResizeChildren','off','Color',bg,'Visible',matlab.lang.OnOffSwitchState(visible)); obj.figure=f;
            if isprop(f,'Theme'), f.Theme='dark'; end
            f.SizeChangedFcn=@(~,~) obj.minimumSize();
            g=uigridlayout(f,[3 1],'RowHeight',{84,'1x',144},'Padding',[24 16 24 16], ...
                'RowSpacing',16,'BackgroundColor',bg);
            head=uigridlayout(g,[2 2],'RowHeight',{36,28},'ColumnWidth',{'1x',250}, ...
                'Padding',0,'BackgroundColor',bg);
            uilabel(head,'Text','SPATIAL STUDIO','FontName','Segoe UI','FontSize',27,'FontWeight','bold','FontColor',fg);
            badge=uilabel(head,'Text','ELEC5305  /  BINAURAL','FontColor',muted,'HorizontalAlignment','right');
            badge.Layout.Row=1; badge.Layout.Column=2;
            obj.songLabel=uilabel(head,'Text','Load a song to begin','FontSize',14,'FontColor',fg);
            obj.status=uilabel(head,'Text','Ready','FontColor',muted,'HorizontalAlignment','right');
            body=uigridlayout(g,[1 2],'ColumnWidth',{420,'1x'},'Padding',0,'ColumnSpacing',18,'BackgroundColor',bg);
            left=uigridlayout(body,[5 1],'RowHeight',{28,'1x','1x','1x','1x'}, ...
                'Padding',0,'RowSpacing',12,'BackgroundColor',bg);
            uilabel(left,'Text','STEMS  /  DIRECTION','FontSize',12,'FontWeight','bold','FontColor',muted);
            names={'Vocals','Drums','Bass','Other'};
            obj.sliders=gobjects(1,4); obj.labels=gobjects(1,4); obj.mutes=gobjects(1,4);
            obj.solos=gobjects(1,4); obj.sourceButtons=gobjects(1,4);
            for s=1:4
                card=uipanel(left,'BackgroundColor',panel,'BorderType','none');
                c=uigridlayout(card,[3 4],'RowHeight',{27,18,'1x'},'ColumnWidth',{112,'1x',65,61}, ...
                    'Padding',[14 8 14 6],'RowSpacing',2,'ColumnSpacing',5,'BackgroundColor',panel);
                obj.sourceButtons(s)=uibutton(c,'Text',names{s},'FontWeight','bold','FontSize',14, ...
                    'FontColor',obj.colours(s,:),'BackgroundColor',panel,'ButtonPushedFcn',@(~,~) obj.selectStem(s));
                obj.labels(s)=uilabel(c,'FontColor',fg,'HorizontalAlignment','right','FontSize',12);
                obj.mutes(s)=uicheckbox(c,'Text','Mute','FontColor',muted, ...
                    'ValueChangedFcn',@(h,~) obj.control(s,1,h.Value));
                obj.solos(s)=uicheckbox(c,'Text','Solo','FontColor',muted, ...
                    'ValueChangedFcn',@(h,~) obj.control(s,2,h.Value));
                note=uilabel(c,'Text','LEFT  -80                              0                              +80  RIGHT', ...
                    'FontColor',muted,'FontSize',9); note.Layout.Row=2; note.Layout.Column=[1 4];
                obj.sliders(s)=uislider(c,'Limits',[-80 80],'Value',obj.targets(s), ...
                    'MajorTicks',[],'MinorTicks',[],'FontColor',muted);
                obj.sliders(s).Layout.Row=3; obj.sliders(s).Layout.Column=[1 4];
                obj.sliders(s).ValueChangingFcn=@(~,e) obj.angle(s,e.Value,1);
                obj.sliders(s).ValueChangedFcn=@(h,~) obj.angle(s,h.Value,2);
            end
            space=uipanel(body,'BackgroundColor',panel,'BorderType','none');
            sg=uigridlayout(space,[4 1],'RowHeight',{30,'1x',26,24},'Padding',[16 12 16 12], ...
                'RowSpacing',4,'BackgroundColor',panel);
            uilabel(sg,'Text','SOUND STAGE','FontColor',fg,'FontSize',14,'FontWeight','bold');
            ax=uiaxes(sg,'Color',panel,'XColor',panel,'YColor',panel,'Box','off'); obj.axes=ax;
            hold(ax,'on'); disableDefaultInteractivity(ax); ax.Interactions=[]; ax.Toolbar.Visible='off';
            ax.XLim=[-1.28 1.28]; ax.YLim=[-.27 1.34]; ax.DataAspectRatio=[1 1 1];
            ax.XLimMode='manual'; ax.YLimMode='manual'; ax.DataAspectRatioMode='manual';
            ax.XTick=[]; ax.YTick=[]; ax.HitTest='off';
            theta=linspace(-80,80,161);
            plot(ax,sind(theta),cosd(theta),'Color',[.26 .32 .41],'LineWidth',2,'HitTest','off','PickableParts','none');
            for a=[-80 -40 0 40 80]
                plot(ax,[0 sind(a)],[0 cosd(a)],':','Color',[.17 .21 .28],'HitTest','off','PickableParts','none');
                text(ax,1.12*sind(a),1.12*cosd(a),sprintf('%+d°',a),'Color',muted, ...
                    'HorizontalAlignment','center','FontSize',10,'HitTest','off','PickableParts','none');
            end
            plot(ax,0,0,'o','MarkerSize',25,'MarkerFaceColor',[.17 .22 .30], ...
                'MarkerEdgeColor',muted,'HitTest','off','PickableParts','none');
            plot(ax,[-.04 0 .04],[-.01 .07 -.01],'-','Color',fg,'LineWidth',1.5,'HitTest','off','PickableParts','none');
            text(ax,0,-.16,'LISTENER','Color',muted,'HorizontalAlignment','center','FontSize',10,'HitTest','off','PickableParts','none');
            text(ax,0,1.29,'FRONT','Color',fg,'HorizontalAlignment','center','FontSize',11,'HitTest','off','PickableParts','none');
            text(ax,-1.12,-.08,'LEFT','Color',muted,'HorizontalAlignment','center','HitTest','off','PickableParts','none');
            text(ax,1.12,-.08,'RIGHT','Color',muted,'HorizontalAlignment','center','HitTest','off','PickableParts','none');
            obj.rays=gobjects(1,4); obj.markers=gobjects(1,4); shapes={'o','s','d','^'};
            for s=1:4
                obj.rays(s)=plot(ax,[0 0],[0 1],'-','Color',obj.colours(s,:)*.55, ...
                    'HitTest','off','PickableParts','none');
                obj.markers(s)=plot(ax,0,1,shapes{s},'MarkerSize',20-2*s,'LineWidth',1.8, ...
                    'Color',obj.colours(s,:),'MarkerFaceColor',panel, ...
                    'ButtonDownFcn',@(~,e) obj.beginDrag(s,e));
            end
            obj.selectionRing=plot(ax,0,1,'o','MarkerSize',25,'Color',fg,'LineWidth',1.2, ...
                'HitTest','off','PickableParts','none');
            uilabel(sg,'Text','Drag a coloured source to change its direction.','FontColor',fg,'HorizontalAlignment','center');
            uilabel(sg,'Text','Overlap: select a stem name first, then drag the shared point.', ...
                'FontColor',muted,'FontSize',11,'HorizontalAlignment','center');
            transport=uipanel(g,'BackgroundColor',panel,'BorderType','none');
            t=uigridlayout(transport,[3 1],'RowHeight',{6,44,22}, ...
                'Padding',[16 12 16 12],'RowSpacing',12,'BackgroundColor',panel);
            obj.progress=uipanel(t,'BorderType','none','BackgroundColor',[.17 .21 .28]);
            obj.progressFill=uipanel(obj.progress,'BorderType','none','BackgroundColor',obj.colours(1,:), ...
                'Units','normalized','Position',[0 0 .001 1]);
            buttons=uigridlayout(t,[1 6],'RowHeight',{'1x'}, ...
                'ColumnWidth',{126,90,90,90,'1x',320},'Padding',0,'ColumnSpacing',10,'BackgroundColor',panel);
            obj.loadButton=uibutton(buttons,'Text','Load Music','BackgroundColor',[.18 .24 .33],'FontColor',fg);
            obj.loadButton.Visible=matlab.lang.OnOffSwitchState(customMusic);
            obj.playButton=uibutton(buttons,'Text','Play','FontWeight','bold','BackgroundColor',obj.colours(1,:),'FontColor',bg);
            obj.pauseButton=uibutton(buttons,'Text','Pause','BackgroundColor',[.18 .24 .33],'FontColor',fg);
            obj.stopButton=uibutton(buttons,'Text','Stop','BackgroundColor',[.18 .24 .33],'FontColor',fg);
            uilabel(buttons,'Text','');
            vg=uigridlayout(buttons,[1 3],'ColumnWidth',{108,'1x',44}, ...
                'Padding',[0 0 0 0],'ColumnSpacing',8,'BackgroundColor',panel);
            uilabel(vg,'Text','MASTER VOLUME','FontColor',muted,'FontSize',11);
            obj.volumeSlider=uislider(vg,'Limits',[0 100],'Value',65,'MajorTicks',[],'MinorTicks',[]);
            obj.volumeSlider.ValueChangingFcn=@(~,e) obj.volume(e.Value);
            obj.volumeSlider.ValueChangedFcn=@(h,~) obj.volume(h.Value);
            obj.volumeLabel=uilabel(vg,'Text','65%','FontColor',fg,'FontWeight','bold','HorizontalAlignment','right');
            foot=uigridlayout(t,[1 2],'ColumnWidth',{'1x',190},'Padding',0,'BackgroundColor',panel);
            uilabel(foot,'Text','HEADPHONES  /  44.1 kHz  /  Mute overrides Solo', ...
                'FontColor',muted,'FontSize',10);
            obj.timeLabel=uilabel(foot,'Text','0:00 / 0:00','FontColor',muted,'HorizontalAlignment','right');
            f.WindowButtonMotionFcn=@(~,~) obj.pointerMove();
            f.WindowButtonUpFcn=@(~,~) obj.endDrag();
            if isprop(f,'WindowFocusLostFcn'), f.WindowFocusLostFcn=@(~,~) obj.endDrag(); end
            obj.updateAngles(obj.targets,obj.targets);
        end
        function setProgress(obj,ratio)
            obj.progressFill.Position=[0 0 max(.001,min(1,ratio)) 1];
        end
        function minimumSize(obj)
            p=obj.figure.Position;
            if p(3)<1080 || p(4)<720, p(3:4)=max(p(3:4),[1080 720]); obj.figure.Position=p; end
        end
        function selectStem(obj,s)
            obj.selected=s; obj.updateSelection();
        end
        function angle(obj,s,value,source)
            value=max(-80,min(80,value));
            obj.targets(s)=value; obj.sliders(s).Value=value;
            obj.labels(s).Text=sprintf('%+.1f°',value);
            x=sind(value); y=cosd(value);
            obj.rays(s).XData=[0 x]; obj.rays(s).YData=[0 y];
            obj.markers(s).XData=x; obj.markers(s).YData=y;
            obj.selectStem(s);
            if ~isempty(obj.onAngle), obj.onAngle(s,value,source); end
        end
        function control(obj,s,kind,value)
            obj.selectStem(s);
            if ~isempty(obj.onControl), obj.onControl(s,kind,value); end
        end
        function volume(obj,value)
            value=max(0,min(100,value)); obj.volumeSlider.Value=value;
            obj.volumeLabel.Text=sprintf('%.0f%%',value);
            if ~isempty(obj.onVolume), obj.onVolume(value); end
        end
        function beginDrag(obj,s,event)
            if ~strcmp(obj.figure.SelectionType,'normal'), return; end
            % A selected member of an overlapping group wins over draw order.
            if abs(obj.targets(s)-obj.targets(obj.selected))<2, s=obj.selected; end
            obj.selectStem(s); obj.dragging=s; obj.figure.Pointer='hand';
            if ~isempty(event) && isprop(event,'IntersectionPoint')
                p=event.IntersectionPoint; obj.dragAt(p(1),p(2));
            end
        end
        function pointerMove(obj)
            if obj.dragging==0, return; end
            p=obj.axes.CurrentPoint; obj.dragAt(p(1,1),p(1,2));
        end
        function dragAt(obj,x,y)
            if obj.dragging==0 || ~all(isfinite([x y])) || hypot(x,y)<.05, return; end
            obj.angle(obj.dragging,max(-80,min(80,atan2d(x,y))),3);
        end
        function endDrag(obj)
            obj.dragging=0;
            if isvalid(obj.figure), obj.figure.Pointer='arrow'; end
        end
        function updateAngles(obj,targets,measured)
            obj.targets=targets;
            for s=1:4
                obj.labels(s).Text=sprintf('%+.1f°',targets(s));
                obj.labels(s).Tooltip=sprintf('Target %+.1f° | HRTF %+.0f°',targets(s),measured(s));
                obj.sliders(s).Value=targets(s);
                x=sind(targets(s)); y=cosd(targets(s));
                obj.rays(s).XData=[0 x]; obj.rays(s).YData=[0 y];
                obj.markers(s).XData=x; obj.markers(s).YData=y;
            end
            obj.updateSelection();
        end
        function updateSelection(obj)
            s=obj.selected;
            obj.selectionRing.XData=sind(obj.targets(s)); obj.selectionRing.YData=cosd(obj.targets(s));
            for k=1:4
                if k==s, c=[.19 .25 .34]; else, c=[.085 .105 .145]; end
                obj.sourceButtons(k).BackgroundColor=c;
            end
        end
        function delete(obj)
            if ~isempty(obj.figure) && isvalid(obj.figure), delete(obj.figure); end
        end
    end
end

classdef Phase4StudioView < handle
    % Spatial Studio presentation and pointer handling; no audio processing.
    properties
        figure
        sliders
        labels
        mutes
        solos
        autos
        sourceButtons
        axes
        rays
        markers
        selectionRing
        playButton
        pauseButton
        stopButton
        loadButton
        exportButton
        exportLabel
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
        onAuto = []
        importLabel
        importTrack
        importFill
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
            head=uigridlayout(g,[3 2],'RowHeight',{32,22,18},'ColumnWidth',{'1x',380}, ...
                'Padding',0,'RowSpacing',2,'BackgroundColor',bg);
            uilabel(head,'Text','SPATIAL STUDIO','FontName','Segoe UI','FontSize',27,'FontWeight','bold','FontColor',fg);
            badge=uilabel(head,'Text','ELEC5305  /  BINAURAL','FontColor',muted,'HorizontalAlignment','right');
            badge.Layout.Row=1; badge.Layout.Column=2;
            obj.songLabel=uilabel(head,'Text','Load a song to begin','FontSize',14,'FontColor',fg);
            obj.status=uilabel(head,'Text','Ready','FontColor',muted,'HorizontalAlignment','right');
            obj.importTrack=uipanel(head,'BorderType','none','BackgroundColor',[.17 .21 .28],'Visible','off');
            obj.importTrack.Layout.Row=3; obj.importTrack.Layout.Column=1;
            obj.importFill=uipanel(obj.importTrack,'BorderType','none','BackgroundColor',obj.colours(1,:), ...
                'Units','normalized','Position',[0 0 .001 1]);
            obj.importLabel=uilabel(head,'Text','','FontSize',10,'FontColor',muted,'HorizontalAlignment','right','Visible','off');
            obj.importLabel.Layout.Row=3; obj.importLabel.Layout.Column=2;
            body=uigridlayout(g,[1 2],'ColumnWidth',{420,'1x'},'Padding',0,'ColumnSpacing',18,'BackgroundColor',bg);
            left=uigridlayout(body,[5 1],'RowHeight',{28,'1x','1x','1x','1x'}, ...
                'Padding',0,'RowSpacing',12,'BackgroundColor',bg);
            uilabel(left,'Text','STEMS  /  DIRECTION','FontSize',12,'FontWeight','bold','FontColor',muted);
            names={'Vocals','Drums','Bass','Other'};
            obj.sliders=gobjects(1,4); obj.labels=gobjects(1,4); obj.mutes=gobjects(1,4);
            obj.solos=gobjects(1,4); obj.autos=gobjects(1,4); obj.sourceButtons=gobjects(1,4);
            for s=1:4
                card=uipanel(left,'BackgroundColor',panel,'BorderType','none');
                c=uigridlayout(card,[3 5],'RowHeight',{27,18,'1x'},'ColumnWidth',{90,'1x',59,55,54}, ...
                    'Padding',[14 8 14 6],'RowSpacing',2,'ColumnSpacing',5,'BackgroundColor',panel);
                obj.sourceButtons(s)=uibutton(c,'Text',names{s},'FontWeight','bold','FontSize',14, ...
                    'FontColor',obj.colours(s,:),'BackgroundColor',panel,'ButtonPushedFcn',@(~,~) obj.selectStem(s));
                obj.labels(s)=uilabel(c,'FontColor',fg,'HorizontalAlignment','right','FontSize',12);
                obj.mutes(s)=uicheckbox(c,'Text','Mute','FontColor',muted, ...
                    'ValueChangedFcn',@(h,~) obj.control(s,1,h.Value));
                obj.solos(s)=uicheckbox(c,'Text','Solo','FontColor',muted, ...
                    'ValueChangedFcn',@(h,~) obj.control(s,2,h.Value));
                obj.autos(s)=uicheckbox(c,'Text','Auto','FontColor',obj.colours(s,:), ...
                    'ValueChangedFcn',@(h,~) obj.auto(s,h.Value));
                note=uilabel(c,'Text','LEFT  -80                              0                              +80  RIGHT', ...
                    'FontColor',muted,'FontSize',9); note.Layout.Row=2; note.Layout.Column=[1 5];
                obj.sliders(s)=uislider(c,'Limits',[-80 80],'Value',obj.targets(s), ...
                    'MajorTicks',[],'MinorTicks',[],'FontColor',muted);
                obj.sliders(s).Layout.Row=3; obj.sliders(s).Layout.Column=[1 5];
                obj.sliders(s).ValueChangingFcn=@(~,e) obj.angle(s,e.Value,1);
                obj.sliders(s).ValueChangedFcn=@(h,~) obj.angle(s,h.Value,2);
            end
            space=uipanel(body,'BackgroundColor',panel,'BorderType','none');
            sg=uigridlayout(space,[4 1],'RowHeight',{30,'1x',26,24},'Padding',[16 12 16 12], ...
                'RowSpacing',4,'BackgroundColor',panel);
            uilabel(sg,'Text','SOUND STAGE','FontColor',fg,'FontSize',14,'FontWeight','bold');
            ax=uiaxes(sg,'Color',panel,'XColor',panel,'YColor',panel,'Box','off'); obj.axes=ax;
            hold(ax,'on'); disableDefaultInteractivity(ax); ax.Interactions=[]; ax.Toolbar.Visible='off';
            ax.XLim=[-1.28 1.28]; ax.YLim=[-.25 .83]; ax.DataAspectRatio=[1 1 1];
            ax.XLimMode='manual'; ax.YLimMode='manual'; ax.DataAspectRatioMode='manual';
            ax.XTick=[]; ax.YTick=[]; ax.HitTest='off';
            theta=linspace(-80,80,161);
            patch(ax,[-1.23 1.23 .84 -.84],[-.13 -.13 .76 .76],[.075 .095 .13], ...
                'EdgeColor','none','HitTest','off','PickableParts','none');
            for radius=[.35 .68 1]
                [px,py]=Phase4StageProjection.project(theta,radius);
                plot(ax,px,py,'Color',[.20 .26 .34],'LineWidth',1+(radius==1), ...
                    'HitTest','off','PickableParts','none');
            end
            for a=[-80 -40 0 40 80]
                [px,py]=Phase4StageProjection.project(a);
                plot(ax,[0 px],[0 py],':','Color',[.19 .24 .31],'HitTest','off','PickableParts','none');
                [tx,ty]=Phase4StageProjection.project(a,1.12);
                text(ax,tx,ty,sprintf('%+d°',a),'Color',muted, ...
                    'HorizontalAlignment','center','FontSize',10,'HitTest','off','PickableParts','none');
            end
            % A soft ground shadow and a small head seen from behind/above.
            phi=linspace(0,2*pi,50);
            patch(ax,.11*cos(phi),-.025+.045*sin(phi),[.035 .045 .065], ...
                'EdgeColor','none','HitTest','off','PickableParts','none');
            patch(ax,.065*cos(phi),.065*sin(phi),[.17 .22 .30], ...
                'EdgeColor',muted,'LineWidth',1.2,'HitTest','off','PickableParts','none');
            plot(ax,[-.035 0 .035],[.045 .095 .045],'-','Color',fg,'LineWidth',1.5,'HitTest','off','PickableParts','none');
            text(ax,0,-.14,'LISTENER','Color',muted,'HorizontalAlignment','center','FontSize',10,'HitTest','off','PickableParts','none');
            text(ax,0,.77,'FRONT','Color',fg,'HorizontalAlignment','center','FontSize',11,'HitTest','off','PickableParts','none');
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
            buttons=uigridlayout(t,[1 7],'RowHeight',{'1x'}, ...
                'ColumnWidth',{126,90,90,90,126,'1x',320},'Padding',0,'ColumnSpacing',10,'BackgroundColor',panel);
            obj.loadButton=uibutton(buttons,'Text','Load Music','BackgroundColor',[.18 .24 .33],'FontColor',fg);
            obj.loadButton.Visible=matlab.lang.OnOffSwitchState(customMusic);
            obj.playButton=uibutton(buttons,'Text','Play','FontWeight','bold','BackgroundColor',obj.colours(1,:),'FontColor',bg);
            obj.pauseButton=uibutton(buttons,'Text','Pause','BackgroundColor',[.18 .24 .33],'FontColor',fg);
            obj.stopButton=uibutton(buttons,'Text','Stop','BackgroundColor',[.18 .24 .33],'FontColor',fg);
            obj.exportButton=uibutton(buttons,'Text','Export WAV','BackgroundColor',[.18 .24 .33],'FontColor',fg,'Enable','off');
            uilabel(buttons,'Text','');
            vg=uigridlayout(buttons,[1 3],'ColumnWidth',{108,'1x',44}, ...
                'Padding',[0 0 0 0],'ColumnSpacing',8,'BackgroundColor',panel);
            uilabel(vg,'Text','MASTER VOLUME','FontColor',muted,'FontSize',11);
            obj.volumeSlider=uislider(vg,'Limits',[0 100],'Value',65,'MajorTicks',[],'MinorTicks',[]);
            obj.volumeSlider.ValueChangingFcn=@(~,e) obj.volume(e.Value);
            obj.volumeSlider.ValueChangedFcn=@(h,~) obj.volume(h.Value);
            obj.volumeLabel=uilabel(vg,'Text','65%','FontColor',fg,'FontWeight','bold','HorizontalAlignment','right');
            foot=uigridlayout(t,[1 2],'ColumnWidth',{'1x',190},'Padding',0,'BackgroundColor',panel);
            obj.exportLabel=uilabel(foot,'Text','HEADPHONES  /  44.1 kHz  /  Mute overrides Solo', ...
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
        function setExportBusy(obj,busy)
            state=matlab.lang.OnOffSwitchState(~busy);
            controls=[num2cell(obj.sliders),num2cell(obj.mutes),num2cell(obj.solos), ...
                num2cell(obj.autos),num2cell(obj.sourceButtons), ...
                {obj.volumeSlider,obj.loadButton,obj.playButton,obj.pauseButton,obj.stopButton,obj.exportButton}];
            for k=1:numel(controls), controls{k}.Enable=state; end
        end
        function setExportProgress(obj,fraction,stage)
            obj.importTrack.Visible='on'; obj.importLabel.Visible='on';
            obj.status.Text='Exporting'; obj.status.Tooltip=stage;
            if isfinite(fraction)
                obj.importFill.Position=[0 0 max(.001,fraction) 1];
                obj.importLabel.Text=sprintf('%s %.0f%%',stage,100*fraction);
            else
                obj.importFill.Position=[0 0 .3 1]; obj.importLabel.Text=stage;
            end
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
            [x,y]=Phase4StageProjection.project(value);
            obj.rays(s).XData=[0 x]; obj.rays(s).YData=[0 y];
            obj.markers(s).XData=x; obj.markers(s).YData=y;
            obj.selectStem(s);
            if ~isempty(obj.onAngle), obj.onAngle(s,value,source); end
        end
        function auto(obj,s,value)
            obj.selectStem(s); obj.autos(s).Value=logical(value);
            if ~isempty(obj.onAuto), obj.onAuto(s,value); end
        end
        function setImportProgress(obj,active,state)
            obj.importTrack.Visible=matlab.lang.OnOffSwitchState(active);
            obj.importLabel.Visible=matlab.lang.OnOffSwitchState(active);
            if ~active, return; end
            elapsed=state.elapsed_seconds;
            if state.indeterminate || isempty(state.percent) || ~isfinite(state.percent)
                % Moving pulse explicitly denotes unknown percentage, not progress.
                obj.importFill.Position=[.7*mod(elapsed/2,1) 0 .3 1];
                obj.importLabel.Text=sprintf('Indeterminate | waited %.0f s',elapsed);
                obj.importLabel.Tooltip=state.stage;
            else
                obj.importFill.Position=[0 0 max(.001,state.percent/100) 1];
                if isfield(state,'cache_hit') && state.cache_hit
                    obj.importLabel.Text=sprintf('Cache ready | waited %.0f s',elapsed);
                    obj.importLabel.Tooltip='Validated cached stems; no inference performed.';
                else
                    obj.importLabel.Text=sprintf('Inference %.0f%% | waited %.0f s',state.percent,elapsed);
                    obj.importLabel.Tooltip='Completed inference work across four models; excludes model loading and output validation.';
                end
            end
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
            obj.angle(s,obj.targets(s),3); % Mouse-down itself cancels this stem's Auto.
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
            obj.angle(obj.dragging,Phase4StageProjection.unproject(x,y),3);
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
                [x,y]=Phase4StageProjection.project(targets(s));
                obj.rays(s).XData=[0 x]; obj.rays(s).YData=[0 y];
                obj.markers(s).XData=x; obj.markers(s).YData=y;
            end
            obj.updateSelection();
        end
        function updateSelection(obj)
            s=obj.selected;
            [x,y]=Phase4StageProjection.project(obj.targets(s));
            obj.selectionRing.XData=x; obj.selectionRing.YData=y;
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

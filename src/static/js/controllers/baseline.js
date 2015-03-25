var Baseline = Backbone.View.extend({
    el: $("#baseline"),
    events:{
        'click #baseline_select': 'visibility_change',
        'click #baseline_check':  'selected',        
        'click #baseline_list_select': 'show_baseline_list'
    },
    initialize: function(){
        _.bindAll(this, 'callback', 'hide_report_tool_bar', 'show_report_tool_bar', 'hide_image_picker', 'show_image_picker', 'visibility_change', 'setting_baseline_popup', 'show_image_picker_search');
        this.callerView = this.options.callerView;
        this.report     = this.options.report;
        this.map        = this.options.mapview; 
//        this.setting_report_data();
        this.report_tool_bar = new ReportToolbar({el: this.$("#range_select"), report: this.report, url_send: '/baseline_report/', callerView: this});
        //this.image_picker = new ImagePicker({el: this.$("#image_picker"), callerView: this});        
        this.visibility = false;
        this.selected = false;
        this.baselines = new LayerCollection();
        this.baselines.url = 'baseline_list/';
        this.baselines.fetch();
        var that = this;
        this.report_tool_bar.bind('send_success', function(){that.baselines.add(that.report_tool_bar.data_request)});
    },
    show_baseline_list: function(e){
    	if(e) e.preventDefault();
        if(this.layer_editor_baseline === undefined) {
            this.layer_editor_baseline = new LayerEditorBaseline({
                parent: this.$('#baseline_list'),
                layers: this.baselines
            });
        }


        if(this.layer_editor_baseline.showing) {
            this.layer_editor_baseline.close(); 
            this.$("#baseline_list_select").css({
                "color": "white",
                "text-shadow": "0 1px black",
                "background": "none",
               });
        } else {
        	console.log(this.baselines);
            this.layer_editor_baseline.layers = this.baselines;
            this.layer_editor_baseline.trigger('change_layers');
            var that = this;
            this.baselines.each(function(layer){
                      var layer_map = that.map.layers.get(layer.get('id'));
                      if(layer_map){
                    	  //Already exist
                      }else{
                    	  that.map.layers.add(layer);
                      }
            });
            
            this.layer_editor_baseline.layers.each(function(m){
                if(!m.get('visibility')){
                    that.layer_editor_baseline.layers.remove(m);
                }
            });
            this.$("#baseline_list_select").css({
            	                                "color": "rgb(21, 2, 2)",
            	                                "text-shadow": "0 1px white",
            	                                "background": "-webkit-gradient(linear, 50% 0%, 50% 100%, from(#E0E0E0), to(#EBEBEB))",
            	                               });
            this.trigger('show_baseline_list');
            this.layer_editor_baseline.show();
        }
    },
    setting_report_data: function(){
        var date    = new Date();
        var current_month     = date.getMonth();
        var current_year     = date.getYear();

        var new_start = moment(new Date(current_year, current_month_sad + 1, 1)).format("DD-MM-YYYY");
        var new_end   = moment(new Date(current_year, current_month_sad + 1, 0)).format("DD-MM-YYYY");
        console.log("Nem start: "+new_start);
        this.report.set('str', new_start);
        this.report.set('str_end', new_end);

    },
    setting_baseline_popup: function(popup, grid){
    	if(this.selected && grid.model.get('z') == '2'){
    		//popup.append( "<p>Test</p>" );
    		var setting_baseline = popup.find('.setting_baseline')
    		setting_baseline.show();
    		var that = this;
    		setting_baseline.click(function(e) {
    			if(e)e.preventDefault();
    			that.show_imagepicker_search(grid);
			});
    		
    	}else{
    		var setting_baseline = popup.find('.setting_baseline')
    		setting_baseline.hide();
    	}
    },
    show_imagepicker_search: function(grid) {
    	
    	if(this.editor_baseline_imagepicker === undefined) {
            this.editor_baseline_imagepicker = new EditorBaselineImagePicker({
                parent: this.$('#baseline_list')                
            });
        }
    	
    	if(this.editor_baseline_imagepicker.showing) {
            this.editor_baseline_imagepicker.close();             
        } else {
        	console.log(this.baselines);            
            
            //var that = this;
            
            this.trigger('show_imagepicker_search');
            this.editor_baseline_imagepicker.show();
        }
	},
    selected: function(){
        this.selected = document.getElementById('baseline_check').checked;
        this.callerView.callback_selected(this);
    },
    disable: function(){
        this.selected = false;
        document.getElementById('baseline_check').checked = false;
    },
    callback: function(view){
        if(view === this.report_tool_bar && this.report_tool_bar.visibility){
            this.hide_image_picker();
        }
        /*
        else if(view === this.image_picker && this.image_picker.visibility){
            this.hide_report_tool_bar();
        }*/
    },
    hide_report_tool_bar: function(){
        if(this.report_tool_bar.visibility){
          this.report_tool_bar.visibility_change();
        }
    },
    show_report_tool_bar: function(){
        if(!this.report_tool_bar.visibility){
          this.report_tool_bar.visibility_change();
        }
    },
    hide_image_picker: function(){
        if(this.image_picker.visibility){
          this.image_picker.visibility_change();
        }
    },
    show_image_picker: function(){
        if(!this.image_picker.visibility){
          this.image_picker.visibility_change();
          this.image_picker.bind('visibility_change', this.show_baseline_list(null));
        }        
    },
    show_selected: function(){
    	if(this.selected){
    		this.$("#baseline_content").css("left", "50px");
    		this.el.show();
    	}else{
    		this.el.hide();
    	}
    },
    visibility_change: function(){
        if(this.visibility){
            $(this.el).css("background-color", "rgba(0, 0, 0, 0)");
            this.$("#baseline_select h3").css("color", "#999999");
            this.$("#baseline_content").hide();
            this.visibility = false;
        }
        else{
            $(this.el).css("background-color", "rgba(0, 0, 0, 1)");
            this.$("#baseline_select h3").css("color", "white");
            this.$("#baseline_content").show();
            this.visibility = true;
            this.callerView.callback(this);
        }

    }
});

var ReportToolbar = Backbone.View.extend({
    //el: $("#range_select"),
    events: {
        'click #submit_date_picker': 'send_date_report',
        'click #date_range_select': 'visibility_change'
    },
    initialize: function() {
       _.bindAll(this, 'update_range_date', 'render');
       var self = this;
       this.report     = this.options.report;
       this.callerView = this.options.callerView;

       this.visibility = false;
       var start = this.report.escape('str');
       this.start_date = moment(new Date(start)).format("DD/MMM/YYYY");
       var end = this.report.escape('str_end');
       this.end_date = moment(new Date(end)).format("DD/MMM/YYYY");
       this.data_request = null;

       this.$("#range_picker").attr("value", this.start_date+' to '+this.end_date).html();
       this.visibility_picker_range = false;
       this.url_send = this.options.url_send;

       this.$('#date_timepicker_start').attr("value", this.start_date).html();
       this.$('#date_timepicker_end').attr("value", this.end_date).html();
       
       var d = new Date();
       var date_defaut = moment(new Date(d.getFullYear(), d.getMonth(), 0)).format("DD/MMM/YYYY");
       
      var picker_start = new Pikaday(
         	    {
         	        field: this.$("#date_timepicker_start")[0],
         	        format: 'DD/MMM/YYYY',       	        
         	        minDate: new Date('01/03/1985'),
         	        //maxDate: new Date(this.$('#date_timepicker_end').val()),
         	        maxDate: new Date(date_defaut),
         	        yearRange: [1985, new Date().getFullYear()],
         	        onSelect: function() {             	        	  
         	        	var date = this.getDate(); 
         	        	var date_start = moment(new Date(date.getFullYear(), date.getMonth(), 1)).format("DD/MMM/YYYY");
         	        	var date_end = moment(new Date(date.getFullYear(), date.getMonth() + 1, 0)).format("DD/MMM/YYYY");
         	        	self.$('#date_timepicker_start').attr("value", date_start).html();
         	        	self.$('#date_timepicker_end').attr("value", date_end).html();             	        	
  				    }
  				    
         	    });
             
         var picker_end = new Pikaday(
         	    {
         	        field: this.$("#date_timepicker_end")[0],
         	        format: 'DD/MMM/YYYY',
         	        minDate: new Date('01/03/1985'),
         	        maxDate: new Date(date_defaut),
         	        yearRange: [1985, new Date().getFullYear()],
         	        onSelect: function() {
        	        	//var date = new Date(self.$('#date_timepicker_start').val());   
        	        	var date = this.getDate(); 
        	        	var date_start = moment(new Date(date.getFullYear(), date.getMonth(), 1)).format("DD/MMM/YYYY");
        	        	var date_end = moment(new Date(date.getFullYear(), date.getMonth() + 1, 0)).format("DD/MMM/YYYY");
        	        	self.$('#date_timepicker_start').attr("value", date_start).html();
        	        	self.$('#date_timepicker_end').attr("value", date_end).html();
        	        	
     	        	    //this.setDate(new Date(date.getFullYear(), date.getMonth(), 1));
 				    }
         	    });
    },
    send_date_report: function(e){
    	if(e) e.preventDefault();
    	
    	var date_start = this.$('#date_timepicker_start').val();
    	var date_end = this.$('#date_timepicker_end').val();
    	
        this.$("#loading_range_picker").show();
        var that = this;
        var request = $.ajax({
                            url: this.url_send,
                            type: 'POST',
                            data: {date_start: date_start, date_end: date_end},
                            dataType: 'json',
                            async: true,
                            success:function(d) {
                            	  that.$("#loading_range_picker").hide();
                    	          alert(d.result.message);
                                  console.log(d);
                                  that.data_request = d.result.data;
                                  that.trigger('send_success');
                                  console.log(that.data_request);
                                  return d; 
                            },
                          }).responseText;

        //var s = jQuery.parseJSON(message);
        //alert(s.result);
        //console.log(s);
    },
    set_range_date_input: function(report){
    	var start = report.escape('str');
        var start_date = moment(new Date(start)).format("DD/MMM/YYYY");
        var end = report.escape('str_end');
        var end_date = moment(new Date(end)).format("DD/MMM/YYYY");        

        this.$("#range_picker").attr("value", start_date+' to '+end_date).html();
    },
    update_range_date: function(evt, obj){
        var dates = obj.value.split(' to ');
        console.log(dates[0]+' - '+dates[1]);
        this.start_date = dates[0];
        this.end_date = dates[1];
    },
    render: function(){
        return this;
    },
    visibility_change: function(e){
    	if(e)e.preventDefault();
    	if(this.visibility) {
            this.$("#form_date_range").hide(); 
            this.$("#date_range_select").css({
                "color": "white",
                "text-shadow": "0 1px black",
                "background": "none",
               });
            this.visibility = false;
        } else {
        	this.$("#form_date_range").show();            
            this.$("#date_range_select").css({
            	                                "color": "rgb(21, 2, 2)",
            	                                "text-shadow": "0 1px white",
            	                                "background": "-webkit-gradient(linear, 50% 0%, 50% 100%, from(#E0E0E0), to(#EBEBEB))",
            	                               });
            this.visibility = true;
            this.render();
            this.callerView.callback(this);
        }
        
    },
    show: function() {
        this.el.show();
    },

    hide: function() {
        this.el.hide();
    }
});

var ImagePicker = Backbone.View.extend({
    //el: $("#image_picker"),
    events: {
        'click #picker_select' : 'visibility_change',
        'click #submit': 'send_images'
    },
    initialize: function(){
        _.bindAll(this, 'visibility_change');
        this.thumbsView = new ThumbsView({el: this.$("#thumb"), tile_el: this.$("#tile"), parentView: this});
        this.callerView = this.options.callerView;
        this.visibility = false;
    },
    change_sensor: function(sensor){
        this.thumbsView.change_sensor(sensor);
    },
    send_images: function(e){
    	if(e) e.preventDefault();
    	
        var thumb = this.$("#thumb").val();
        var tile = this.$("#tile").val();        
        console.log(thumb);
        var message = $.ajax({
                              url: "/picker/",
                              type: 'POST',
                              data: {thumb: thumb.join(), tile: tile},
                              dataType: 'json',
                              async: false
                            }).responseText;

        var s = jQuery.parseJSON(message);
        alert(s.result);
        console.log(s);
    },
    show: function() {
        this.el.show();
    },

    hide: function() {
        this.el.hide();
    },
    visibility_change: function(e){
    	if(e) e.preventDefault();
    	
        if(this.visibility){
          this.$("#picker_form").hide();
          //$(this.el).css("background", "");
          this.visibility = false;
        }else{
          //$(this.el).css("background", 'url("static/img/bkg_image_picker_over.png") no-repeat -1px 0');
          this.$("#picker_form").show();
          this.visibility = true;
          this.trigger('visibility_change');
          this.callerView.callback(this);
        }
    }
});

var DownScalling = Backbone.View.extend({
    el: $("#downscalling"),
    events: {
        'click #scalling_select': 'visibility_change',
        'click #submit':          'send_downscalling'
    },
    initialize: function(){
        _.bindAll(this, 'visibility_change', 'hide_form');
        var parameters = new Parameters();
        this.callerView = this.options.callerView;
        this.downScalling = new SelectParameters({collection: parameters, parentView: this});
        this.visibility = false;
    },
     send_downscalling: function(e){
    	 if(e) e.preventDefault();
    	 
    	 var values_valid = true;
    	 
    	 var sill3 = this.$("#i_sill3").val();
    	 var range3 = this.$("#i_range3").val();
         var nugget3 = this.$("#i_nugget3").val();

         var sill4 = this.$("#i_sill4").val();
         var range4 = this.$("#i_range4").val();
         var nugget4 = this.$("#i_nugget4").val();

         var sill6 = this.$("#i_sill6").val();
         var range6 = this.$("#i_range6").val();
         var nugget6 = this.$("#i_nugget6").val();

         var sill7 = this.$("#i_sill7").val();
         var range7 = this.$("#i_range7").val();
         var nugget7 = this.$("#i_nugget7").val();
    	 
        if(isNaN(parseInt(sill3, 10))){
        	console.log("Not number: "+sill3);
        	values_valid = false;
        }else if(isNaN(parseInt(range3, 10))){
        	console.log("Not number: "+range3);
        	values_valid = false;
        }else if(isNaN(parseInt(nugget3, 10))){
        	console.log("Not number: "+nugget3);
        	values_valid = false;        	
        }else if(isNaN(parseInt(sill4, 10))){
        	console.log("Not number: "+sill4);
        	values_valid = false;
        }else if(isNaN(parseInt(range4, 10))){
        	console.log("Not number: "+range4);
        	values_valid = false;
        }else if(isNaN(parseInt(nugget4, 10))){
        	console.log("Not number: "+sill3);
        	values_valid = false;
        }else if(isNaN(parseInt(sill6, 10))){
        	console.log("Not number: "+sill6);
        	values_valid = false;
        }else if(isNaN(parseInt(range6, 10))){
        	console.log("Not number: "+range6);
        	values_valid = false;
        }else if(isNaN(parseInt(nugget6, 10))){
        	console.log("Not number: "+nugget6);
        	values_valid = false;
        }else if(isNaN(parseInt(sill7, 10))){
        	console.log("Not number: "+sill7);
        	values_valid = false;
        }else if(isNaN(parseInt(range7, 10))){
        	console.log("Not number: "+range7);
        	values_valid = false;
        }else if(isNaN(parseInt(nugget7, 10))){
        	console.log("Not number: "+nugget7);
        	values_valid = false;
        }
        
        if(values_valid){
        	var tile = this.$("#tile").val();
            var compounddate = this.callerView.compounddate();

            console.log(thumb);
            var message = $.ajax({
                                  url: "/downscalling/",
                                  type: 'POST',
                                  data: {
                                      tile: tile, compounddate: compounddate,
                                      sill3: sill3, range3: range3, nugget3: nugget3,
                                      sill4: sill4, range4: range4, nugget4: nugget4,
                                      sill6: sill6, range6: range6, nugget6: nugget6,
                                      sill7: sill7, range7: range7, nugget7: nugget7,
                                },
                                  dataType: 'json',
                                  async: false
                                }).responseText;

            var s = jQuery.parseJSON(message);
            alert(s.result);
            console.log(s);
        }
   
        
    },
    hide_form: function(){
        $("#scalling_form").hide();
        //$(this.el).css("background", "");
        this.visibility = false;
    },
    show: function() {
        this.el.show();
    },

    hide: function() {
        this.el.hide();
    },
    visibility_change: function(e){
    	if(e)e.preventDefault();
        if(this.visibility){
            this.hide_form();
        }
        else{
          $("#scalling_form").show();
          //$(this.el).css("background", 'url("static/img/bkg_downscalling_over.png") no-repeat 4px 0');
          this.visibility = true;
          this.callerView.callback(this);
        }
        e.preventDefault();
    }

});

var ReporView = LayerView.extend({
	tagName: 'li',

    events: {
        'click': 'click'
    },
    
	initialize: function() {
        _.bindAll(this, 'render', 'click', 'changed');
        this.model.bind('change', this.changed);
    },
    render: function() {
    	var el = $(this.el);
        this.id = 'report_' + this.model.escape('id');
        var name = this.model.escape('assetid')
        if(name == 'null'){
        	name = "LAST PERIOD"
        }
        
        el.html("<a href='#'>" + name + "</a>");
        el.attr('id', this.id);
        this.changed();
        //el.addClass('sortable');                        
        return this;
    },
    click: function(e) {
        e.preventDefault();
        this.model.set_enabled(!this.model.enabled);
    },
    changed: function() {
        var enabled = this.model.enabled;
        if(!enabled) {
            //this.trigger('disable', this);
            $(this.el).removeClass('selected');
        } else {
            $(this.el).addClass('selected');
            this.trigger('enable_report');
        }
    }
});

var LayerEditorReports = Backbone.View.extend({

    showing: false,

    template: _.template($('#reports-layers').html()),
        
    initialize: function() {
        _.bindAll(this, 'show', 'addLayer', 'addLayers', 'sortLayers', 'deselect_layers');
        var self = this;

        this.item_view_map = {};
        this.layers = this.options.layers;
        this.el = $(this.template());
        this.options.parent.append(this.el);
        this.addLayers(this.layers);
        this.el.find('ul').jScrollPane({autoReinitialise:true});

        this.el.find('ul, div.jspPane').sortable({
          revert: false,
          items: '.sortable',
          axis: 'y',
          cursor: 'pointer',
          stop:function(event,ui){
            $(ui.item).removeClass('moving');
            //
            //DONT CALL THIS FUNCTION ON beforeStop event, it will crash :D
            //
            self.sortLayers();
          },
          start:function(event,ui){
            $(ui.item).addClass('moving');
          }
        });
        this.layers.trigger('reset');
        //this.bind('change_layers', function(){self.addLayers(self.layers)});
    },

    // reorder layers in map
    sortLayers: function() {
        var self = this;
        var new_order_list = [];
        // sort layers
        this.el.find('ul').find('li').each(function(idx, item) {
            var id = $(item).attr('id');
            var view = self.item_view_map[id];
            self.layers.remove(view.model);
            new_order_list.push(view.model);
        });
        _(new_order_list).each(function(l) {
            self.layers.add(l);
        });
        this.layers.trigger('reset');
    },

    addLayer: function(layer) {
        if(!layer.hidden) {
            var ul = this.el.find('ul');
            layer.bind('change', this.deselect_layers);
            var view = new ReporView({model: layer});
            var that = this;
            view.bind('enable_report', function(){that.trigger('enable_report')})
            ul.append(view.render().el);
            this.item_view_map[view.id] = view;
        }        
    },
    deselect_layers: function(changed) {
        //console.log("CHANING" + changed.get('description'));
        if(changed.enabled) {
            this.layers.each(function(layer) {
                if(layer.enabled && layer !== changed) {
                    //console.log("disabling " + layer.get('description'));
                    layer.set_enabled(false);
                }
            });
        }
    },
    addLayers: function(layers) {
         this.el.find('ul').html('');         
         var that = this;
         layers.each(function(m){
            if(m.get('visibility') || m.get('type') == 'reports'){
                that.addLayer(m);
            }
         });
    },
    show: function(pos, side) {       	
        this.el.show();//fadeIn();
        this.showing = true;
    },

    close: function() {
        this.el.hide();//fadeOut(0.1);
        this.showing = false;
    }

});



var Sad = Backbone.View.extend({
    el: $("#sad"),
    events: {
        'click #sad_select': 'visibility_change',
        'click #sad_list_select': 'show_reports_list'
    },
    initialize: function(){
        _.bindAll(this, 'visibility_change', 'callback', 'hide_date_range', 'show_date_range', 'hide_image_picker', 'show_image_picker', 'hide_down_scalling', 'show_down_scalling', 'reload_report', 'set_selected', 'hide_layer_editor_reports');
        this.callerView = this.options.callerView;
        this.map = this.options.mapview;
        this.report = this.options.report

        //this.setting_report_data();
        this.date_range = new ReportToolbar({el: this.$("#date_range"), report: this.report, url_send: '/range_report/', callerView: this});
        this.image_picker = new ImagePicker({el: this.$("#image_picker"), callerView: this});
        this.down_scalling = new DownScalling({callerView: this});
        this.visibility = false;
        this.selected = false;
        this.reports = new ReportsCollection();
        this.reports.url = 'reports_list/';
        this.reports.fetch();
        var that = this;
        this.date_range.bind('send_success', function(){that.reports.add(that.date_range.data_request)});
    },   
    compounddate: function(){
        var date = moment(new Date(this.report.escape('str'))).format('YYYYMM');
        return date;
    },
    show_reports_list: function(e){
    	if(e) e.preventDefault();
        if(this.layer_editor_reports === undefined) {
            this.layer_editor_reports = new LayerEditorReports({
                parent: this.$('#sad_list'),
                layers: this.reports
            });
            this.layer_editor_reports.bind('enable_report', this.reload_report)
        }


        if(this.layer_editor_reports.showing) {
        	this.hide_layer_editor_reports();
        } else {
        	console.log(this.reports);
            this.layer_editor_reports.layers = this.reports;
            this.layer_editor_reports.trigger('change_layers');
            var that = this;
            /*this.reports.each(function(layer){
                      var layer_map = that.map.layers.get(layer.get('id'));
                      if(layer_map){
                    	  //Already exist
                      }else{
                    	  that.map.layers.add(layer);
                      }
            });*/
            
            this.layer_editor_reports.layers.each(function(m){
                if(!m.get('visibility')){
                    that.layer_editor_reports.layers.remove(m);
                }
            });
            this.$("#sad_list_select").css({
            	                                "color": "rgb(21, 2, 2)",
            	                                "text-shadow": "0 1px white",
            	                                "background": "-webkit-gradient(linear, 50% 0%, 50% 100%, from(#E0E0E0), to(#EBEBEB))",
            	                               });
            this.trigger('show_reports_list');
            this.layer_editor_reports.show();
            this.callback(this.layer_editor_reports);
        }
    },
    reload_report: function(){
    	this.report = this.reports.get_report_enabled();
    	this.date_range.set_range_date_input(this.report);
    	this.trigger('report_change');    	
    },
    setting_report_data: function(){
        var date    = new Date();
        var start    = this.report.escape('str');
        var date_sad = new Date(start);

        var current_month     = date.getMonth();
        var current_month_sad = date_sad.getMonth();

        var current_year     = date.getFullYear();
        var current_year_sad = date_sad.getFullYear();

        var month_diference = current_month - current_month_sad;
        var year_diference  = current_year  - current_year_sad;

        if(month_diference == 2 && year_diference == 0){
            var new_start = moment(new Date(current_year, current_month_sad + 1, 1)).format("DD-MM-YYYY");
            var new_end   = moment(new Date(current_year, current_month_sad + 1, 0)).format("DD-MM-YYYY");
            console.log("Nem start: "+new_start);
            console.log(this.report);
            console.log(new_start);
            console.log(new_end);
            
            this.report.set('str', new_start);
            this.report.set('str_end', new_end);
        }
        else if(month_diference == -10 && year_diference == 1){
            var new_start = moment(new Date(current_year_sad, current_month_sad + 1, 1)).format("DD-MM-YYYY");
            var new_end   = moment(new Date(current_year_sad, current_month_sad + 1, 0)).format("DD-MM-YYYY");
            console.log("Nem start: "+new_start);
            this.report.set('str', new_start);
            this.report.set('str_end', new_end);
        }

    },
    set_selected: function(){
    	this.selected = true;      	      
        this.callerView.callback_selected(this);
        this.$("#sad_select").addClass('sad_select');
        //this.trigger('sad_selected');
    },
    disable: function(){
    	$(this.el).css("background-color", "rgba(0, 0, 0, 0)")
        this.$("#sad_select h3").css("color", "#999999");
        this.$("#sad_content").hide();
        this.visibility = false;
        this.selected = false;
        this.$("#sad_select").removeClass('sad_select');
    },        
    callback: function(view){
        if(view === this.date_range && this.date_range.visibility){
            this.hide_image_picker();
            this.hide_down_scalling();
            this.hide_layer_editor_reports();
        }
        else if(view === this.image_picker && this.image_picker.visibility){
            this.hide_date_range();
            this.hide_down_scalling();
            this.hide_layer_editor_reports();
        }
        else if(view === this.down_scalling && this.down_scalling.visibility){
            this.hide_date_range();
            this.hide_image_picker();
            this.hide_layer_editor_reports();
        }else if(view === this.layer_editor_reports && this.layer_editor_reports.showing){
            this.hide_date_range();
            this.hide_down_scalling();
            this.hide_image_picker();
        }
    },
    hide_layer_editor_reports: function() {
    	this.layer_editor_reports.close(); 
        this.$("#sad_list_select").css({
            "color": "white",
            "text-shadow": "0 1px black",
            "background": "none",
           });
	},
    hide_date_range: function(){
        if(this.date_range.visibility){
          this.date_range.visibility_change();
        }
    },
    show_date_range: function(){
        if(!this.date_range.visibility){
          this.date_range.visibility_change();
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
        }
    },
    hide_down_scalling: function(){
        if(this.down_scalling.visibility){
          this.down_scalling.visibility_change();
        }
    },
    show_down_scalling: function(){
        if(!this.down_scalling.visibility){
          this.down_scalling.visibility_change();
        }
    },
    show_selected: function(){
    	if(this.selected){
    		this.el.show();
    	}else{
    		this.el.hide();
    	}
    },
    show: function() {
        this.el.show();
    },

    hide: function() {
        this.el.hide();
    },
    visibility_change: function(e){
    	if(e)e.preventDefault();
        if(this.visibility){
            $(this.el).css("background-color", "rgba(0, 0, 0, 0)")
            this.$("#sad_select h3").css("color", "#999999");
            this.$("#sad_content").hide();
            this.visibility = false;
        }
        else{
          $(this.el).css("background-color", "rgba(0, 0, 0, 1)");
          this.$("#sad_select h3").css("color", "white");
          this.$("#sad_content").show();
          this.visibility = true;
          this.trigger('visibility_change');
          this.callerView.callback(this);
          this.set_selected();
        }
    }

});

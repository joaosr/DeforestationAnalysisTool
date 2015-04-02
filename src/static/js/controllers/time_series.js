var Period_Time_Series = Backbone.View.extend({
    //el: $("#range_select"),
    events: {
        'click #submit_date_picker': 'send_date_time_series',
      	'click #date_range_select': 'visibility_change'
    },
    initialize: function() {
       _.bindAll(this, 'update_range_date', 'render');
       var self = this;
       this.report     = this.options.report;
       this.callerView = this.options.callerView;

       var start = this.report.escape('str');
       this.start_date = moment(new Date(start)).format("DD/MMM/YYYY");
       var end = this.report.escape('str_end');
       this.end_date = moment(new Date(end)).format("DD/MMM/YYYY");
       this.data_response = null;

       //this.$("#range_picker").attr("value", this.start_date+' to '+this.end_date).html();
       this.visibility = false;
       this.url_send = this.options.url_send;
       this.$('#date_timepicker_start').attr("value", this.start_date).html();
       this.$('#date_timepicker_end').attr("value", this.end_date).html();
       
       var picker_start = new Pikaday(
       	    {
       	        field: this.$("#date_timepicker_start")[0],
       	        format: 'DD/MMM/YYYY',       	        
       	        minDate:new Date('01/03/1985'),
       	        maxDate: new Date(this.$('#date_timepicker_end').val()),   
       	        yearRange: [1985, new Date().getFullYear()],
       	        onOpen: function() {
    	        	this.setMaxDate(new Date(self.$('#date_timepicker_end').val()));
				}
       	    });
       
       var picker_end = new Pikaday(
       	    {
       	        field: this.$("#date_timepicker_end")[0],
       	        format: 'DD/MMM/YYYY',
       	        minDate: new Date(this.$('#date_timepicker_start').val()),
       	        maxDate: new Date(),
       	        yearRange: [1985, new Date().getFullYear()],
       	        onOpen: function() {
       	        	this.setMinDate(new Date(self.$('#date_timepicker_start').val()));
				}
       	    });
       
      /*
       this.$("#range_picker").dateRangePicker({
            format: 'DD/MMM/YYYY',
            separator: ' to ',
            showShortcuts: false}).bind('datepicker-change', this.update_range_date);
       */
    },
    send_date_time_series: function(e){
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
                                  that.data_response = d.result.data;
                                  that.trigger('send_success');
                                  console.log(that.data_response);
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
            //this.callerView.callback(this);
        }
        
    },
    show: function() {
        this.el.show();
    },

    hide: function() {
        this.el.hide();
    }
});

var LayerEditorTimeSeries = Backbone.View.extend({

    showing: false,

    template: _.template($('#time-series-layers').html()),

    initialize: function() {
        _.bindAll(this, 'show', 'addLayer', 'addLayers', 'sortLayers');
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
        this.bind('change_layers', function(){self.addLayers(self.layers)});
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
            if(layer.get('color') !== undefined) {
                var view = new SwitchLayerView({model: layer});
            } else {
                var view = new LayerView({model: layer});
            }
            ul.append(view.render().el);
            this.item_view_map[view.id] = view;
        }
    },    
    addLayers: function(layers) {
         this.el.find('ul').html('');
         console.log("Add Now!!!!!!!");
         var that = this;
         layers.raster_layers().each(function(m){
            if(m.get('visibility') || m.get('type') == 'time_series'){
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

var TimeSeries = Backbone.View.extend({
    el: $("#time_series"),
     events:{
        'click #time_series_select': 'visibility_change',
        'click #time_series_check': 'selected',
        'click #time_series_historical_results_select': 'show_time_series_historical_results'
    },
    initialize: function(){
        _.bindAll(this, 'visibility_change');
        this.callerView = this.options.callerView;
        this.report     = this.options.report;
        this.map        = this.options.mapview;
        this.range_date = new Period_Time_Series({el: this.$("#date_range"), report: this.report, url_send: '/time_series/', callerView: this});
        this.visibility = false;
        this.selected = false;
        this.time_series = new LayerCollection();
        this.time_series.url = 'time_series_historical_results/';
        this.time_series.fetch();
        var that = this;
        this.range_date.bind('send_success', function(){that.time_series.add(that.range_date.data_response)});
    },
    selected: function(){
        this.selected = document.getElementById('time_series_check').checked;
        this.callerView.callback_selected(this);
    },
    disable: function(){
        this.selected = false;
        document.getElementById('time_series_check').checked = false;
    },
    show_time_series_historical_results: function(e){
    	if(e) e.preventDefault();
        if(this.layer_editor_time_series === undefined) {
            this.layer_editor_time_series = new LayerEditorTimeSeries({
                parent: this.$('#time_series_historical_results'),
                layers: this.time_series
            });
        }


        if(this.layer_editor_time_series.showing) {
            this.layer_editor_time_series.close(); 
            this.$("#baseline_list_select").css({
                "color": "white",
                "text-shadow": "0 1px black",
                "background": "none",
               });
        } else {
        	console.log(this.time_series);
            this.layer_editor_time_series.layers = this.time_series;
            this.layer_editor_time_series.trigger('change_layers');
            var that = this;
            this.time_series.each(function(layer){
                      var layer_map = that.map.layers.get(layer.get('id'));
                      if(layer_map){
                    	  //Already exist
                      }else{
                    	  that.map.layers.add(layer);
                      }
            });
            
            this.layer_editor_time_series.layers.each(function(m){
                if(!m.get('visibility')){
                    that.layer_editor_time_series.layers.remove(m);
                }
            });
            this.$("#baseline_list_select").css({
            	                                "color": "rgb(21, 2, 2)",
            	                                "text-shadow": "0 1px white",
            	                                "background": "-webkit-gradient(linear, 50% 0%, 50% 100%, from(#E0E0E0), to(#EBEBEB))",
            	                               });
            this.trigger('show_time_series_historical_results');
            this.layer_editor_time_series.show();
        }
    },
    show_selected: function(){
    	if(this.selected){
    		this.el.show();    		
    	}else{
    		this.el.hide();
    	}
    },
    visibility_change: function(){
        if(this.visibility){
            $(this.el).css("background-color", "rgba(0, 0, 0, 0)");
            this.$("#time_series_select h3").css("color", "#999999");
            this.$("#time_series_content").hide();
            this.visibility = false;
        }
        else{
             $(this.el).css("background-color", "rgba(0, 0, 0, 1)");
            this.$("#time_series_select h3").css("color", "white");
            this.$("#time_series_content").show();   
            this.visibility = true;
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
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

var EditingToolsTimeSeries = Backbone.View.extend({

    initialize: function() {
        _.bindAll(this, 'change_state', 'new_polygon', 'reset', 'polygon_mouseout', 'polygon_mouseover');
        this.state = 'move';
        this.time_series = this.options.time_series;
        this.time_series.polygon_tools.bind('state', this.change_state);
    },

    new_polygon: function(data) {
    	console.log("here!");
        //this.time_series.cell_polygons.polygons.create(data);
        var p = new Polygon(data);
        this.time_series.cell_polygons.polygons.add(p);
        window.loading_small.loading('saving poly');
        p.save(null, {
            success: function() {
                window.loading_small.finished('saving poly');
            }
        });
    },

    //reset to initial state
    reset: function() {
        this.time_series.timeseries_layer.unbind('polygon', this.new_polygon);
        this.time_series.create_polygon_tool.unbind('polygon', this.new_polygon);
        this.time_series.timeseries_layer.editing_state = false;
        this.time_series.cell_polygons.editing_state = false;
        this.time_series.create_polygon_tool.editing_state(false);
        this.time_series.polygon_tools.polytype.hide();
        //this.time_series.map.$("canvas").css('cursor','auto');
        this.time_series.cell_polygons.unbind('click_on_polygon', this.time_series.create_polygon_tool.edit_polygon);
        this.time_series.cell_polygons.unbind('mouseover', this.polygon_mouseover);
        this.time_series.cell_polygons.unbind('mouseout', this.polygon_mouseout);
        this.time_series.map.map.setOptions({draggableCursor: 'default'});
    },

    editing_mode: function() {
        this.time_series.cell_polygons.bind('click_on_polygon', this.time_series.create_polygon_tool.edit_polygon);
    },

    polygon_mouseout: function() {
        var st = this.state;
        var cursors_pos = {
            'edit': '4 4',
            'auto': '7 7',
            'remove': '6 6',
            'draw': '4 16'
        };
        this.time_series.map.map.setOptions({draggableCursor: 'url(/static/img/cursor_' + st +'.png) ' + cursors_pos[st] + ', default'});
    },

    polygon_mouseover: function() {
        var st = this.state;
        var cursors_pos = {
            'edit': '4 4',
            'auto': '7 7',
            'remove': '6 6',
            'draw': '4 16'
        };
        $('path').css({cursor: 'url("http://maps.gstatic.com/intl/en_us/mapfiles/openhand_8_8.cur"), default !important'});
    },

    change_state: function(st) {
        if(st == this.state) {
            return;
        }
        this.state = st;
        this.reset();
        this.polygon_mouseout();
        switch(st) {
            case 'edit':
                this.editing_mode();
                this.time_series.cell_polygons.bind('mouseover', this.polygon_mouseover);
                this.time_series.cell_polygons.bind('mouseout', this.polygon_mouseout);
                break;
            case 'remove':
                this.time_series.cell_polygons.editing_state = true;
                this.time_series.cell_polygons.bind('mouseover', this.polygon_mouseover);
                this.time_series.cell_polygons.bind('mouseout', this.polygon_mouseout);
                break;
            case 'draw':
                this.time_series.create_polygon_tool.editing_state(true);
                this.time_series.polygon_tools.polytype.bind('state', this.time_series.create_polygon_tool.poly_type);
                this.time_series.create_polygon_tool.bind('polygon', this.new_polygon);
                this.time_series.polygon_tools.polytype.show();
                this.time_series.polygon_tools.polytype.select('def');
                break;
            case 'auto':
                this.time_series.timeseries_layer.unbind('polygon', this.new_polygon);
                this.time_series.timeseries_layer.bind('polygon', this.new_polygon);
                this.time_series.timeseries_layer.editing_state = true;
                //this.time_series.map.$("canvas").css('cursor','crosshair');
                break;
        }
        console.log(st);
    }

});

var PolygonToolbarTimeSeries = Backbone.View.extend({

    el: $("#work_toolbar_timeseries"),

    events: {
        'click #compare': 'none',
        'click #ndfirange': 'none',
        'click .class_selector': 'visibility_change'
    },

    initialize: function() {
        _.bindAll(this, 'show', 'hide', 'change_state', 'reset', 'visibility_change', 'update_timeseries');        
        this.buttons = new ButtonGroup({el: this.$('#timeseries_selection')});
        this.polytype = new ButtonGroup({el: this.$('#timeseries_polytype')});
        this.timeseries_range = new RangeSliderTimeSeries({el: this.$("#timeseries_maptools")});
        this.time_series = {}          
        this.timeseries_range.bind('stop', this.update_timeseries);
        this.compare = new ButtonGroup({el: $("#compare_buttons")});
        this.polytype.hide();
        this.buttons.bind('state', this.change_state);
        

    },
    update_timeseries: function(low, high, shade, gv, soil, cloud){
    	this.time_series.def = low;
    	this.time_series.deg = high;
    	this.time_series.shade = shade;
    	this.time_series.gv = gv;
    	this.time_series.soil = soil;
    	this.time_series.cloud = cloud;

        console.log(this.time_series); 
      	this.trigger('send_timeseries', this.time_series);
    },
    visibility_change: function(e) {
        var el = $(e.target);
        var what = $(e.target).attr('id');
        var selected = false;
        if(el.hasClass('check_selected')) {
            el.removeClass('check_selected');
        } else {
            el.addClass('check_selected');
            selected = true;
        }
        this.trigger('visibility_change', what, selected);
        e.preventDefault();
    },

    none: function(e) { e.preventDefault();},

    change_state: function(st) {
        this.trigger('state', st);
    },

    reset: function() {
        this.polytype.unselect_all();
        this.buttons.unselect_all();
    },
    show: function() {
        this.el.show();
    },

    hide: function() {
        this.el.hide();
    }

});

var RangeSliderTimeSeries = Backbone.View.extend({
	 initialize: function() {
		 _.bind(this, 'slide', 'slide_shade', 'slide_gv', 'slide_soil', 'slide_cloud', 'set_values', 'render');

		 this.low = 165;
		 this.high = 175;
		 this.shade = 65;
		 this.gv = 19;
		 this.soil = 4;
		 this.cloud = 42;


		 this.render();
	 },
	 render: function(timeseries){
		var self = this;     
		if(timeseries){
		 this.low = timeseries.def;
		 this.high = timeseries.deg;
		 this.shade = timeseries.shade;
		 this.gv = timeseries.gv;
		 this.soil = timeseries.soil;
		 this.cloud = timeseries.cloud;
		}

		this.$("#slider_forest").slider({
				 range: true,
				 min: 0,
				 max: 200,
				 //values: [40, 60], //TODO: load from model
				 values: [self.low, self.high], //TODO: load from model
				 slide: function(event, ui) {
					 // Hack to get red bar resizing

					 self.low  = ui.values[0];
					 self.high = ui.values[1];
					 self.slide(self.low, self.high);
				 },
				 stop: function(event, ui) {
					 self.low  = ui.values[0];
					 self.high = ui.values[1];            	 
					 self.trigger('stop', self.low, self.high, self.shade, self.gv, self.soil, self.cloud);
					 //self.trigger('stop', low);
				 },
				 create: function(event,ui) {
					 // Hack to get red bar resizing
					 var size = self.$('#slider_forest a.ui-slider-handle:eq(1)').css('left');
					 self.$('#slider_forest span.hack_forest').css('left',size);
					 // Hack for handles tooltip

					 var size0 = self.$('#slider_forest a.ui-slider-handle:eq(0)').css('left');

					 self.$('#slider_forest a.ui-slider-handle:eq(0)').empty();
					 self.$('#slider_forest a.ui-slider-handle:eq(0)').append('<p id="ht0" class="tooltip">'+self.low+'</p>');
					 self.$('#slider_forest a.ui-slider-handle:eq(1)').empty();
					 self.$('#slider_forest a.ui-slider-handle:eq(1)').append('<p id="ht1" class="tooltip">'+self.high+'</p>');
				 }
		  });

		  this.$("#slider_shade").slider({
			 range: "100",
			 min: 0,
			 max: 100,         
			 value: self.shade, //TODO: load from model
			 slide: function(event, ui) {
				 // Hack to get red bar resizing
				 self.shade  = ui.value;             
				 self.slide_shade(self.shade);
			 },
			 stop: function(event, ui) {
				 self.shade  = ui.value;             
				 self.trigger('stop', self.low, self.high, self.shade, self.gv, self.soil, self.cloud);
			 },
			 create: function(event,ui) {
				 var size = self.$('#slider_shade a.ui-slider-handle').css('left');
				 self.$('#slider_shade span.hack_shade').css('left',size);
				 self.$('#slider_shade a.ui-slider-handle').empty();
				 self.$('#slider_shade a.ui-slider-handle').append('<p id="ht0" class="tooltip">'+self.shade+'</p>');             
			 }
		   });

		  this.$("#slider_gv").slider({
			  range: "100",
			  min: 0,
			  max: 100,         
			  value: self.gv, //TODO: load from model
			  slide: function(event, ui) {
				  // Hack to get red bar resizing
				  self.gv  = ui.value;             
				  self.slide_gv(self.gv);
			  },
			  stop: function(event, ui) {
				 self.gv  = ui.value;             
				  self.trigger('stop', self.low, self.high, self.shade, self.gv, self.soil, self.cloud);              
			  },
			  create: function(event,ui) {
				  var size = self.$('#slider_gv a.ui-slider-handle').css('left');
				  self.$('#slider_gv span.hack_gv').css('left',size);
				  self.$('#slider_gv a.ui-slider-handle').empty();
				  self.$('#slider_gv a.ui-slider-handle').append('<p id="ht0" class="tooltip">'+self.gv+'</p>');             
			  }
			});

		  this.$("#slider_soil").slider({
			  range: "100",
			  min: 0,
			  max: 100,         
			  value: self.soil, //TODO: load from model
			  slide: function(event, ui) {
				  // Hack to get red bar resizing
				  self.soil  = ui.value;             
				  self.slide_soil(self.soil);
			  },
			  stop: function(event, ui) {
				 self.soil  = ui.value;             
				  self.trigger('stop', self.low, self.high, self.shade, self.gv, self.soil, self.cloud);
			  },
			  create: function(event,ui) {
				  var size = self.$('#slider_soil a.ui-slider-handle').css('left');
				  self.$('#slider_soil span.hack_soil').css('left',size);
				  self.$('#slider_soil a.ui-slider-handle').empty();
				  self.$('#slider_soil a.ui-slider-handle').append('<p id="ht0" class="tooltip">'+self.soil+'</p>');             
			  }
			});

			this.$("#slider_cloud").slider({
			  range: "100",
			  min: 0,
			  max: 100,         
			  value: self.cloud, //TODO: load from model
			  slide: function(event, ui) {
				  // Hack to get red bar resizing
				  self.cloud  = ui.value;             
				  self.slide_cloud(self.cloud);
			  },
			  stop: function(event, ui) {
				  self.cloud  = ui.value;             
				  self.trigger('stop', self.low, self.high, self.shade, self.gv, self.soil, self.cloud); 
			  },
			  create: function(event,ui) {
				  var size = self.$('#slider_cloud a.ui-slider-handle').css('left');
				  self.$('#slider_cloud span.hack_cloud').css('left',size);
				  self.$('#slider_cloud a.ui-slider-handle').empty();
				  self.$('#slider_cloud a.ui-slider-handle').append('<p id="ht0" class="tooltip">'+self.cloud+'</p>');             
			  }
			});
	 },
	 slide: function(low, high, silent) {
		 this.low = low;
		 this.high = high;
		 var size = this.$('#slider_forest a.ui-slider-handle:eq(1)').css('left');
		 this.$('#slider_forest span.hack_forest').css('left',size);
		 // Hack for handles tooltip
		 var size0 = this.$('#slider_forest a.ui-slider-handle:eq(0)').css('left');
		 //this.$('span.hack_degradation').css('left', size);
		 this.$('#slider_forest p#ht0').text(this.low);
		 this.$('#slider_forest p#ht1').text(this.high);
		 if(silent !== true) {
			 this.trigger('change', this.low, this.high, this.shade, this.gv, this.soil, this.cloud);
		 }
	 },

	 slide_shade: function(shade, silent) {
		 this.shade = shade;
		 var size = this.$('#slider_shade a.ui-slider-handle').css('left');
		 this.$('#slider_shade span.hack_shade').css('left',size);

		 this.$('#slider_shade p#ht0').text(this.shade);     
		 if(silent !== true) {
			 this.trigger('change', this.low, this.high, this.shade, this.gv, this.soil, this.cloud);
		 }
	 },

	 slide_gv: function(gv, silent) {
		 this.gv = gv;
		 var size = this.$('#slider_gv a.ui-slider-handle').css('left');
		 this.$('#slider_gv span.hack_gv').css('left',size);

		 this.$('#slider_gv p#ht0').text(this.gv);     
		 if(silent !== true) {
			 this.trigger('change', this.low, this.high, this.shade, this.gv, this.soil, this.cloud);
		 }
	 },

	 slide_soil: function(soil, silent) {
		 this.soil = soil;
		 var size = this.$('#slider_soil a.ui-slider-handle').css('left');
		 this.$('#slider_soil span.hack_soil').css('left',size);

		 this.$('#slider_soil p#ht0').text(this.soil);     
		 if(silent !== true) {
			 this.trigger('change', this.low, this.high, this.shade, this.gv, this.soil, this.cloud);
		 }
	 },

	 slide_cloud: function(cloud, silent) {
		 this.cloud = cloud;
		 var size = this.$('#slider_cloud a.ui-slider-handle').css('left');
		 this.$('#slider_cloud span.hack_cloud').css('left',size);

		 this.$('#slider_cloud p#ht0').text(this.cloud);     
		 if(silent !== true) {
			 this.trigger('change', this.low, this.high, this.shade, this.gv, this.soil, this.cloud);
		 }
	 },

	 // set_values([0, 1.0],[0, 1.0])
	 set_values: function(low, high) {
		 low = Math.floor(low*200);
		 high =  Math.floor(high*200);

		 this.el.slider( "values" , 0, low);
		 this.el.slider( "values" , 1, high);
		 //launch an event
		 this.slide(low, high, false);//true);
	 }
});

var EditorTimeSeriesImagePicker = Backbone.View.extend({

	showing : false,

	template : _.template($('#editor-image-picker-tile').html()),

	initialize : function() {
		_.bindAll(this, 'show', 'addTile', 'addTiles', 'sortLayers',
				'search_image_tiles', 'addThumbs', 'send_image_picker');
		var self = this;
		this.el = $(this.template());

		this.cell = this.options.cell;
		this.bbox = this.options.bbox;
		console.log(this.bbox);
		var cell_name = "Define time series features (Cell " + this.cell.get('z') + "/"
				+ this.cell.get('x') + "/" + this.cell.get('y')
				+ ")";
		this.el.find("#cell_name").html(cell_name);
		this.cell_name = this.cell.get('z') + "_"
				+ this.cell.get('x') + "_" + this.cell.get('y');
		
		this.done = false;
		this.timeseries_response = null;
		this.timeseries_layers = new LayerTimeSeriesCollection();
		this.list_tiles_name = [];
		this.date_start = "";
		this.date_end = "";
		this.list_cloud_percent = {};

        this.$("#loading_tiles").show();   
		var request = $.ajax({
			url : "search_tiles_intersect/",
			type : 'POST',
			data : {
				cell_name: this.cell_name,
				bbox: this.bbox    
			},
			dataType : 'json',
			async : true,
			success : function(d) {
				console.log(d.tiles);
				self.$("#loading_tiles").hide();
				self.addTiles(d.tiles);
                      
				return d;
			},
		}).responseText;

		this.$('a.close_editor').click(function(e) {
			self.close();
		});

		this.$('a.close_image_picker').click(function(e) {
			self.close();
		});

		this.$('#open_image_picker').click(function(e) {
			if (e)e.preventDefault();
			self.search_image_tiles(e);
		});

		this.options.parent.append(this.el);		

		var date_end = moment().subtract(31, 'days').calendar();
		date_end     = new Date(date_end); 
		
		var minDate = new Date('1984-01-01');

		var picker_start = new Pikaday({
			field : this.$("#period_start")[0],
			format : 'DD/MMM/YYYY',			
			minDate : minDate,
			maxDate : date_end,
			yearRange : [ 1984, date_end.getFullYear() ],
			onSelect: function() {
				picker_end.setMinDate(this.getDate());
				
		    }

		});
		
		

		var picker_end = new Pikaday({
			field : this.$("#period_end")[0],
			format : 'DD/MMM/YYYY',			
			minDate : minDate,
			maxDate : date_end,
			yearRange : [ 1984, date_end.getFullYear() ],
			onSelect: function() {
				picker_start.setMaxDate(this.getDate());				
		    }
		});
		
		

		this.cloud_percent_list_ids = [];

	},
	search_image_tiles : function(e) {
		this.date_start = this.$("#period_start").val();
		this.date_end = this.$("#period_end").val();
		this.list_cloud_percent = {};
		var lack_percent = false;
		var request = "";
		var self = this;

		for (var i = 0; i < this.list_tiles_name.length; i++) {
			var tile_name = this.list_tiles_name[i];
			var percent = this.$("#cloud_cover_" + tile_name).val();

			if (percent === "0") {
				lack_percent = true;
			}

			this.list_cloud_percent[tile_name] = percent;

		}

		if (this.date_start === "" || this.date_end === "") {
			alert("Some period are none.");
		} else if (lack_percent) {
			alert("Some percentes cloud are none.");
		} else {
			console.log(this.date_start);
			console.log(this.date_end);
			console.log(this.list_cloud_percent);
			this.$("#image_picker_tile").show();
			this.$("#image_picker_tile ul.thumbnails.image_picker_selector").remove();			
			this.$("#loading_cover").show();

			request = $.ajax({
							url : "/imagepicker_tile/",
							type : 'POST',
							data : {
								date_start : this.date_start,
								date_end : this.date_end,
								list_cloud_percent : JSON
										.stringify(this.list_cloud_percent)
							},
							dataType : 'json',
							async : true,
							success : function(d) {
								console.log(d.result);
								self.$("#loading_cover").hide();
								self.$("#image_picker_tile #send_image_picker").click(
										function(e) {
											if (e)
												e.preventDefault();
											self.send_image_picker(e);
										});
								self.addThumbs(d.result);
								return d;
							},
						}).responseText;

		}

	},
	send_image_picker : function(e) {
		if (e)
			e.preventDefault();
		var self = this;
		var thumbs_tile = this.$("#thumbs_tile").val();

		console.log(thumbs_tile);
		this.$("#loading_cover").show();
		var message = $.ajax({
			url : "/imagepicker_tile/",
			type : 'POST',
			data : {
				thumbs_tile: thumbs_tile.join(),
				date_start : this.date_start,
				date_end : this.date_end,
				cell_name : this.cell_name
			},
			dataType : 'json',
			async : true,
			success : function(d) {
				console.log(d.result);
				//alert(d.result);
				//self.$('#make_timeseries')[0].disabled = false
				self.make_timeseries();				
				return d;
			},
			error: function(d){                      				
			    self.$("#loading_cover").hide(); 
				alert("Try again.");

			},
		}).responseText;

		// var s = jQuery.parseJSON(message);
		// alert(s.result);
		// console.log(s);
	},
	make_timeseries : function(e) {
		if (e)e.preventDefault();
		var date_start = this.$("#period_start").val();
		var date_end = this.$("#period_end").val();
		date_start = date_start.split("/");
		date_start = date_start.join("-");
		date_end = date_end.split("/");
		date_end = date_end.join("-");
		var self = this;

		this.timeseries_layers.url = "/timeseries_on_cell/" + date_start + "/"
				+ date_end + "/" + this.cell_name + "/"
		this.timeseries_layers.fetch({
			success : function() {
				self.done = true;
				self.timeseries_response = this;
				self.$("#loading_cover").hide();				
				self.trigger('timeseries_success');
				return this;
			},
			error: function(d){                      				
			    self.$("#loading_cover").hide(); 
				alert("Try again.");

			},
		});

	},
	addThumbs : function(thumbs_tiles) {
		this.$("#thumbs_tile").empty();
		this.$("ul.thumbnails.image_picker_selector").empty();
		this.$("ul.thumbnails.image_picker_selector").attr('disabled', false);

		for ( var thumbs in thumbs_tiles) {
			this.$("#thumbs_tile").append(
					'<optgroup label="' + thumbs.replace("/", "_")
							+ '" id="thumbs_' + thumbs.replace("/", "_")
							+ '"></optgroup>');
			var thumbsViewBaseline = new ThumbsViewBaseline({
				el : this.$("#thumbs_" + thumbs.replace("/", "_"))
			});
			thumbsViewBaseline.collection = new ThumbsBaseline(
					thumbs_tiles[thumbs]);
			thumbsViewBaseline.render();
		}

		this.$("#thumbs_tile").imagepicker({
			show_label : true,
			hide_select : true
		});
		
		this.$('ul.thumbnails.image_picker_selector ul').jScrollPane({autoReinitialise : true});
		
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

	},
	// reorder layers in map
	sortLayers : function() {
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

	addTile : function(tile) {
		var ul = this.el.find('ul#cloud_cover');
		console.log(tile);

		var tile_name = tile['name'].replace("/", "_");

		this.list_tiles_name.push(tile_name);

		ul.append('<li><label for="cloud_cover_' + tile_name +'">' + tile['name']
				+ ': </label><input type="number" id="cloud_cover_' + tile_name
				+ '" value="30" min="0" max="100" step="5"></li>');

	},
	addTiles : function(tiles) {
		if (tiles) {
			this.el.find('ul#cloud_cover').html('');
			var that = this;

			for ( var tile in tiles) {
				console.log(tiles[tile]);
				this.addTile(tiles[tile]);
			}
		}

	},
	show : function(pos, side) {
		this.el.show();// fadeIn();
		this.showing = true;
	},

	close : function() {
		this.el.hide();// fadeOut(0.1);
		this.showing = false;
	}

});

var TimeSeries = Backbone.View.extend({
    el: $("#time_series"),
     events:{
        'click #time_series_select': 'visibility_change',
        'click #time_series_historical_results_select': 'show_time_series_historical_results'
    },
    initialize: function(){
        _.bindAll(this, 'visibility_change', 'set_selected', 'is_timeseries_load', 'show_imagepicker_search', 'genarete_timeseries', 'load_timeseries', 'setting_timeseries_popup', 'change_timeseries');
        this.callerView = this.options.callerView;
        this.polygon_tools = new PolygonToolbarTimeSeries();  

        this.report     = this.options.report;
        this.map        = this.options.mapview;
        this.range_date = new Period_Time_Series({el: this.$("#date_range"), report: this.report, url_send: '/time_series/', callerView: this});
        this.visibility = false;
        this.selected = false;
        
        this.timeseries_layer = new TimeSeriesLayer({mapview: this.map, report: this.report});
        
        this.polygon_tools.timeseries_range.bind('change', this.timeseries_layer.apply_filter);
        this.polygon_tools.timeseries_range.bind('send_timeseries', this.change_timeseries);
        this.polygon_tools.compare.bind('state', function(change_state) {
			self.trigger("compare_state", change_state);
		});
        this.create_polygon_tool = new  PolygonDrawTool({mapview: this.map});
        this.cell_polygons = new CellPolygons({mapview: this.map, operation: 'time_series', report: this.report});
        this.time_series = new LayerTimeSeriesCollection();
        this.time_series.url = 'time_series_historical_results/';
        this.time_series.fetch();
        var that = this;
        this.cell_items = {}
        this.range_date.bind('send_success', function(){that.time_series.add(that.range_date.data_response)});
    },
    create_cell_items : function(cell) {
				var self = this;

				cell.bind('add_cell_intem', function(child){					
					var child_name = child.get('z') + '_' + child.get('x') + '_' + child.get('y')	
								
					if(self.cell_items[child_name] === undefined){
					  	
					  self.cell_items[child_name] = {};	
					  self.cell_items[child_name].cell = child;
					  self.cell_items[child_name].layers = new LayerTimeSeriesCollection();						  
					  $.ajax({							
							url : "/timeseries_last_maps/",
							type : 'POST',
							data : {
								cell_name : child_name
							},
							dataType : 'json',
							async : true,
							success : function(time_series) {
																
								if(time_series.result){
									
									self.cell_items[child_name].time_series = time_series.result;									
									return time_series;
								}
							}
					  });
					}
					
					
				});

	},    	
	load_timeseries: function(cell){
	    this.bind('load_success', function(){						
			cell.trigger('change_cell_action', {color: "rgba(140, 224, 122, 0.8)", text_action: "Enter"});
		});
		this.bind('load_error', function(){						
			cell.trigger('change_cell_action', {color: "rgba(159, 40, 56, 0.8)", text_action: "Try again"});
		});
		cell.trigger('change_cell_action', {color: "rgba(106, 169, 202, 0.8)", color_transition: "rgba(106, 169, 202, 0.6)", text_action: "Loading..."});
		
    },
    setting_timeseries_popup : function(popup, cell) {
		var self = this;

        
          
		var cell_bbox = "";
		cell.bind("get_cell_bbox", function(bbox) {
			cell_bbox = bbox;	
		});

		var cell_name = cell.model.get('z') + '_' + cell.model.get('x')
				+ '_' + cell.model.get('y');
          				
        
		if (this.selected && cell.model.get('z') === 2) {
									
			var popup_el = popup.find('#timeseries_actions');
			var time_series = this.cell_items[cell_name].time_series;

			if (time_series) {
				popup_el.find('#load_timeseries').unbind('click');
				popup_el.find('#load_timeseries').click(
						function(e) {
							if (e){e.preventDefault();}
							self.genarete_timeseries(cell.model);
						});

				popup_el.find('#load_timeseries').show();
				
				popup_el.find('#create_timeseries').unbind('click');
				popup_el.find('#create_timeseries').click(
						function(e) {
							if (e){e.preventDefault();}
							self.show_imagepicker_search(cell.model);							
						});

				popup_el.find('#create_timeseries').show();
			}else{
				popup_el.find('#load_timeseries').hide();
			} 

			popup_el.show();

		} else {			
			popup.find('#timeseries_actions').hide();
		}
	},
	work_mode: function(callback, cell, x, y, z) {
		this.polygon_tools.show();            	
    	var response = this.setting_timeseries_layers(cell);
    	
  	    this.map.reset_layers_map('2', response['time_series'], 'time_series');         	              	    
  	    this.timeseries_layer.map_auth();
 	    
  	    callback.compare_view(cell.get('compare_view'));
 	    
  	   _.each(callback.compare_maps, function(m) {
       		  m.zoom_level = '2';
      		  m.operation_map = 'time_series';
  	   });
 	   
	    this.map.show_zoom_control();
        this.map.show_layers_control();

        this.cell_polygons.polygons.x = x;
        this.cell_polygons.polygons.y = y;
        this.cell_polygons.polygons.z = z;
        this.cell_polygons.polygons.operation = 'time_series';
        this.cell_polygons.polygons.fetch();
      
        this.start_editing_tools(true);
        callback.get_status_layer_map(cell.get('compare_view'));
	},
	change_timeseries: function(timeseries) {
			console.log(timeseries);
			$.ajax({
						url : "/change_timeseries/",
						type : 'POST',
						data : {
							timeseries: JSON.stringify(timeseries),								
						},
						dataType : 'json',
						async : true,
						success : function(timeseries) {								
							console.log(timeseries);
						}
				  });

	},
    show_imagepicker_search : function(cell) {				
        
        cell.bind('bbox');
		bbox = cell.bbox(this.map);
						 
		

		var cell_name = cell.get('z') + "_" + cell.get('x')
				+ "_" + cell.get('y');
		

		var editor_imagepicker = this.cell_items[cell_name].imagepicker;
		var that = this;
		if (editor_imagepicker === undefined) {
			editor_imagepicker = new EditorTimeSeriesImagePicker(
					{
						parent: this.el,
						cell: cell,
						bbox: bbox
					});
			// TODO inserir os layers do response em uma nova lista		
			editor_imagepicker
					.bind(
							'timeseries_success',
							function() {
								that.time_series
										.add(editor_imagepicker.timeseries_layers
												.get_by_cell(this.cell_name))
							});
			this.cell_items[cell_name].imagepicker = editor_imagepicker;
			this.cell_items[cell_name].layers = editor_imagepicker.timeseries_layers;
		}

		/*
		 * if(this.editor_time_series_imagepicker === undefined) {
		 *  }
		 */

		if (editor_imagepicker.showing) {
			// this.editor_time_series_imagepicker.close();
		} else {
			console.log(this.time_series);

			var that = this;

			this.trigger('show_imagepicker_search');
			editor_imagepicker.show();
		}
		
	},
    genarete_timeseries : function(cell){		
        var self = this;						
        var cell_name = cell.get('z') + "_" + cell.get('x')
				+ "_" + cell.get('y');        

        var ts = this.cell_items[cell_name].time_series;

        if(ts){
			var date_start = ts[0].start;
			var date_end = ts[0].end;

			date_start = date_start.split("/");
			date_start = date_start.join("-");
			date_end = date_end.split("/");
			date_end = date_end.join("-");

            this.load_timeseries(cell); 
			this.cell_items[cell_name].layers.url = "/timeseries_on_cell/"
				+ date_start + "/" + date_end + "/" + cell_name + "/"
        						
			this.cell_items[cell_name].layers
					.fetch({
						success : function(d) {
							self.trigger('load_success');							
							return this;
						},
						error : function(d) {
							self.trigger('load_error');							
							return this;
						}
					});
        }else{
			this.show_imagepicker_search(cell);
        }

	},
    set_selected: function(){        
        this.selected = true;
        this.callerView.callback_selected(this);
        this.$("#time_series_select").addClass('time_series_select');
    },
    setting_timeseries_layers: function(cell) {
		var self = this;
		var cell_name = cell.get('z') + '_' + cell.get('x') + '_'
				+ cell.get('y');
						
		var layers = this.cell_items[cell_name].layers;

		if (layers) {
			console.log(layers);
			
			var layer_names = [];
			var map_one_layer_status = "";
			var map_two_layer_status = "";
			var map_three_layer_status = "";
			var map_four_layer_status = "";

			layers.each(function(layer) {
				
				layer_names.push(layer.get('description'));
				
			});

			for (var i = 0; i < layer_names.length; i++) {
				var name = layer_names[i];
				console.log(name);
				if (name.search("RGB/") > -1) {
					map_one_layer_status = map_one_layer_status + '"'
							+ name + '","' + 'false' + '",';
					map_two_layer_status = map_two_layer_status + '"'
							+ name + '","' + 'true' + '",';
					map_three_layer_status = map_three_layer_status
							+ '"' + name + '","' + 'false' + '",';
					map_four_layer_status = map_four_layer_status + '"'
							+ name + '","' + 'false' + '",';
				} else if (name === 'NDFI') {
					map_one_layer_status = map_one_layer_status + '"'
							+ name + '","' + 'false' + '",';
					map_two_layer_status = map_two_layer_status + '"'
							+ name + '","' + 'false' + '",';
					map_three_layer_status = map_three_layer_status
							+ '"' + name + '","' + 'true' + '",';
					map_four_layer_status = map_four_layer_status + '"'
							+ name + '","' + 'false' + '",';
				} else if (name === 'SMA') {
					map_one_layer_status = map_one_layer_status + '"'
							+ name + '","' + 'false' + '",';
					map_two_layer_status = map_two_layer_status + '"'
							+ name + '","' + 'false' + '",';
					map_three_layer_status = map_three_layer_status
							+ '"' + name + '","' + 'false' + '",';
					map_four_layer_status = map_four_layer_status + '"'
							+ name + '","' + 'true' + '",';
				} else if (name.search("TIME_SERIES/") > -1) {
					map_one_layer_status = map_one_layer_status + '"'
							+ name + '","' + 'true' + '",';
					map_two_layer_status = map_two_layer_status + '"'
							+ name + '","' + 'false' + '",';
					map_three_layer_status = map_three_layer_status
							+ '"' + name + '","' + 'false' + '",';
					map_four_layer_status = map_four_layer_status + '"'
							+ name + '","' + 'false' + '",';
				}
			
			}
					
					var available_maps=[
										{
										    id: '6',
										    type: 'google_maps',
										    map_id: 'TERRAIN',
										      visibility: true,
										  description: 'Terrain',
										    enabled: true
										}, 
										{
										    id: '7',
										    type: 'google_maps',
										    map_id: 'SATELLITE',
										       visibility: true,
										 description: 'Satellite'
										},
										{
										    id: '9',
										    type: 'google_maps',
										    map_id: 'ROADMAP',
										        visibility: true,
										description: 'Roadmap'
										}, {
										    id: '8',
										    type: 'google_maps',
										    map_id: 'HYBRID',
										     visibility: true,
										   description: 'Hybrid',
										}


					                  ];
					
					layers.add(available_maps);
					

					map_one_layer_status = map_one_layer_status + '*';
					map_two_layer_status = map_two_layer_status + '*';
					map_three_layer_status = map_three_layer_status + '*';
					map_four_layer_status = map_four_layer_status + '*';

					cell.set({
						"map_one_layer_status" : map_one_layer_status
					});
					cell.set({
						"map_two_layer_status" : map_two_layer_status
					});
					cell.set({
						"map_three_layer_status" : map_three_layer_status
					});
					cell.set({
						"map_four_layer_status" : map_four_layer_status
					});

					return {
						'cell' : cell,
						'time_series' : layers
					};
				} else {
					return false;
				}
			
	},
    is_timeseries_load: function(cell_name) {
    	var timeseries_loaded = this.cell_items[cell_name].layers.get_by_cell(cell_name);
		
		if (timeseries_loaded) {
			this.polygon_tools.timeseries_range.time_series = this.cell_items[cell_name].time_series
				this.polygon_tools.timeseries_range.render(this.cell_items[cell_name].time_series);
			return true;
		} else {
			return false;
		}
				
	},	
    disable: function(){
    	$(this.el).css("background-color", "rgba(0, 0, 0, 0)");
        this.$("#time_series_select h3").css("color", "#999999");
        this.$("#time_series_content").hide();
        this.visibility = false;        
        this.selected = false;
        this.$("#time_series_select").removeClass('time_series_select');
    },
    start_editing_tools: function(state) {
		if(state){
			this.editing_router = new EditingToolsTimeSeries({
				time_series: this
		   });
		}else{
			if(this.editing_router) {
				//unbind all
				this.editing_router.reset();
				this.polygon_tools.reset();
				delete this.editing_router;
			}
		}

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
            this.$("#time_series_list_select").css({
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
            this.$("#time_series_list_select").css({
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
            //this.$("#time_series_content").hide();
            this.visibility = false;
        }
        else{
             $(this.el).css("background-color", "rgba(0, 0, 0, 1)");
            this.$("#time_series_select h3").css("color", "white");
            //this.$("#time_series_content").show();   
            this.visibility = true;
            this.callerView.callback(this);
            this.set_selected();            
        }
    },
    show: function() {
        this.el.show();
    },

    hide: function() {
        this.el.hide();
    }
});


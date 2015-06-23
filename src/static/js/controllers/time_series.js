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

		/*this.$('#make_timeseries').click(function(e) {
			if (e)e.preventDefault();
			console.log('Baseline make_timeseries');
			self.make_timeseries(e);
		});*/

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
			//this.$("#image_picker_baseline #loading_image_picker").show();
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
				self.trigger('time_series_success');
				return this;
			}
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
        _.bindAll(this, 'visibility_change', 'set_selected', 'is_timeseries_load', 'enter_cell', 'show_imagepicker_search', 'setting_timeseries_layers');
        this.callerView = this.options.callerView;
        this.report     = this.options.report;
        this.map        = this.options.mapview;
        this.range_date = new Period_Time_Series({el: this.$("#date_range"), report: this.report, url_send: '/time_series/', callerView: this});
        this.visibility = false;
        this.selected = false;
        
        this.timeseries_layer = new TimeSeriesLayer({mapview: this.map, report: this.report});
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
					  self.cell_items[child_name]['cell'] = child;
					  self.cell_items[child_name]['layers'] = new LayerTimeSeriesCollection();						  
					}
					
					
				});

	},    
	enter_cell: function(cell){                
        /*cell.bind('bbox');
		var cell_bbox = cell.bbox(this.map);*/ 

		var cell_name = cell.get('z') + "_" + cell.get('x')
				+ "_" + cell.get('y');

		//var baseline_lay = this.baselines.get_by_cell(cell_name);
		var ts = this.cell_items[cell_name].time_series;
		
		if(ts){
			this.load_timeseries(this.cell_items[cell_name].cell);
			
		}else{
			this.show_imagepicker_search(cell);
			
		}

	},
	load_baselines_saved: function(cell){
		var self = this;

		var timeseries_saved = new LayerTimeSeriesCollection();



		timeseries_saved.url = 'timeseries/' + cell.get('z')+'_'+cell.get('x')+'_'+cell.get('y') + '/';
		timeseries_saved.fetch({
		   success: function(result){
			   timeseries_saved.each(function(time_series){
				 var cell_name = time_series.get('cell');				                          		                          	
				 console.log(self.cell_items[cell_name].cell); 
				 self.cell_items[cell_name].time_series = time_series;


				 self.load_baseline(self.cell_items[cell_name].cell);
			   });
			   return this;
		   }	
		});




	},
	load_timeseries: function(cell){
	    this.bind('load_success', function(){						
			cell.trigger('change_cell_action', {color: "rgba(140, 224, 122, 0.8)", text_action: "Enter"});
		});
		cell.trigger('change_cell_action', {color: "rgba(106, 169, 202, 0.8)", color_transition: "rgba(106, 169, 202, 0.6)", text_action: "Loading..."});
		
		this.genarete_timeseries(cell);

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
		 * if(this.editor_baseline_imagepicker === undefined) {
		 *  }
		 */

		if (editor_imagepicker.showing) {
			// this.editor_baseline_imagepicker.close();
		} else {
			console.log(this.time_series);

			var that = this;

			this.trigger('show_imagepicker_search');
			editor_imagepicker.show();
		}
		
	},
    genarete_timeseries : function(cell){								
        var cell_name = cell.get('z') + "_" + cell.get('x')
				+ "_" + cell.get('y');        

        var ts = this.cell_items[cell_name].time_series;
        var date_start = ts.get('start');
        var date_end = ts.get('end');
               
	 
		date_start = date_start.split("/");
		date_start = date_start.join("-");
		date_end = date_end.split("/");
		date_end = date_end.join("-");

		cell.bind('bbox');
		var bbox = cell.bbox(this.map); 

		

		//var baseline_lay = this.baselines.get_by_cell(cell_name);
		
		
		var editor_imagepicker = this.cell_items[cell_name].imagepicker;
		var self = this;
		if (editor_imagepicker === undefined) {
			editor_imagepicker = new EditorBaselineImagePicker(
					{
						parent : this.el,
						cell : cell,
						bbox: bbox
					});
			/*editor_imagepicker
					.bind(
							'time_series_success',
							function() {
								self.time_series
										.add(editor_imagepicker.timeseries_layers
												.get_by_cell(this.cell_name))
							});*/
			this.cell_items[cell_name].imagepicker = editor_imagepicker;
			this.cell_items[cell_name].layers = editor_imagepicker.timeseries_layers;
		}

		this.cell_items[cell_name].layers.url = "/timeseries_on_cell/"
				+ date_start + "/" + date_end + "/" + cell_name + "/"
				
        						
		this.cell_items[cell_name].layers
				.fetch({
					success : function() {
						self.cell_items[cell_name].imagepicker.done = true;
						self.cell_items[cell_name].imagepicker.timeseries_response = this;								
						self.cell_items[cell_name].imagepicker.trigger('time_series_success');
						self.trigger('load_success');
						//alert("Baseline loaded.");
						return this;
					}
				});

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
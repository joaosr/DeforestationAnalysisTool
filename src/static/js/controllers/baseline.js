var ThumbBaseline = Backbone.Model.extend();

var ThumbsBaseline = Backbone.Collection.extend({
	model : ThumbBaseline,
	parse : function(result) {
		console.log(result.result);
		return result.result;
	}
});

var ThumbViewBaseline = Backbone.View
		.extend({
			tagName : "option",
			initialize : function() {
				_.bindAll(this, 'render');
			},
			render : function() {
				console.log(this.model.get('thumb'));
				$(this.el).attr(
						'data-img-label',
						this.model.get('date') + ' <br> '
								+ this.model.get('map_image')).html();
				$(this.el).attr(
						'data-img-src',
						'https://earthengine.googleapis.com/api/thumb?thumbid='
								+ this.model.get('thumb') + '&token='
								+ this.model.get('token')).html(
						this.model.get("date"));
				$(this.el).attr(
						'value',
						this.model.get('date') + '__' + this.model.get('tile')
								+ '__' + this.model.get('map_image')).html();
				$(this.el).attr(
						'id',
						this.model.get('date') + '__' + this.model.get('tile')
								+ '__' + this.model.get('map_image')).html();
				return this;
				thumbs
			}
		});

var ThumbsViewBaseline = Backbone.View.extend({
	el : $("#thumb"),
	initialize : function() {
		_.bindAll(this, 'addOne', 'addAll', 'render');
		console.log("Aqui");
		this.collection = new ThumbsBaseline();
		this.collection.bind('reset', this.addAll());
	},
	// TODO 13/02/15 mudança na implementação do fluxo de uso do sistema, esse
	// método pode não ser mais necessário
	change_sensor : function(sensor) {
		this.tilesView.setSensor(sensor);
	},
	addOne : function(thumb) {
		console.log('mais aqui');
		var thumbViewBaseline = new ThumbViewBaseline({
			model : thumb
		});
		$(this.el).append(thumbViewBaseline.render().el);
	},
	addAll : function() {
		console.log('Agora aqui');
		this.collection.each(this.addOne);
	},
	render : function() {
		this.addAll();
	}
});

var Period = Backbone.View
		.extend({
			// el: $("#range_select"),
			events : {
				'click #submit_date_picker' : 'send_date_report',
				'click #date_range_select' : 'visibility_change'
			},
			initialize : function() {
				_.bindAll(this, 'update_range_date', 'render',
						'visibility_change');
				var self = this;
				this.report = this.options.report;
				this.callerView = this.options.callerView;
				// this.$("#report-date").html(this.report.escape('str'));
				// this.$("#report-date-end").html(this.report.escape('str_end'));
				this.visibility = false;
				var start = this.report.escape('str');
				this.start_date = moment(new Date(start)).format("DD/MMM/YYYY");
				var end = this.report.escape('str_end');
				this.end_date = moment(new Date(end)).format("DD/MMM/YYYY");
				this.data_request = null;

				this.$('#date_timepicker_start').attr("value", this.start_date)
						.html();
				this.$('#date_timepicker_end').attr("value", this.end_date)
						.html();
				this.visibility_picker_range = false;
				this.url_send = this.options.url_send;

				var picker_start = new Pikaday({
					field : this.$("#date_timepicker_start")[0],
					format : 'DD/MMM/YYYY',
					minDate : new Date('01/03/1985'),
					maxDate : new Date(this.$('#date_timepicker_end').val()),
					yearRange : [ 1985, new Date().getFullYear() ],
					onOpen : function() {
						this.setMaxDate(new Date(self.$('#date_timepicker_end')
								.val()));
					}
				});

				var picker_end = new Pikaday({
					field : this.$("#date_timepicker_end")[0],
					format : 'DD/MMM/YYYY',
					minDate : new Date(this.$('#date_timepicker_start').val()),
					maxDate : new Date(this.end_date),
					yearRange : [ 1985, new Date().getFullYear() ],
					onOpen : function() {
						this.setMinDate(new Date(self.$(
								'#date_timepicker_start').val()));
					}
				});

			},
			send_date_report : function(e) {
				if (e)
					e.preventDefault();

				var date_start = this.$('#date_timepicker_start').val();
				var date_end = this.$('#date_timepicker_end').val();

				this.$("#loading_range_picker").show();
				var that = this;
				var request = $.ajax({
					url : this.url_send,
					type : 'POST',
					data : {
						date_start : date_start,
						date_end : date_end
					},
					dataType : 'json',
					async : true,
					success : function(d) {
						that.$("#loading_range_picker").hide();
						alert(d.result.message);
						console.log(d);
						that.data_request = d.result.data;
						that.trigger('send_success');
						console.log(that.data_request);
						return d;
					},
				}).responseText;

				// var s = jQuery.parseJSON(message);
				// alert(s.result);
				// console.log(s);
			},
			set_range_date_input : function(report) {
				var start = report.escape('str');
				var start_date = moment(new Date(start)).format("DD/MMM/YYYY");
				var end = report.escape('str_end');
				var end_date = moment(new Date(end)).format("DD/MMM/YYYY");

				this.$("#range_picker").attr("value",
						start_date + ' to ' + end_date).html();
			},
			update_range_date : function(evt, obj) {
				var dates = obj.value.split(' to ');
				console.log(dates[0] + ' - ' + dates[1]);
				this.start_date = dates[0];
				this.end_date = dates[1];
			},
			render : function() {
				return this;
			},
			visibility_change : function(e) {
				if (e)
					e.preventDefault();
				if (this.visibility) {
					this.$("#form_date_range").hide();
					this.$("#date_range_select").css({
						"color" : "white",
						"text-shadow" : "0 1px black",
						"background" : "none",
					});
					this.visibility = false;
				} else {
					this.$("#form_date_range").show();
					this
							.$("#date_range_select")
							.css(
									{
										"color" : "rgb(21, 2, 2)",
										"text-shadow" : "0 1px white",
										"background" : "-webkit-gradient(linear, 50% 0%, 50% 100%, from(#E0E0E0), to(#EBEBEB))",
									});
					this.visibility = true;
					this.render();
					// this.callerView.callback(this);
				}

			},
			show : function() {
				this.el.show();
			},

			hide : function() {
				this.el.hide();
			}
		});

var LayerEditorBaseline = Backbone.View.extend({

	showing : false,

	template : _.template($('#baseline-layers').html()),

	initialize : function() {
		_.bindAll(this, 'show', 'addLayer', 'addLayers', 'sortLayers');
		var self = this;

		this.item_view_map = {};
		this.layers = this.options.layers;
		this.el = $(this.template());
		this.options.parent.append(this.el);
		this.addLayers(this.layers);
		this.el.find('ul').jScrollPane({
			autoReinitialise : true
		});

		this.el.find('ul, div.jspPane').sortable({
			revert : false,
			items : '.sortable',
			axis : 'y',
			cursor : 'pointer',
			stop : function(event, ui) {
				$(ui.item).removeClass('moving');
				//
				// DONT CALL THIS FUNCTION ON beforeStop event, it will crash :D
				//
				self.sortLayers();
			},
			start : function(event, ui) {
				$(ui.item).addClass('moving');
			}
		});
		this.layers.trigger('reset');
		/*this.bind('change_layers', function() {
			self.addLayers(self.layers)
		});*/
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

	addLayer : function(layer) {
		if (!layer.hidden) {
			var ul = this.el.find('ul');
			if (layer.get('color') !== undefined) {
				var view = new SwitchLayerView({
					model : layer
				});
			} else {
				var view = new LayerView({
					model : layer
				});
			}
			ul.append(view.render().el);
			this.item_view_map[view.id] = view;
		}
	},
	addLayers : function(layers) {
		this.el.find('ul').html('');
		console.log("Add Now!!!!!!!");
		var that = this;
		layers.raster_layers().each(function(m) {
			if (m.get('visibility') || m.get('type') == 'baseline') {
				that.addLayer(m);
			}
		});
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

var EditingToolsBaseline = Backbone.View.extend({

    initialize: function() {
        _.bindAll(this, 'change_state', 'new_polygon', 'reset', 'polygon_mouseout', 'polygon_mouseover');
        this.state = 'move';
        this.baseline = this.options.baseline;
        this.baseline.polygon_tools.bind('state', this.change_state);
    },

    new_polygon: function(data) {
        //this.baseline.cell_polygons.polygons.create(data);
        var p = new Polygon(data);
        this.baseline.cell_polygons.polygons.add(p);
        window.loading_small.loading('saving poly');
        p.save(null, {
            success: function() {
                window.loading_small.finished('saving poly');
            }
        });
    },

    //reset to initial state
    reset: function() {
        this.baseline.baseline_layer.unbind('polygon', this.new_polygon);
        this.baseline.create_polygon_tool.unbind('polygon', this.new_polygon);
        this.baseline.baseline_layer.editing_state = false;
        this.baseline.cell_polygons.editing_state = false;
        this.baseline.create_polygon_tool.editing_state(false);
        this.baseline.polygon_tools.polytype.hide();
        //this.baseline.map.$("canvas").css('cursor','auto');
        this.baseline.cell_polygons.unbind('click_on_polygon', this.baseline.create_polygon_tool.edit_polygon);
        this.baseline.cell_polygons.unbind('mouseover', this.polygon_mouseover);
        this.baseline.cell_polygons.unbind('mouseout', this.polygon_mouseout);
        this.baseline.map.map.setOptions({draggableCursor: 'default'});
    },

    editing_mode: function() {
        this.baseline.cell_polygons.bind('click_on_polygon', this.baseline.create_polygon_tool.edit_polygon);
    },

    polygon_mouseout: function() {
        var st = this.state;
        var cursors_pos = {
            'edit': '4 4',
            'auto': '7 7',
            'remove': '6 6',
            'draw': '4 16'
        };
        this.baseline.map.map.setOptions({draggableCursor: 'url(/static/img/cursor_' + st +'.png) ' + cursors_pos[st] + ', default'});
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
                this.baseline.cell_polygons.bind('mouseover', this.polygon_mouseover);
                this.baseline.cell_polygons.bind('mouseout', this.polygon_mouseout);
                break;
            case 'remove':
                this.baseline.cell_polygons.editing_state = true;
                this.baseline.cell_polygons.bind('mouseover', this.polygon_mouseover);
                this.baseline.cell_polygons.bind('mouseout', this.polygon_mouseout);
                break;
            case 'draw':
                this.baseline.create_polygon_tool.editing_state(true);
                this.baseline.polygon_tools.polytype.bind('state', this.baseline.create_polygon_tool.poly_type);
                this.baseline.create_polygon_tool.bind('polygon', this.new_polygon);
                this.baseline.polygon_tools.polytype.show();
                this.baseline.polygon_tools.polytype.select('def');
                break;
            case 'auto':
                this.baseline.baseline_layer.unbind('polygon', this.new_polygon);
                this.baseline.baseline_layer.bind('polygon', this.new_polygon);
                this.baseline.baseline_layer.editing_state = true;
                //this.baseline.map.$("canvas").css('cursor','crosshair');
                break;
        }
        console.log(st);
    }

});

var PolygonToolbarBaseline = Backbone.View.extend({

    el: $("#work_toolbar_baseline"),

    events: {
        'click #compare': 'none',
        'click #ndfirange': 'none',
        'click .class_selector': 'visibility_change'
    },

    initialize: function() {
        _.bindAll(this, 'show', 'hide', 'change_state', 'reset', 'visibility_change');
        this.buttons = new ButtonGroup({el: this.$('#baseline_selection')});
        this.polytype = new ButtonGroup({el: this.$('#baseline_polytype')});
        this.baseline_range = new RangeSliderBaseline({el: this.$("#baseline_maptools")});
        this.compare = new ButtonGroup({el: $("#compare_buttons")});
        this.polytype.hide();
        this.buttons.bind('state', this.change_state);
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

var EditorBaselineImagePicker = Backbone.View.extend({

	showing : false,

	template : _.template($('#editor-baseline-image-picker').html()),

	initialize : function() {
		_.bindAll(this, 'show', 'addTile', 'addTiles', 'sortLayers',
				'search_image_tiles', 'addThumbs', 'send_image_picker');
		var self = this;
		this.el = $(this.template());

		this.cell = this.options.cell;
		this.bbox = this.options.bbox;
		console.log(this.bbox);
		var cell_name = "Define baseline features (Cell " + this.cell.model.get('z') + "/"
				+ this.cell.model.get('x') + "/" + this.cell.model.get('y')
				+ ")";
		this.el.find("#cell_name").html(cell_name);
		this.cell_name = this.cell.model.get('z') + "_"
				+ this.cell.model.get('x') + "_" + this.cell.model.get('y');
		
		this.done = false;
		this.baseline_response = null;
		this.baseline_layers = new LayerBaselineCollection();
		this.list_tiles_name = [];
		this.date_start = "";
		this.date_end = "";
		this.list_cloud_percent = {};

		var request = $.ajax({
			url : "baseline_search_tiles/",
			type : 'POST',
			data : {
				cell_name: this.cell_name,
				bbox: this.bbox    
			},
			dataType : 'json',
			async : true,
			success : function(d) {
				console.log(d.tiles);
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

		this.$('#genarete_baseline').click(function(e) {
			if (e)e.preventDefault();
			console.log('Baseline genarete_baseline');
			self.genarete_baseline(e);
		});

		this.options.parent.append(this.el);

		var date_start = moment().subtract(31, 'days').calendar();

		var date_end = new Date();
		
		var minDate = new Date('1984-01-01');

		var picker_start = new Pikaday({
			field : this.$("#period_start")[0],
			format : 'DD/MMM/YYYY',
			defaultDate: minDate,
			minDate : minDate,
			maxDate : new Date(date_start),
			yearRange : [ 1984, date_end.getFullYear() ],
			onSelect: function() {
				picker_end.setMinDate(this.getDate());
		    }/*,
			onOpen : function() {
				this.setMaxDate(new Date(self.$("#period_end").val()));
			}*/

		});
		
		

		var picker_end = new Pikaday({
			field : this.$("#period_end")[0],
			format : 'DD/MMM/YYYY',
			defaultDate: new Date('1984-12-31'),
			minDate : minDate,
			maxDate : date_end,
			yearRange : [ 1984, date_end.getFullYear() ],
			onSelect: function() {
				picker_end.setMinDate(this.getDate());
		    }/*,
			onOpen : function() {
				this.setMinDate(new Date(self.$("#period_start").val()));
			}*/
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
			this.$("#image_picker_baseline").show();
			this.$("#image_picker_baseline ul.thumbnails.image_picker_selector").empty();
			this.$("#image_picker_baseline #loading_image_picker").show();

			request = $.ajax({
				url : "/imagepicker_baseline/",
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
					self.$("#image_picker_baseline #loading_image_picker")
							.hide();
					self.$("#image_picker_baseline #send_image_picker").click(
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
		var thumbs_baseline = this.$("#thumbs_baseline").val();

		console.log(thumbs_baseline);
		var message = $.ajax({
			url : "/imagepicker_baseline/",
			type : 'POST',
			data : {
				thumbs_baseline : thumbs_baseline.join(),
				date_start : this.date_start,
				date_end : this.date_end,
				cell_name : this.cell_name
			},
			dataType : 'json',
			async : true,
			success : function(d) {
				console.log(d.result);
				alert(d.result);
				self.$('#genarete_baseline')[0].disabled = false
				return d;
			},
		}).responseText;

		// var s = jQuery.parseJSON(message);
		// alert(s.result);
		// console.log(s);
	},
	genarete_baseline : function(e) {
		if (e)e.preventDefault();
		var date_start = this.$("#period_start").val();
		var date_end = this.$("#period_end").val();
		date_start = date_start.split("/");
		date_start = date_start.join("-");
		date_end = date_end.split("/");
		date_end = date_end.join("-");
		var self = this;

		this.baseline_layers.url = "/baseline_on_cell/" + date_start + "/"
				+ date_end + "/" + this.cell_name + "/"
		this.baseline_layers.fetch({
			success : function() {
				self.done = true;
				self.baseline_response = this;
				alert("Baseline created.");
				self.trigger('baseline_success');
				return this;
			}
		});

	},
	addThumbs : function(thumbs_tiles) {
		this.$("#thumbs_baseline").empty();
		this.$("ul.thumbnails.image_picker_selector").empty();
		this.$("ul.thumbnails.image_picker_selector").attr('disabled', false);

		for ( var thumbs in thumbs_tiles) {
			this.$("#thumbs_baseline").append(
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

		this.$("#thumbs_baseline").imagepicker({
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
				+ '" value="30" min="0" max="100"></li>');

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

var Baseline = Backbone.View.extend({
			el : $("#baseline"),
			events : {
				'click #baseline_select' : 'visibility_change',
				'click #baseline_list_select' : 'show_baseline_list'
			},
			initialize : function() {
				_.bindAll(this, 'callback', 'hide_report_tool_bar',
						'show_report_tool_bar', 'hide_image_picker',
						'show_image_picker', 'visibility_change',
						'setting_baseline_popup', 'show_imagepicker_search',
						'set_selected', 'genarete_baseline');
				var self = this;
				
				this.callerView = this.options.callerView;
				this.polygon_tools = new PolygonToolbarBaseline();
				
				this.report = this.options.report;
				this.map = this.options.mapview;
				// this.setting_report_data();
				this.report_tool_bar = new Period({
					el : this.$("#date_range"),
					report : this.report,
					url_send : '/baseline_report/',
					callerView : this
				});
				// this.image_picker = new ImagePicker({el:
				// this.$("#image_picker"), callerView: this});
				this.visibility = false;
				this.selected = false;

				this.baseline_layer = new BaselineLayer({mapview: this.map, report: this.report});
				this.polygon_tools.baseline_range.bind('change', this.baseline_layer.apply_filter);
				this.polygon_tools.bind('visibility_change', this.baseline_layer.class_visibility);
				this.polygon_tools.compare.bind('state', function(change_state) {
					self.trigger("compare_state", change_state);
				});
				this.create_polygon_tool = new  PolygonDrawTool({mapview: this.map});
				this.cell_polygons = new CellPolygons({mapview: this.map});
				//this.polygon_tools.baseline_range.bind('stop', this.change_baseline);
				this.baselines = new LayerBaselineCollection();
				this.baselines.url = 'baseline_list/';
				this.baselines.fetch();
				var that = this;
				this.report_tool_bar.bind('send_success', function() {
					that.baselines.add(that.report_tool_bar.data_request)
				});
				this.item_view_imagepicker = {};
			},
			baselines_cell : function(cell_name) {
				this.baselines.url = 'baseline/' + cell_name + '/';
				this.baselines.fetch(/*
										 * { success: function(){ self.done =
										 * true; self.baseline_response = this;
										 * self.trigger('baseline_success');
										 * return this; } }
										 */);

			},
			show_baseline_list : function(e) {
				if (e)
					e.preventDefault();
				if (this.layer_editor_baseline === undefined) {
					this.layer_editor_baseline = new LayerEditorBaseline({
						parent : this.$('#baseline_list'),
						layers : this.baselines
					});
				}

				if (this.layer_editor_baseline.showing) {
					this.layer_editor_baseline.close();
					this.$("#baseline_list_select").css({
						"color" : "white",
						"text-shadow" : "0 1px black",
						"background" : "none",
					});
				} else {
					console.log(this.baselines);
					this.layer_editor_baseline.layers = this.baselines;
					this.layer_editor_baseline.trigger('change_layers');
					var that = this;
					this.baselines.each(function(layer) {
						var layer_map = that.map.layers.get(layer.get('id'));
						if (layer_map) {
							// Already exist
						} else {
							that.map.layers.add(layer);
						}
					});

					this.layer_editor_baseline.layers.each(function(m) {
						if (!m.get('visibility')) {
							that.layer_editor_baseline.layers.remove(m);
						}
					});
					this
							.$("#baseline_list_select")
							.css(
									{
										"color" : "rgb(21, 2, 2)",
										"text-shadow" : "0 1px white",
										"background" : "-webkit-gradient(linear, 50% 0%, 50% 100%, from(#E0E0E0), to(#EBEBEB))",
									});
					this.trigger('show_baseline_list');
					this.layer_editor_baseline.show();
				}
			},
			change_baseline: function(low, high) {
	            //var baseline = this.map.layer.;
	            cell.set({
	                'ndfi_low': low/200.0,
	                'ndfi_high': high/200.0
	            });
	            cell.save();
	        },
			setting_report_data : function() {
				var date = new Date();
				var current_month = date.getMonth();
				var current_year = date.getYear();

				var new_start = moment(
						new Date(current_year, current_month_sad + 1, 1))
						.format("DD-MM-YYYY");
				var new_end = moment(
						new Date(current_year, current_month_sad + 1, 0))
						.format("DD-MM-YYYY");
				console.log("Nem start: " + new_start);
				this.report.set('str', new_start);
				this.report.set('str_end', new_end);

			},
			setting_baseline_popup : function(popup, cell) {
				var self = this;
				
				
				var cell_bbox = "";
				cell.bind("get_cell_bbox", function(bbox) {
					cell_bbox = bbox;	
				});
				
				var cell_name = cell.model.get('z') + '_' + cell.model.get('x')
						+ '_' + cell.model.get('y');
				if (this.selected && cell.model.get('z') == '2') {
					// popup.append( "<p>Test</p>" );
					var setting_baseline = popup.find('#setting_baseline');
					var baseline_lay = this.baselines.get_by_cell(cell_name);

					if (baseline_lay) {
						setting_baseline.find('#rebuild_baseline').unbind('click');
						setting_baseline.find('#rebuild_baseline').click(
								function(e) {
									if (e){e.preventDefault();}
									self.show_imagepicker_search(e, cell, cell_bbox);
								});

						
						console.log(cell_name);
						setting_baseline.find('#load_baseline').unbind('click');
						setting_baseline.find('#load_baseline').click(
								function(e) {
									e.preventDefault();
									console.log(cell_name);
									var that = this;
									$(this)[0].disabled = true;
									
									
									self.bind('load_success', function(){
										$(that)[0].disabled = false;
										
									})
									
									self.genarete_baseline(e, cell, baseline_lay.get('start'), baseline_lay.get('end'), cell_name, cell_bbox, this);
								});
						
						setting_baseline.find('#load_baseline').show();
						setting_baseline.find('#rebuild_baseline').show();
						setting_baseline.find('#build_baseline').hide();
					} else {
						setting_baseline.find('#build_baseline').unbind('click');
						setting_baseline.find('#build_baseline').click(
								function(e) {
									if (e){e.preventDefault();}
									    self.show_imagepicker_search(e, cell, cell_bbox);
								});

						setting_baseline.find('#load_baseline').hide();
						setting_baseline.find('#rebuild_baseline').hide();
						setting_baseline.find('#build_baseline').show();
					}

					setting_baseline.show();

				} else {
					var setting_baseline = popup.find('#setting_baseline')
					setting_baseline.hide();
				}
			},
			cell_done : function(cell_name) {
				var item = this.item_view_imagepicker[cell_name];
				if (item) {
					return item.done;
				} else {
					return false;
				}

			},
			setting_baseline_layers : function(cell) {
				var self = this;
				var cell_name = cell.get('z') + '_' + cell.get('x') + '_'
						+ cell.get('y');
				var item = this.item_view_imagepicker[cell_name];

				if (item) {
					console.log(item.baseline_layers);
					// this.baselines = new
					// LayerCollection(item.baseline_response);
					var layer_names = [];
					var map_one_layer_status = "";
					var map_two_layer_status = "";
					var map_three_layer_status = "";
					var map_four_layer_status = "";
										
					item.baseline_layers.each(function(layer) {
						// var layer_map = self.map.layers.get(layer.get('id'));
						layer_names.push(layer.get('description'));
						// if(layer_map){
						// Already exist
						// }else{
						// self.map.layers.add(layer);
						// }
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
						} else if (name.search("BASELINE/") > -1) {
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
					
					item.baseline_layers.add(available_maps);
					

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
						'baseline' : item.baseline_layers
					};
				} else {
					return false;
				}

			},
			show_imagepicker_search : function(e, cell, bbox) {
				if (e)e.preventDefault();

				var cell_name = cell.model.get('z') + "_" + cell.model.get('x')
						+ "_" + cell.model.get('y');

				this.editor_baseline_imagepicker = this.item_view_imagepicker[cell_name];
				var that = this;
				if (this.editor_baseline_imagepicker === undefined) {
					this.editor_baseline_imagepicker = new EditorBaselineImagePicker(
							{
								parent: this.el,
								cell: cell,
								bbox: bbox
							});
					this.editor_baseline_imagepicker
							.bind(
									'baseline_success',
									function() {
										that.baselines
												.add(that.editor_baseline_imagepicker.baseline_layers
														.get_by_cell(this.cell_name))
									});
					this.item_view_imagepicker[cell_name] = this.editor_baseline_imagepicker;
				}

				/*
				 * if(this.editor_baseline_imagepicker === undefined) {
				 *  }
				 */

				if (this.editor_baseline_imagepicker.showing) {
					// this.editor_baseline_imagepicker.close();
				} else {
					console.log(this.baselines);

					var that = this;

					this.trigger('show_imagepicker_search');
					this.editor_baseline_imagepicker.show();
				}
			},
			genarete_baseline : function(e, cell, date_start, date_end, cell_name, bbox) {				
				
				date_start = date_start.split("/");
				date_start = date_start.join("-");
				date_end = date_end.split("/");
				date_end = date_end.join("-");
				
				this.editor_baseline_imagepicker = this.item_view_imagepicker[cell_name];
				var self = this;
				if (this.editor_baseline_imagepicker === undefined) {
					this.editor_baseline_imagepicker = new EditorBaselineImagePicker(
							{
								parent : this.el,
								cell : cell,
								bbox: bbox
							});
					this.editor_baseline_imagepicker
							.bind(
									'baseline_success',
									function() {
										self.baselines
												.add(self.editor_baseline_imagepicker.baseline_layers
														.get_by_cell(this.cell_name))
									});
					this.item_view_imagepicker[cell_name] = this.editor_baseline_imagepicker;
				}

				this.editor_baseline_imagepicker.baseline_layers.url = "/baseline_on_cell/"
						+ date_start + "/" + date_end + "/" + cell_name + "/"
						
                						
				this.editor_baseline_imagepicker.baseline_layers
						.fetch({
							success : function() {
								self.editor_baseline_imagepicker.done = true;
								self.editor_baseline_imagepicker.baseline_response = this;
								self.editor_baseline_imagepicker.trigger('baseline_success');
								self.trigger('load_success');
								alert("Baseline loaded.");
								return this;
							}
						});

			},
			set_selected : function() {
				this.selected = true;
				this.callerView.callback_selected(this);
				this.$("#baseline_select").addClass('baseline_select');
			},
			disable : function() {
				$(this.el).css("background-color", "rgba(0, 0, 0, 0)");
				this.$("#baseline_select h3").css("color", "#999999");
				this.$("#baseline_content").hide();
				this.visibility = false;
				this.selected = false;
				this.$("#baseline_select").removeClass('baseline_select');
			},
			callback : function(view) {
				if (view === this.report_tool_bar
						&& this.report_tool_bar.visibility) {
					this.hide_image_picker();
				}
				/*
				 * else if(view === this.image_picker &&
				 * this.image_picker.visibility){ this.hide_report_tool_bar(); }
				 */
			},
			hide_report_tool_bar : function() {
				if (this.report_tool_bar.visibility) {
					this.report_tool_bar.visibility_change();
				}
			},
			show_report_tool_bar : function() {
				if (!this.report_tool_bar.visibility) {
					this.report_tool_bar.visibility_change();
				}
			},
			hide_image_picker : function() {
				if (this.image_picker.visibility) {
					this.image_picker.visibility_change();
				}
			},
			show_image_picker : function() {
				if (!this.image_picker.visibility) {
					this.image_picker.visibility_change();
					this.image_picker.bind('visibility_change', this
							.show_baseline_list(null));
				}
			},
			show_selected : function() {
				if (this.selected) {
					this.el.show();
				} else {
					this.el.hide();
				}
			},
			show : function() {
				this.el.show();
			},

			hide : function() {
				this.el.hide();
			},
			start_editing_tools: function(state) {
				if(state){
					this.editing_router = new EditingToolsBaseline({
	                    baseline: this
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
			visibility_change : function() {
				if (this.visibility) {
					$(this.el).css("background-color", "rgba(0, 0, 0, 0)");
					this.$("#baseline_select h3").css("color", "#999999");
					//this.$("#baseline_content").hide();
					this.visibility = false;
				} else {
					$(this.el).css("background-color", "rgba(0, 0, 0, 1)");
					this.$("#baseline_select h3").css("color", "white");
					//this.$("#baseline_content").show();
					this.visibility = true;
					this.callerView.callback(this);
					this.set_selected();
				}

			}
		});

//jqueryui slider wrapper
//triggers change with values
var RangeSliderBaseline = Backbone.View.extend({
 initialize: function() {
     _.bind(this, 'slide', 'slide_shade', 'slide_gv', 'slide_soil', 'set_values');
     var self = this;
     this.low = 165;
     this.high = 175;
     this.shade = 70;
     this.gv = 15;
     this.soil = 10;
     
     this.$("#slider_forest").slider({
             range: true,
             min: 0,
             max: 200,
             //values: [40, 60], //TODO: load from model
             values: [165, 175], //TODO: load from model
             slide: function(event, ui) {
                 // Hack to get red bar resizing

                 self.low  = ui.values[0];
                 self.high = ui.values[1];
                 self.slide(self.low, self.high);
             },
             stop: function(event, ui) {
            	 self.low  = ui.values[0];
            	 self.high = ui.values[1];
                 self.trigger('stop', self.low, self.high);
                 //self.trigger('stop', low);
             },
             create: function(event,ui) {
                 // Hack to get red bar resizing
                 var size = self.$('#slider_forest a.ui-slider-handle:eq(1)').css('left');
                 self.$('#slider_forest span.hack_forest').css('left',size);
                 // Hack for handles tooltip
                 
                 var size0 = self.$('#slider_forest a.ui-slider-handle:eq(0)').css('left');

                 self.$('#slider_forest a.ui-slider-handle:eq(0)').append('<p id="ht0" class="tooltip">165</p>');
                 self.$('#slider_forest a.ui-slider-handle:eq(1)').append('<p id="ht1" class="tooltip">175</p>');
             }
      });
     
      this.$("#slider_shade").slider({
         range: "100",
         min: 0,
         max: 100,         
         value: 70, //TODO: load from model
         slide: function(event, ui) {
             // Hack to get red bar resizing
             self.shade  = ui.value;             
             self.slide_shade(self.shade);
         },
         stop: function(event, ui) {
        	 self.shade  = ui.value;             
             self.trigger('stop', self.low, self.high, self.shade);
         },
         create: function(event,ui) {
             
             self.$('#slider_shade a.ui-slider-handle').append('<p id="ht0" class="tooltip">70</p>');             
         }
       });
      
      this.$("#slider_gv").slider({
          range: "100",
          min: 0,
          max: 100,         
          value: 15, //TODO: load from model
          slide: function(event, ui) {
              // Hack to get red bar resizing
              self.gv  = ui.value;             
              self.slide_gv(self.gv);
          },
          stop: function(event, ui) {
         	 self.gv  = ui.value;             
              self.trigger('stop', self.low, self.high, self.shade, self.gv);              
          },
          create: function(event,ui) {
              self.$('#slider_gv a.ui-slider-handle').append('<p id="ht0" class="tooltip">15</p>');             
          }
        });
      
      this.$("#slider_soil").slider({
          range: "100",
          min: 0,
          max: 100,         
          value: 10, //TODO: load from model
          slide: function(event, ui) {
              // Hack to get red bar resizing
              self.soil  = ui.value;             
              self.slide_soil(self.soil);
          },
          stop: function(event, ui) {
         	 self.soil  = ui.value;             
              self.trigger('stop', self.low, self.high, self.shade, self.gv, self.soil); 
          },
          create: function(event,ui) {
              self.$('#slider_soil a.ui-slider-handle').append('<p id="ht0" class="tooltip">10</p>');             
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
         this.trigger('change', this.low, this.high, this.shade, this.gv, this.soil);
     }
 },
 
 slide_shade: function(shade, silent) {
	 this.shade = shade;
 
     this.$('#slider_shade p#ht0').text(this.shade);     
     if(silent !== true) {
         this.trigger('change', this.low, this.high, this.shade, this.gv, this.soil);
     }
 },
 
 slide_gv: function(gv, silent) {
	 this.gv = gv;
 
     this.$('#slider_gv p#ht0').text(this.gv);     
     if(silent !== true) {
         this.trigger('change', this.low, this.high, this.shade, this.gv, this.soil);
     }
 },
 
 slide_soil: function(soil, silent) {
	 this.soil = soil;

     this.$('#slider_soil p#ht0').text(this.soil);     
     if(silent !== true) {
         this.trigger('change', this.low, this.high, this.shade, this.gv, this.soil);
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


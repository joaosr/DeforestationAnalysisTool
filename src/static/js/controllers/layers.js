
var LayerView = Backbone.View.extend({

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
        this.id = 'layer_' + this.model.escape('id');
        el.html("<a href='#'>" + this.model.escape('description') + "</a>");
        el.attr('id', this.id);
        this.changed();
        if(this.model.get('type') !== 'google_maps') {
            el.addClass('sortable');
        }
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
            //this.trigger('enable', this);
        }
    }
});

var ReporView = LayerView.extend({
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

var SwitchLayerView = LayerView.extend({

    initialize: function() {
        _.bindAll(this, 'render', 'click', 'changed');
        this.model.bind('change', this.changed);
    },

    render: function() {
        var color_class = this.model.escape('description').replace(' ', '_').toLowerCase();
        this.constructor.__super__.render.call(this);
        $(this.el).addClass('switch');
        $(this.el).prepend('<span class="switch_button ' + color_class + '"></span>');
        this.changed();
        return this;
    },

    changed: function() {
        var enabled = this.model.enabled;
        if(!enabled) {
            $(this.el).removeClass('on');
        } else {
            $(this.el).addClass('on');
        }
    }
});

var GoogleMapsLayerView = LayerView.extend({
    click: function(e) {
        e.preventDefault();
        this.model.set_enabled(true);
    }
});

var LayerEditor = Backbone.View.extend({

    showing: false,

    template: _.template($('#layer-editor').html()),

    initialize: function() {
        _.bindAll(this, 'show', 'addLayer', 'addLayers', 'sortLayers', 'addLayer');
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
          stop: function(event,ui){
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
         var that = this;
         layers.raster_layers().each(function(m){
            if(m.get('visibility') && m.get('type') !== 'baseline'){
                that.addLayer(m);
            }
         });
    },
    
    show: function(pos, side) {
        /*if(side == 'center') {
            this.el.css({top: pos.top - 110, left: pos.left - this.el.width()});
            this.el.css({'background-image': "url('/static/img/bkg_layer_editor.png')"});
        } else {
        }*/
        this.el.css({top: pos.top - 6 , left: pos.left - this.el.width() + 28});
        this.el.show();//fadeIn();
        this.showing = true;
    },

    close: function() {
        this.el.hide();//fadeOut(0.1);
        this.showing = false;
    }

});

var EditorBaselineImagePicker = Backbone.View.extend({

    showing: false,

    template: _.template($('#editor-baseline-image-picker').html()),

    initialize: function() {
        _.bindAll(this, 'show', 'addTile', 'addTiles', 'sortLayers');
        var self = this;
        this.el = $(this.template());
        
        var picker_start = new Pikaday(
        	    {
        	        field: document.getElementById('#period_start'),
        	        firstDay: 1,
        	        minDate: new Date('2000-01-01'),
        	        maxDate: new Date('2020-12-31'),
        	        yearRange: [2000,2020]
        	    });
        
        var picker_end = new Pikaday(
        	    {
        	        field: document.getElementById('#period_end'),
        	        firstDay: 1,
        	        minDate: new Date('2000-01-01'),
        	        maxDate: new Date('2020-12-31'),
        	        yearRange: [2000,2020]
        	    });
        
        this.grid = this.options.grid;
        var cell_name = ":: Cell "+this.grid.model.get('z')+"/"+this.grid.model.get('x')+"/"+this.grid.model.get('y')+" ::";        
        this.el.find("#cell_name").html(cell_name);
        cell_name = this.grid.model.get('z')+"_"+this.grid.model.get('x')+"_"+this.grid.model.get('y');
        
        var request = $.ajax({
                              url: "baseline_search_tiles/",
                              type: 'POST',
                              data: {cell_name: cell_name},
                              dataType: 'json',
                              async: true,
                              success:function(d) {
                            	      console.log(d);
                            	      self.addTiles(d.tiles);
                            	      /*
            	                      that.$("#loading_range_picker").hide();
    	                              alert(d.result.message);
					                  console.log(d);
					                  that.data_request = d.result.data;
					                  that.trigger('send_success');
					                  console.log(that.data_request);
					                  */
					                  return d; 
                              },
                            }).responseText;
        
        this.options.parent.append(this.el);
        //this.el.find('#editor_baseline_image_picker').append("");
        /*
        this.item_view_map = {};
        this.layers = this.options.layers;
        this.el = $(this.template());
        
        this.options.parent.append(this.el);
        this.addTiles(this.layers);
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
        
        this.bind('change_layers', function(){self.addTiles(self.layers)});
        */        
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

    addTile: function(tile) {
        //if(!layer.hidden) {
            var ul = this.el.find('ul#cloud_cover');
            console.log(tile);        
            ul.html("<li><p>"+tile['name']+": <input type='text'></p></li>");
            //append(view.render().el);
            
        //}
    },    
    addTiles: function(tiles) {
    	if(tiles){
         this.el.find('ul#cloud_cover').html('');         
         var that = this;         
         
         for(var tile in tiles){
        	 this.addTile(tiles[tile]);
         }
        } 
         /*
         layers.raster_layers().each(function(m){
            if(m.get('visibility') || m.get('type') == 'baseline'){
                that.addTile(m);
            }
         });*/         
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


var LayerEditorBaseline = Backbone.View.extend({

    showing: false,

    template: _.template($('#baseline-layers').html()),

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
            if(m.get('visibility') || m.get('type') == 'baseline'){
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


var LayerEditorGoogleMaps = Backbone.View.extend({

    showing: false,

    template: _.template($('#layer-editor-base').html()),

    initialize: function() {
        _.bindAll(this, 'show', 'addLayer', 'addLayers', 'deselect_layers');
        var self = this;

        this.item_view_map = {};
        this.layers = this.options.layers;
        this.el = $(this.template());
        this.options.parent.append(this.el);
        this.addLayers(this.layers);
        this.layers.trigger('reset');
    },

    addLayer: function(layer) {
        if(!layer.hidden) {
            var ul = this.el.find('ul');
            layer.bind('change', this.deselect_layers);
            var view = new GoogleMapsLayerView({model: layer});
            ul.append(view.render().el);
            this.item_view_map[view.id] = view;
        }
    },

    deselect_layers: function(changed) {
        //console.log("CHANING" + changed.get('description'));
        if(changed.enabled) {
            this.layers.base_layers().each(function(layer) {
                if(layer.enabled && layer !== changed) {
                    //console.log("disabling " + layer.get('description'));
                    layer.set_enabled(false);
                }
            });
        }
    },

    addLayers: function(layers) {
         this.el.find('ul').html('');
         layers.base_layers().each(this.addLayer);
    },

    show: function(pos, side) {
        this.el.css({top: pos.top - 6 , left: pos.left - this.el.width() + 28});
        this.el.show();
        this.showing = true;
    },

    close: function() {
        this.el.hide();
        this.showing = false;
    }

});


function is_color(col1, col2) {
    return col1[0] == col2[0] &&
            col1[1] == col2[1] &&
            col1[2] == col2[2];
}

var TimeSeriesLayer = Backbone.View.extend({

    //DEFORESTATION_COLOR: [248, 8, 8],
    //DEGRADATION_COLOR: [247, 119, 87],
    DEFORESTATION_COLOR: [255, 255, 0],
    DEGRADATION_COLOR: [0, 255, 254],
    PREVIOUS_DEFORESTATION_COLOR: [0, 0, 255],
    PREVIOUS_DEGRADATION_COLOR: [0, 255, 255],
    FOREST_COLOR: [0, 153, 77],
    BASELINE_COLOR: [0, 0, 0],
    UNCLASSIFIED_COLOR: [255, 255, 255],
    NDFI_ENCODING_LIMIT: 201,

    initialize: function() {
        _.bindAll(this, 'canvas_setup', 'filter', 'apply_filter', 'map_auth', 'change_map_auth', 'click', 'class_visibility');
        var self = this;
        this.editing_state = false;
        this.mapview = this.options.mapview;
        this.report = this.options.report;        
        this.layer = new CanvasTileLayer(this.canvas_setup, this.filter);
 
        this.def_thresh = 165;
        this.deg_thresh = 175;
        this.shade_thresh = 70;
        this.gv_thresh = 15; 
        this.soil_thresh = 10;
        this.cloud_thresh = 7;
        this.showing = false;
        this.inner_poly_sensibility = 10;
        console.log("Report ID: "+this.report.id);        
        this.extra_images_list = {};
        this.extra_images_data = {};

        this.mapview.bind('click', this.click);
        
        
        

        this.sub_map_layer = [];
        this.add_class_control_layers();
        console.log(" === TimeSeries layer created === ");
    },

    add_class_control_layers: function() {
        var self = this;
        var classes = ['deforestation', 'degradation', 'forest'];
        _.each(classes, function(name) {
            var var_name = 'show_' + name;
            self[var_name] = 255;
        });
    },

    map_auth: function() {
        var self = this;
        this.map_layer = this.mapview.layers.set_canvas_in_custom_layer(this.layer); 
        
        var map_layer_timeseries = this.map_layer.time_series;

        for(var key  in this.map_layer){
            if(key !== "timeseries"){
                this.map_layer[key].set({"layer": new CanvasTileLayer(this.canvas_setup, this.filter)});
            }
        }
        
        this.token =  map_layer_timeseries.get('token');
        this.mapid = map_layer_timeseries.get('mapid');
        this.mapview.layers.trigger('reset');
    	
        console.log("Token: "+this.token+"Mapid: "+this.mapid);
        
        if(this.showing) {
            this.hide();
            this.show();
        }
    },

    change_map_auth: function(){
    	/*
        var map_layer = this.mapview.layers.get_by_name(this.map_layer.get('description'));

        if(map_layer){
          if(map_layer.get_enabled()){
            //this.ndfimap.set({sensor: 'modis'});
            this.token = this.ndfimap.get('token');
            this.mapid = this.ndfimap.get('mapid');
          }
        }

        map_layer = this.mapview.layers.get_by_name(this.map_layer_L5.get('description'));
        if(map_layer){
          if(map_layer.get_enabled()){
            //this.ndfimap.set({sensor: 'landsat5'});
            this.token = this.ndfimap_L5.get('token');
            this.mapid = this.ndfimap_L5.get('mapid');
           }
        }

        map_layer = this.mapview.layers.get_by_name(this.map_layer_L7.get('description'));

        if(map_layer){
          if(map_layer.get_enabled()){
            //this.ndfimap.set({sensor: 'landsat5'});
            this.token = this.ndfimap_L7.get('token');
            this.mapid = this.ndfimap_L7.get('mapid');
           }
        }*/
    },

    class_visibility: function(layer_id, enabled) {
        this['show_' + layer_id] = enabled?255:0;
        this.refrest();
    },

    refrest: function() {
        if(this.showing) {
            this.apply_filter(this.def_thresh, this.deg_thresh);
        }
    },

    click: function(e) {
        var self = this;
        if(!this.editing_state) {
            return;
        }
        window.loading_small.loading('ndfilayer: click');

        var c = this.layer.composed(this.mapview.el[0]);
        //var c =  this.layer_L5.composed(this.mapview.el[0]);
        var point = this.mapview.projector.transformCoordinates(e.latLng);

        // rendef offscreen
        var ctx = c.getContext('2d');
        var image_data = ctx.getImageData(0, 0, c.width, c.height);


        // get pixel color
        var pixel_pos = (Math.floor(point.y)*c.width + Math.floor(point.x)) * 4;
        var color = [];
        color[0] = image_data.data[pixel_pos + 0];
        color[1] = image_data.data[pixel_pos + 1];
        color[2] = image_data.data[pixel_pos + 2];
        color[3] = image_data.data[pixel_pos + 3];
        var def = is_color(color, this.DEFORESTATION_COLOR);
        var deg = is_color(color, this.DEGRADATION_COLOR);
        if(!deg && !def) {
            window.loading_small.finished('ndfilayer: click');
            return;
        }


        var poly = contour(image_data.data, c.width, c.height, Math.floor(point.x), Math.floor(point.y));

        var inners = inner_polygons(image_data.data,
                 c.width, c.height, poly, color);

        // discard small polys
        inners = _.select(inners, function(p){ return p.length > self.inner_poly_sensibility; });

        var newpoly = this.create_poly(poly, inners);
        window.loading_small.finished('ndfilayer: click');

        var type = Polygon.prototype.DEGRADATION;
        if(def) {
            type = Polygon.prototype.DEFORESTATION;
        }
        this.trigger('polygon', {paths: newpoly, type: type});

        delete image_data;
        delete c;
    },

    create_poly: function(points, inners) {
            var self = this;
            var paths = [];

            function simplify(points) {
                return GDouglasPeucker(points, 30);
            }
            // pixel -> latlon
            function unproject(p) {
                var ll = self.mapview.projector.untransformCoordinates(
                    new google.maps.Point(p[0], p[1])
                );
                return [ll.lat(), ll.lng()];
            }
            console.log("points before ", points.length);
            // outer path
            var simple = simplify(_.map(points, unproject));
            paths.push(simple);
            console.log("points after", simple.length);

            // inner paths (reversed)
            _.each(inners, function(p) {
                paths.push(simplify(_.map(p.reverse(), unproject)));
            });

            return paths;
            //inners && console.log(inners.length);

            /*
            var poly = new google.maps.Polygon({
                paths: paths,
                strokeWeight: 1
            })
            poly.setMap(App.map);
            return poly;
            */

    },

    show: function() {
        this.showing = true;
        if(this.token) {
            if(this.map_layer.collection) {
            }
            this.map_layer.set_enabled(true);
            //this.mapview.map.overlayMapTypes.insertAt(0, this.layer);
            console.log("showing NDFI");
        }
    },

    hide: function() {
        this.showing = false;
        this.map_layer.set_enabled(false);
        /*
        this.map_layer_L5.set_enabled(false);
        this.map_layer_L7.set_enabled(false);
        */
    },

    apply_filter: function(def_thresh, deg_thresh, shade_thresh, gv_thresh, soil_thresh, cloud_thresh) {
        this.def_thresh   = def_thresh;        
        this.deg_thresh   = deg_thresh;
        this.shade_thresh = shade_thresh;
        this.gv_thresh    = gv_thresh;
        this.soil_thresh  = soil_thresh;
        this.cloud_thresh = cloud_thresh;

        //this.layer.filter = this.filter //TODO mater somente em versão debugg        
        
        this.layer.filter_tiles_canvas(this.extra_images_list, this.def_thresh, this.deg_thresh, this.shade_thresh, this.gv_thresh, this.soil_thresh, this.cloud_thresh);
        
    },

    
     
    canvas_setup: function (canvas, coord, zoom) {
      var EARTH_ENGINE_TILE_SERVER = 'https://earthengine.googleapis.com/map/';
      var self = this;
      if (zoom < 12) {
        //return;
      }
      
      function load_finished() {
        window.loading_small.finished("canvas_setup:");
      }
      window.loading_small.loading("canvas_setup:");// " + image.src);
      // sometimes due to browser limitation to get images from the same domain
      // images are not loaded, so start a timeout to finished the loading
      setTimeout(load_finished, 20*1000);
      var image_timeseries = new Image();
      var extra_images = {}
      
      //check if thereis support for corssOrigin images and use proxy if isn't available
      var map_layer_timeseries = this.map_layer.time_series;
      
      if(image_timeseries.crossOrigin !== undefined) {
          image_timeseries.crossOrigin = '';
          image_timeseries.src = EARTH_ENGINE_TILE_SERVER + map_layer_timeseries.get('mapid') + "/"+ zoom + "/"+ coord.x + "/" + coord.y +"?token=" + map_layer_timeseries.get('token');          
      } else {
        image_timeseries.src = "/ee/tiles/" + map_layer_timeseries.get('mapid') + "/"+ zoom + "/"+ coord.x + "/" + coord.y +"?token=" + map_layer_timeseries.get('token');        
      }
      
      for(var key in this.map_layer){
    	  if(key !== "timeseries"){
	    	  extra_images[key] = new Image();
	    	  
	    	  if(extra_images[key].crossOrigin !== undefined) {
	    		  extra_images[key].crossOrigin = '';
	    		  extra_images[key].src = EARTH_ENGINE_TILE_SERVER + this.map_layer[key].get('mapid') + "/"+ zoom + "/"+ coord.x + "/" + coord.y +"?token=" + this.map_layer[key].get('token');          
	          } else {
	        	  extra_images[key].src = "/ee/tiles/" + this.map_layer[key].get('mapid') + "/"+ zoom + "/"+ coord.x + "/" + coord.y +"?token=" + this.map_layer[key].get('token');        
	          }  
    	  }
      }

      var ctx = canvas.getContext('2d');
      canvas.image = image_timeseries;
      canvas.coord = coord;
    
      image_timeseries.onload = function() {
          load_finished();
          //ctx.globalAlpha = 0.5;
          
          
          ctx.drawImage(this, 0, 0);
          canvas.image_data = ctx.getImageData(0, 0, canvas.width, canvas.height);         

          var canvas_name = coord.x + '_' + coord.y + '_' + zoom;

          self.extra_images_list[canvas_name] = extra_images;
                   
          self.layer.filter_tile_canvas(canvas, extra_images, [self.def_thresh, self.deg_thresh, self.shade_thresh, self.gv_thresh, self.soil_thresh, self.cloud_thresh]);
      };
      
      /*$(image).load(function() {
            load_finished();
            //ctx.globalAlpha = 0.5;
            ctx.drawImage(image, 0, 0);
            canvas.image_data = ctx.getImageData(0, 0, canvas.width, canvas.height);
            self.layer.filter_tile(canvas, [self.def_thresh, self.deg_thresh]);
      }).error(function() {
            console.log("server error loading image");
            load_finished();
      });*/
    },
    
    // filter image canvas based on thresholds
    // and color it
    filter: function(ndfi_data, mask_images, w, h, def_thresh, deg_thresh, shade_thresh, gv_thresh, soil_thresh, cloud_thresh) {    
        var temperature_thresh = 22;
//         shade_thresh = 65;
//         gv_thresh = 19;
//         soil_thresh = 5;
//         cloud_thresh = 5;
        
//         deg_thresh = 175;
//     	def_thresh = 165;
    	
//     	temperature_thresh = 22;
    	
        var components = 4; //rgba
        
        //console.log(mask_images.shade);        
        // yes, this variables are the same as declared on this view
        // this is because javascript looks like optimize if
        // variables are local and a constant
        var NDFI_ENCODING_LIMIT = this.NDFI_ENCODING_LIMIT;        
        
        var DEFORESTATION_COLOR     = [255, 255, 0];
        var OLD_DEFORESTATION_COLOR = [0, 0, 0];
        var DEGRADATION_COLOR       = [0, 255, 254]; //[255, 199, 44];        
        var FOREST_COLOR            = [0, 153, 77]; // [32, 224, 32];
        var CLOUD_COLOR             = [102, 102, 102];
        var WATER_COLOR             = [0, 0, 255];
        
        var UNCLASSIFIED = 203;
        var CLOUD = 202;
        var WATER = 255;        

        var show_deforestation = this.show_deforestation;
        var show_degradation = this.show_degradation;
        var show_forest = this.show_forest;        
        var show_deforested = 255;

        var pixel_pos;
        //console.log(mask_images.cloud);
        //console.log(mask_images.cloud_regions);
        
        // Converte os valores de grayscale para rgba (0-100 para 0-255)
        var shade_thresh_rgb = 255 * shade_thresh / 100
        var gv_thresh_rgb    = 255 * gv_thresh / 100
        var soil_thresh_rgb  = 255 * soil_thresh / 100

        for(var i=0; i < w; ++i) {
            for(var j=0; j < h; ++j) {
                pixel_pos = (j*w + i) * components;
                
                var p = ndfi_data[pixel_pos];
                
                var p_gv    = mask_images.gv[pixel_pos];
                var p_shd_md = mask_images.shade_median[pixel_pos];
                var p_soil  = mask_images.soil[pixel_pos];
                
                var p_cloud        = mask_images.cloud[pixel_pos];
                var p_cloud_region = mask_images.cloud_region[pixel_pos];
                var p_temperature  = mask_images.temperature[pixel_pos];
                
//                 var p_last_map_r   = mask_images.last_map[pixel_pos+0];
//                 var p_last_map_g   = mask_images.last_map[pixel_pos+1];
//                 var p_last_map_b   = mask_images.last_map[pixel_pos+2];
                
//                var p_last_map = mask_images.last_map[pixel_pos+0] + 
//                				 mask_images.last_map[pixel_pos+1] +
//                				 mask_images.last_map[pixel_pos+2];
                
                var a = ndfi_data[pixel_pos + 3];
                
               if(a > 0) {
                	/*
                     * Classification (forest, degradation and deforestation)
                     */
                	if (p == UNCLASSIFIED) {
                        
                		ndfi_data[pixel_pos + 0] = 255;
                        ndfi_data[pixel_pos + 1] = 255;
                        ndfi_data[pixel_pos + 2] = 255;
                        ndfi_data[pixel_pos + 3] = 255;
                        
                    } else if (p > 200) {//(p === 255) {
                    	
                        ndfi_data[pixel_pos + 0] = OLD_DEFORESTATION_COLOR[0];
                        ndfi_data[pixel_pos + 1] = OLD_DEFORESTATION_COLOR[1];
                        ndfi_data[pixel_pos + 2] = OLD_DEFORESTATION_COLOR[2];
                        ndfi_data[pixel_pos + 3] = 255;
                        
                    } else if (p >= 0 && p <= def_thresh) {
                    
                    	ndfi_data[pixel_pos + 0] = DEFORESTATION_COLOR[0];
                        ndfi_data[pixel_pos + 1] = DEFORESTATION_COLOR[1];
                        ndfi_data[pixel_pos + 2] = DEFORESTATION_COLOR[2];
                        ndfi_data[pixel_pos + 3] = show_deforestation;
                    
                    } else if (p > deg_thresh && p <= 200) {
                    	
                    	ndfi_data[pixel_pos + 0] = FOREST_COLOR[0];
                        ndfi_data[pixel_pos + 1] = FOREST_COLOR[1];
                        ndfi_data[pixel_pos + 2] = FOREST_COLOR[2];
                        ndfi_data[pixel_pos + 3] = show_forest;
                        
                    } else if (p > def_thresh && p <= deg_thresh){
                    	ndfi_data[pixel_pos + 0] = DEGRADATION_COLOR[0];
                        ndfi_data[pixel_pos + 1] = DEGRADATION_COLOR[1];
                        ndfi_data[pixel_pos + 2] = DEGRADATION_COLOR[2];
                        ndfi_data[pixel_pos + 3] = show_degradation;                        
                    }
                    /*
                     * Cloud Mask
                     */
                    if (p_cloud_region != 0 && p_cloud >= cloud_thresh && p != 255){// && p_temperature <= temperature_thresh) {
                        //console.log(p_temperature);
                        ndfi_data[pixel_pos + 0] = CLOUD_COLOR[0];
                        ndfi_data[pixel_pos + 1] = CLOUD_COLOR[1];
                        ndfi_data[pixel_pos + 2] = CLOUD_COLOR[2];
                        ndfi_data[pixel_pos + 3] = 255;
                    }
                    /*
                     * Water Mask
                     */
                    if (p_shd_md >= shade_thresh_rgb && p_gv <= gv_thresh_rgb && p_soil <= soil_thresh_rgb && p < 200) {
                        ndfi_data[pixel_pos + 0] = WATER_COLOR[0];
                        ndfi_data[pixel_pos + 1] = WATER_COLOR[1];
                        ndfi_data[pixel_pos + 2] = WATER_COLOR[2];
                        ndfi_data[pixel_pos + 3] = 255;
                    }
                    
                    
//                     if (p_last_map_r == 0 && p_last_map_g == 0 && p_last_map_b == 0) {
//                         ndfi_data[pixel_pos + 0] = OLD_DEFORESTATION_COLOR[0];
//                         ndfi_data[pixel_pos + 1] = OLD_DEFORESTATION_COLOR[1];
//                         ndfi_data[pixel_pos + 2] = OLD_DEFORESTATION_COLOR[2];
//                         ndfi_data[pixel_pos + 3] = 255;
//                     } else if (p_last_map_r == 255 && p_last_map_g == 255 && p_last_map_b == 0) {
//                         ndfi_data[pixel_pos + 0] = OLD_DEFORESTATION_COLOR[0];
//                         ndfi_data[pixel_pos + 1] = OLD_DEFORESTATION_COLOR[1];
//                         ndfi_data[pixel_pos + 2] = OLD_DEFORESTATION_COLOR[2];
//                         ndfi_data[pixel_pos + 3] = 255;
//                     }
               }
           }
        }
    }
});


var LayerModel = Backbone.Model.extend({

    hidden: false,
    _static: false,

    initialize: function() {
        _.bindAll(this, 'set_enabled');
        if(this.get('static') === true) {
            this._static = true;
            this.enabled = true;
        } else {
            this.enabled = false;
        }
        if(this.get('enabled') === true) {
            this.set_enabled(true);
        }
    },

    set_enabled: function(b) {
        if(!this._static) {
            this.enabled = b;
            this.set({'enabled': this.enabled});
            this.trigger('change', this);
        }
    },

    get_enabled: function() {
    	if(this.get('enabled') === true) {
           return true;
        }else{
        	return false;
        }
    }
});

// this layer needs to update the tile url when
// call is changed
var RGBStrechLayer = LayerModel.extend({

    initialize: function() {
        _.bindAll(this, 'set_enabled', 'on_cell');
        var desc = this.get('description') || 'RGB ' + this.get('r') + this.get('g') + this.get('b');
        this.set({
              id: 'RGB',
              type: 'custom',
              description: desc,
              layer: this.google_maps_layer()               
        });
        this.set_enabled(false);
    },

    on_cell: function(x, y, z) {
        this.set({x : x, y: y, z: z});
        this.fetch();
    },

    url: function() {
        var cell_id =  this.get('z') + "_" + this.get('x') + "_" + this.get('y');
        var mapid =  this.get('r') + "/" + this.get('g') + '/' + this.get('b');
        return "/api/v0/report/" + this.get('report_id') + "/operation/" + this.get('operation') + "/cell/" + cell_id + "/rgb/" + mapid + "/sensor/" + this.get('sensor');
    },

    //parses token and mapid response from server and creates tile url
    parse: function(data) {
        //var base_url = 'https://earthengine.sandbox.google.com/map/{mapid}/{Z}/{X}/{Y}?token={token}';
        var base_url = 'https://earthengine.googleapis.com/map/{mapid}/{Z}/{X}/{Y}?token={token}';
        var url = base_url.replace('{mapid}', data.mapid).replace('{token}', data.token);
        return {'url_pattern': url };
    },

    google_maps_layer: function() {
        var self = this;
        return new google.maps.ImageMapType({
            getTileUrl: function(tile, zoom) {
                var urlPattern = self.get('url_pattern');
                if( urlPattern === undefined) {
                    return null;
                }
                var y = tile.y;
                var tileRange = 1 << zoom;
                if (y < 0 || y  >= tileRange) {
                    return null;
                }
                var x = tile.x;
                if (x < 0 || x >= tileRange) {
                    x = (x % tileRange + tileRange) % tileRange;
                }
                return urlPattern.replace("{X}",x).replace("{Y}",y).replace("{Z}",zoom);
            },
            tileSize: new google.maps.Size(256, 256),
            opacity: 1.0,
            isPng: true
            });
    }


});

var LayerBaselineCollection = Backbone.Collection.extend({

    model: LayerModel,

    initialize: function()  {

    },
    parse: function(result){
        console.log(result.result);
        return result.result;
    },
    get_by_cell: function(cell_name) {
        var lay;
        this.each(function(m) {
        	var baseline_name = m.get('description')
        	var index_found = baseline_name.search(cell_name)
            if(index_found > -1) {
                lay = m;
            }
        });
        return lay;
    },
    get_by_name: function(name) {
        var lay;
        this.each(function(m) {
            if(m.get('description') === name) {
                lay = m;
            }
        });
        return lay;
    },
 // return a new collection
    filter_by_type: function(callback) {
        return _(this.filter(function(layer) {
                return callback(layer.get('type'));
               }));
    },
    base_layers: function() {
        return this.filter_by_type(function(t) { return t === 'google_maps'; });
    },

    raster_layers: function() {
        return this.filter_by_type(function(t) { return t !== 'google_maps'; });
    }

});

var LayerCollection = Backbone.Collection.extend({

        model: LayerModel,

        initialize: function()  {

        },
        parse: function(result){
            console.log(result.result);
            return result.result;
        },
        update_time_range: function(start, end){
            this.each(function(m){
                if(m.get('type') === 'xyz'){
                  m.set('date_start', start);
                  m.set('date_end', end);
                }
            });
        },
        update_maps_id: function(){
            this.each(function(m){
                if(m.get('type') === 'xyz'){
                    m.url = ""
                    m.fetch({
                        success: function(){

                        }
                    });
                }
            });
        },
        update_visibility_with_type: function(visibility, type){
             this.each(function(m){
                if(m.get('type') == type && m.get('visibility') != visibility){
                    m.set('visibility', visibility);
                }
             });
        },
        get_by_name: function(name) {
            var lay;
            this.each(function(m) {
                if(m.get('description') === name) {
                    lay = m;
                }
            });
            return lay;
        },
        // return a new collection
        filter_by_type: function(callback) {
            return _(this.filter(function(layer) {
                    return callback(layer.get('type'));
                   }));
        },
        base_layers: function() {
            return this.filter_by_type(function(t) { return t === 'google_maps'; });
        },

        raster_layers: function() {
            return this.filter_by_type(function(t) { return t !== 'google_maps'; });
        }

});

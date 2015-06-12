
var SPLITS = 5;

var Cell = Backbone.Model.extend({
    /*initialize: function() {
        _.bindAll(this, 'bbox');
    },*/

    defaults: {
        //TODO: remove this values from model
        x:0,
        y:0,
        z:0,
        background: "rgba(0, 0, 0, 0.5)"
    },

    parent_cell: function() {
        return new Cell({
            report_id: this.get('report_id'),
            z: this.get('z') - 1,
            x: Math.floor(this.get('x')/SPLITS),
            y: Math.floor(this.get('y')/SPLITS)
        });
    },

    has_changes: function() {
         return this.get('latest_change') > 0 && this.get('added_by') != 'Nobody';
         //return this.get('polygon_count') > 0;
    },

    ndfi_change: function() {
        var t = this.get('ndfi_change_value');
        t = Math.min(1.0, t);
        return t;
    },

    bbox: function(mapview){
    	var p = window.mapper.cell_position(this.get('x'), this.get('y'), this.get('z'));
        // normalize
        var x = Math.floor(p.x);
        var y = Math.floor(p.y);
        var w = Math.floor((p.width/5))*5;
        var h = Math.floor((p.height/5))*5;
        
        var prj = mapview.projector;

        bounds = new google.maps.LatLngBounds(
            prj.untransformCoordinates(new google.maps.Point(x, y + h)),
            prj.untransformCoordinates(new google.maps.Point(x + w, y))
        );
        
        var sw = bounds.getSouthWest();
        var ne = bounds.getNorthEast();

        return sw.lng()+','+sw.lat()+';'+sw.lng()+','+ne.lat()+';'+ne.lng()+','+ne.lat()+';'+ne.lng()+','+sw.lat() +';'+sw.lng()+','+sw.lat();
        
    },

    url: function() {
        return "/api/v0/report/" + this.get('report_id') + "/operation/" + this.get('operation') + "/cell/" + this.get('z') + "_" + this.get('x') + "_" + this.get('y');
    },

    // ok, sorry, i'm not going to use backbone sync stuff
    // only get this information when its needed
    landstat_info: function(callback) {
        var self = this;
        if(self._landstat_info === undefined) {
            var url = this.url() + "/landsat";
            $.get(url, function(data) {
                self._landstat_info = data;
                self.trigger('landsat_info', self._landsat_info);
                if(callback) {
                    callback(data);
                }
            });
        } else {
            self.trigger('landsat_info', self._landsat_info);
            if(callback) {
                callback(self._landstat_info);
            }
        }
    }

});


var Cells = Backbone.Collection.extend({

    model: Cell,

    initialize: function(models, options) {
        this.x = options.x;
        this.y = options.y;
        this.z = options.z;
        this.operation = options.operation;
        this.report = options.report;
    },

    // this function is a helper to calculate subcells at this level
    populate_cells: function() {
        this.fetch();
    },

    url: function() {
        return "/api/v0/report/" + this.report.id + "/operation/"+this.operation + "/cell/" + this.z + "_" + this.x + "_" + this.y +"/children";
    }

});

var Tile = Backbone.Model.extend();

var Tiles = Backbone.Collection.extend({
    model: Tile,
    initialize: function(models, options){
//        this.sensor = options.sensor;
        this.url = 'tiles_sensor/'+options.sensor+'/'
    },
//    url: 'tiles/'+this.sensor+'/',
    parse: function(result){
        console.log(result.result);
        return result.result;
    }

});


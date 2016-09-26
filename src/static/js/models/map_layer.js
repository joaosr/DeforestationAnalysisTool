
// return NDFI map :
// new NDFIMap({report_id: 'blahmehgas'})

/*
var NDFIMap = Backbone.Model.extend({

    url: function() {
        console.log(this.get('report_id'));
        return '/api/v0/report/' + this.get('report_id') + "/map";
    }

});

*/

var NDFIMap = Backbone.Model.extend({

    url: function() {
        return '/api/v0/report/' + this.get('report_id') + '/' + this.get('sensor') + '/map';
    }

});




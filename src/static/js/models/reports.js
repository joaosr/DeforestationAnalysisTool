
var ReportsModel = Backbone.Model.extend({

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

var ReportsCollection = Backbone.Collection.extend({

        model: ReportsModel,

        initialize: function()  {

        },
        parse: function(result){
            return result.data;
        },        
        get_by_name: function(name) {
            var lay;
            this.each(function(m) {
                if(m.get('assetid') === name) {
                    lay = m;
                }
            });
            return lay;
        },
        get_report_enabled: function(){
        	var lay;
        	this.each(function(m) {
                if(m.get_enabled()) {
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

});

var TileView = Backbone.View.extend({
    tagName: "option",
    initialize: function(){
        _.bindAll(this, 'render');
    },
    render: function(){
        $(this.el).attr('value', this.model.get('value')).html(this.model.get('name'));
        return this;
    }
});

var TilesView = Backbone.View.extend({
    //el: $("#tile"),
    events: {
    "change": "changeSelected"
    },
    initialize: function(){
        _.bindAll(this, 'addOne', 'addAll', 'render');
        this.collection = new Tiles([], {sensor: this.options.sensor});
        this.collection.bind('reset', this.addAll());
        this.callerView = this.options.callerView;
        this.tileId = -1;
        var that = this;
        this.collection.fetch({
            success: function(){
                that.render();
            }
        });
    },
    changeSelected: function(){
        this.tileId = $(this.el).val();
        this.callerView.callback();
    },
    addOne: function(tile){
        $(this.el).append(new TileView({model: tile}).render().el);
    },
    addAll: function(){
        this.collection.each(this.addOne);
    },
    render: function (){
        this.addAll();
        return this;
    }
});


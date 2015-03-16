
var Thumb = Backbone.Model.extend();

var Thumbs = Backbone.Collection.extend({
    model: Thumb,
    parse: function(result){
        console.log(result.result);
        return result.result;
    }
});

var ThumbView = Backbone.View.extend({
    tagName: "option",
    initialize: function(){
        _.bindAll(this, 'render');
    },
    render: function(){
        console.log(this.model.get('thumb'));
        $(this.el).attr('data-img-label', this.model.get('date')).html();
        $(this.el).attr('data-img-src', 'https://earthengine.googleapis.com/api/thumb?thumbid='+this.model.get('thumb')+'&token='+this.model.get('token')).html(this.model.get("date"));
        $(this.el).attr('value', this.model.get('date')).html();
        return this;
    }
});

var ThumbsView = Backbone.View.extend({
    el: $("#thumb"),
    initialize: function(){
        _.bindAll(this, 'addOne', 'addAll', 'render');
        console.log("Aqui");
        this.collection = new Thumbs();
        this.collection.bind('reset', this.addAll());
        this.tilesView = new TilesView({el: this.options.tile_el, sensor: 'modis', callerView: this});
    },
    callback: function(){
       $(this.el).empty();
       $(this.el).attr('disabled', false);
       this.collection.url = "picker/"+this.tilesView.tileId;
       var that = this;
       window.loading_small.loading('loading image picker');
       this.collection.fetch({
           success: function(){
               that.render();
               $(that.el).imagepicker({show_label: true});
               console.log(that.collection);
               window.loading_small.finished('loading image picker');
           }
       });
    },
    //TODO 13/02/15 mudança na implementação do fluxo de uso do sistema, esse método pode não ser mais necessário
    change_sensor: function(sensor){
        this.tilesView.setSensor(sensor);
    },
    addOne: function(thumb){
        console.log('mais aqui');
        var thumbView = new ThumbView({model: thumb});
        $(this.el).append(thumbView.render().el);
    },
    addAll: function(){
        console.log('Agora aqui');
        this.collection.each(this.addOne);
    },
    render: function(){
        this.addAll();
    }
});

var TilesViewExtend = TilesView.extend({
   setSelectedId: function(tileId){
       $(this.thumbsView.el).empty();
       $(this.thumbsView.el).attr('disabled', false);
       this.thumbsView.collection.url = "picker/"+tileId+"/";
       var that = this;
       this.thumbsView.collection.fetch({
           success: function(){
               that.thumbsView.render();
               $(that.thumbsView.el).imagepicker({show_label: true});
               console.log(that.thumbsView.collection);
           }
       });
       //this.thumbsView.render();
       //$(this.thumbsView.el).imagepicker({show_label: true});

    }
});


//var tilesViewExtend = new TilesViewExtend();


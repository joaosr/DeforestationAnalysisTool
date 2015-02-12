

var Parameter = Backbone.Model.extend();

var Parameters = Backbone.Collection.extend({
    model: Parameter,
    parse: function(result){
        console.log(result.result);
        return result.result;
    }

});

var OptionParameter = Backbone.View.extend({
    tagName: "option",
    initialize: function(){
        _.bindAll(this, "render");
        this.value = this.options.value;
    },
    render: function(){
        $(this.el).attr("value", this.value).html(this.value);
        return this;
    }
});

var SelectParameters = Backbone.View.extend({
    initialize: function(){
        _.bindAll(this, "addOne", "addAll", "render");
        this.collection.bind('reset', this.addAll());
        this.tilesView = new TilesView({el: $("#scalling_form #tile"), sensor: 'modis', callerView: this});
/*        var that = this;
        this.collection.fetch({
            success: function(){
                that.render();
            }
        });*/
    },
    callback: function(){
        //$(this.el).empty();
        $("tr#band3  td select#sill3").empty();
        $("tr#band3  td select#range3").empty();
        $("tr#band3  td select#nugget3").empty();

        $("tr#band4  td select#sill4").empty();
        $("tr#band4  td select#range4").empty();
        $("tr#band4  td select#nugget4").empty();

        $("tr#band6  td select#sill6").empty();
        $("tr#band6  td select#range6").empty();
        $("tr#band6  td select#nugget6").empty();

        $("tr#band7  td select#sill7").empty();
        $("tr#band7  td select#range7").empty();
        $("tr#band7  td select#nugget7").empty();



        $(this.el).attr('disabled', false);
        this.collection.url = "downscalling/"+this.tilesView.tileId;
        var that = this;
        this.collection.fetch({
           success: function(){
               that.render();
               console.log(that.collection);
           }
       });

    },
    addOne: function(parameter){
        var band = parameter.get('Band');
        if(band == 3){
          $("tr#band3  td select#sill3").append(new OptionParameter({value: parameter.get('Sill')}).render().el);
          $("tr#band3  td select#range3").append(new OptionParameter({value: parameter.get('Range')}).render().el);
          $("tr#band3  td select#nugget3").append(new OptionParameter({value: parameter.get('Nugget')}).render().el);
        }
        else if(band == '4'){
          $("tr#band4  td select#sill4").append(new OptionParameter({value: parameter.get('Sill')}).render().el);
          $("tr#band4  td select#range4").append(new OptionParameter({value: parameter.get('Range')}).render().el);
          $("tr#band4  td select#nugget4").append(new OptionParameter({value: parameter.get('Nugget')}).render().el);
        }
        else if(band == '6'){
          $("tr#band6  td select#sill6").append(new OptionParameter({value: parameter.get('Sill')}).render().el);
          $("tr#band6  td select#range6").append(new OptionParameter({value: parameter.get('Range')}).render().el);
          $("tr#band6  td select#nugget6").append(new OptionParameter({value: parameter.get('Nugget')}).render().el);
        }
        else if(band == '7'){
          $("tr#band7  td select#sill7").append(new OptionParameter({value: parameter.get('Sill')}).render().el);
          $("tr#band7  td select#range7").append(new OptionParameter({value: parameter.get('Range')}).render().el);
          $("tr#band7  td select#nugget7").append(new OptionParameter({value: parameter.get('Nugget')}).render().el);
        }


    },

    addAll: function(){
        this.collection.each(this.addOne);
        console.log(this.collection);
    },
    render: function () {
        this.addAll();
    }

});



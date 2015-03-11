
var Toolbar = Backbone.View.extend({

    show: function() {
        this.el.show();
    },

    hide: function() {
        this.el.hide();
    }
});

var PressedButton = Backbone.View.extend({

    events: {
        "click": 'press'
    },

    initialize: function() {
        _.bindAll(this, 'press');
        this.pressed = false;
    },

    press: function(e) {
        if(this.pressed) {
            this.el.removeClass('selected');
        } else {
            this.el.addClass('selected');
        }
        this.pressed = !this.pressed;
        this.trigger('change', this, this.pressed);
        e.preventDefault();
    }

});

// jqueryui slider wrapper
// triggers change with values
var RangeSlider = Backbone.View.extend({
    initialize: function() {
        _.bind(this, 'slide', 'set_values');
        var self = this;
        this.el.slider({
                range: true,
                min: 0,
                max: 200,
                values: [40, 60], //TODO: load from model
                slide: function(event, ui) {
                    // Hack to get red bar resizing

                    var low = ui.values[0];
                    var high= ui.values[1];
                    self.slide(low, high);
                },
                stop: function(event, ui) {
                    var low = ui.values[0];
                    var high= ui.values[1];
                    self.trigger('stop', low, high);
                },
                create: function(event,ui) {
                    // Hack to get red bar resizing
                    var size = $('a.ui-slider-handle:eq(1)').css('left');
                    $('span.hack_red').css('left',size);
                    // Hack for handles tooltip
                    var size0 = $('a.ui-slider-handle:eq(0)').css('left');

                    $('a.ui-slider-handle:eq(0)').append('<p id="ht0" class="tooltip">40</p>');
                    $('a.ui-slider-handle:eq(1)').append('<p id="ht1" class="tooltip">60</p>');
                }
         });
    },

    slide: function(low, high, silent) {
        var size = $('a.ui-slider-handle:eq(1)').css('left');
        $('span.hack_red').css('left',size);
        // Hack for handles tooltip
        var size0 = $('a.ui-slider-handle:eq(0)').css('left');
        $('p#ht0').text(low);
        $('p#ht1').text(high);
        if(silent !== true) {
            this.trigger('change', low, high);
        }
    },

    // set_values([0, 1.0],[0, 1.0])
    set_values: function(low, high) {
        low = Math.floor(low*200);
        high =  Math.floor(high*200);

        this.el.slider( "values" , 0, low);
        this.el.slider( "values" , 1, high);
        //launch an event
        this.slide(low, high, false);//true);
    }
});

var ReportToolbar = Toolbar.extend({
    //el: $("#range_select"),
    events: {
        'click #submit_date_picker': 'send_date_report'
    },
    initialize: function() {
       _.bindAll(this, 'update_range_date', 'render');
       this.report     = this.options.report;
       this.callerView = this.options.callerView;
       //this.$("#report-date").html(this.report.escape('str'));
       //this.$("#report-date-end").html(this.report.escape('str_end'));
       var start = this.report.escape('str');
       this.start_date = moment(new Date(start)).format("DD/MMM/YYYY");
       var end = this.report.escape('str_end');
       this.end_date = moment(new Date(end)).format("DD/MMM/YYYY");

       this.$("#range_picker").attr("value", this.start_date+' to '+this.end_date).html();
       this.visibility_picker_range = false;

       this.$("#range_picker").dateRangePicker({
            format: 'DD/MMM/YYYY',
            separator: ' to ',
            showShortcuts: false}).bind('datepicker-change', this.update_range_date);
    },
    send_date_report: function(){
        var date_picker = this.$("#range_picker").val();
        console.log(date_picker);
        var message = $.ajax({
                              url: "/range_report/",
                              type: 'POST',
                              data: {range_picker: date_picker},
                              dataType: 'json',
                              async: false,
                            }).responseText;

        var s = jQuery.parseJSON(message);
        alert(s.result);
        console.log(s);
    },
    update_range_date: function(evt, obj){
        var dates = obj.value.split(' to ');
        console.log(dates[0]+' - '+dates[1]);
        this.start_date = dates[0];
        this.end_date = dates[1];
    },
    render: function(){
        return this;
    }
});

var ImagePicker = Toolbar.extend({
    //el: $("#image_picker"),
    events: {
        'click #picker_select' : 'visibility_change',
        'click #submit': 'send_images'
    },
    initialize: function(){
        _.bindAll(this, 'visibility_change');
        this.thumbsView = new ThumbsView();
        this.callerView = this.options.callerView;
        this.visibility = false;
    },
    change_sensor: function(sensor){
        this.thumbsView.change_sensor(sensor);
    },
    send_images: function(){
        var thumb = this.$("#thumb").val();
        var tile = this.$("#tile").val();
        console.log(thumb);
        var message = $.ajax({
                              url: "/picker/",
                              type: 'POST',
                              data: {thumb: thumb, tile: tile},
                              dataType: 'json',
                              async: false,
                            }).responseText;

        var s = jQuery.parseJSON(message);
        alert(s.result);
        console.log(s);
    },
    visibility_change: function(e){

        if(this.visibility){
          this.$("#picker_form").hide();
          //$(this.el).css("background", "");
          this.visibility = false;
        }else{
          //$(this.el).css("background", 'url("static/img/bkg_image_picker_over.png") no-repeat -1px 0');
          this.$("#picker_form").show();
          this.visibility = true;
          this.callerView.callback(this);
        }
    }
});

var DownScalling = Toolbar.extend({
    el: $("#downscalling"),
    events: {
        'click #scalling_select': 'visibility_change'
    },
    initialize: function(){
        _.bindAll(this, 'visibility_change', 'hide_form');
        var parameters = new Parameters();
        this.callerView = this.options.callerView;
        this.downScalling = new SelectParameters({collection: parameters});
        this.visibility = false;
    },
    hide_form: function(){
        $("#scalling_form").hide();
        //$(this.el).css("background", "");
        this.visibility = false;
    },
    visibility_change: function(e){
        if(this.visibility){
            this.hide_form();
        }
        else{
          $("#scalling_form").show();
          //$(this.el).css("background", 'url("static/img/bkg_downscalling_over.png") no-repeat 4px 0');
          this.visibility = true;
          this.callerView.callback(this);
        }
        e.preventDefault();
    }

});

var MonthlySAD = Toolbar.extend({
    el: $("#monthly_sad"),
    events: {
        'click #monthly_sad_select': 'visibility_change'
    },
    initialize: function(){
        _.bindAll(this, 'visibility_change', 'callback', 'hide_report_tool_bar', 'show_report_tool_bar', 'hide_image_picker', 'show_image_picker', 'hide_down_scalling', 'show_down_scalling');
        this.callerView = this.options.callerView;
        this.report = this.options.report
        console.log("==== setting_report_data ====");

        this.setting_report_data();
        this.report_tool_bar = new ReportToolbar({el: this.$("#range_select"), report: this.report, callerView: this});
        this.image_picker = new ImagePicker({el: this.$("#image_picker"), callerView: this});
        this.down_scalling = new DownScalling({callerView: this});
        this.visibility = false;
    },
    setting_report_data: function(){
        var date    = new Date();
        var start    = this.report.escape('str');
        var date_sad = new Date(start);

        var current_month     = date.getMonth();
        var current_month_sad = date_sad.getMonth();

        var current_year     = date.getYear();
        var current_year_sad = date_sad.getYear();

        var month_diference = current_month - current_month_sad;
        var year_diference  = current_year  - current_year_sad;

        if(month_diference == 2 && year_diference == 0){
            var new_start = moment(new Date(current_year, current_month_sad + 1, 1)).format("DD-MM-YYYY");
            var new_end   = moment(new Date(current_year, current_month_sad + 1, 0)).format("DD-MM-YYYY");
            console.log("Nem start: "+new_start);
            this.report.set('str', new_start);
            this.report.set('str_end', new_end);
        }
        else if(month_diference == -10 && year_diference == 1){
            var new_start = moment(new Date(current_year_sad, current_month_sad + 1, 1)).format("DD-MM-YYYY");
            var new_end   = moment(new Date(current_year_sad, current_month_sad + 1, 0)).format("DD-MM-YYYY");
            console.log("Nem start: "+new_start);
            this.report.set('str', new_start);
            this.report.set('str_end', new_end);
        }

    },
    callback: function(view){
        if(view === this.report_tool_bar && this.report_tool_bar.visibility){
            this.hide_image_picker();
            this.hide_down_scalling();
        }
        else if(view === this.image_picker && this.image_picker.visibility){
            this.hide_report_tool_bar();
            this.hide_down_scalling();
        }
        else if(view === this.down_scalling && this.down_scalling.visibility){
            this.hide_report_tool_bar();
            this.hide_image_picker();
        }
    },
    hide_report_tool_bar: function(){
        if(this.report_tool_bar.visibility){
          this.report_tool_bar.visibility_change();
        }
    },
    show_report_tool_bar: function(){
        if(!this.report_tool_bar.visibility){
          this.report_tool_bar.visibility_change();
        }
    },
    hide_image_picker: function(){
        if(this.image_picker.visibility){
          this.image_picker.visibility_change();
        }
    },
    show_image_picker: function(){
        if(!this.image_picker.visibility){
          this.image_picker.visibility_change();
        }
    },
    hide_down_scalling: function(){
        if(this.down_scalling.visibility){
          this.down_scalling.visibility_change();
        }
    },
    show_down_scalling: function(){
        if(!this.down_scalling.visibility){
          this.down_scalling.visibility_change();
        }
    },
    visibility_change: function(){
        if(this.visibility){
            $(this.el).css("background-color", "rgba(0, 0, 0, 0)")
            this.$("#monthly_sad_select h3").css("color", "#999999");
            this.$("#monthly_sad_content").hide();
            this.visibility = false;
        }
        else{
          $(this.el).css("background-color", "rgba(0, 0, 0, 1)");
          this.$("#monthly_sad_select h3").css("color", "white");
          this.$("#monthly_sad_content").show();
          this.visibility = true;
          this.callerView.callback(this);
        }
    }

});

var Baseline = Toolbar.extend({
    el: $("#baseline"),
    events:{
        'click #baseline_select': 'visibility_change'
    },
    initialize: function(){
        _.bindAll(this, 'callback', 'hide_report_tool_bar', 'show_report_tool_bar', 'hide_image_picker', 'show_image_picker', 'visibility_change');
        this.callerView = this.options.callerView;
        this.report = this.options.report
//        this.setting_report_data();
        this.report_tool_bar = new ReportToolbar({el: this.$("#range_select"), report: this.report, callerView: this});
        this.image_picker = new ImagePicker({el: this.$("#image_picker"), callerView: this});
        this.visibility = false;
    },
    setting_report_data: function(){
        var date    = new Date();
        var current_month     = date.getMonth();
        var current_year     = date.getYear();

        var new_start = moment(new Date(current_year, current_month_sad + 1, 1)).format("DD-MM-YYYY");
        var new_end   = moment(new Date(current_year, current_month_sad + 1, 0)).format("DD-MM-YYYY");
        console.log("Nem start: "+new_start);
        this.report.set('str', new_start);
        this.report.set('str_end', new_end);

    },
   callback: function(view){
        if(view === this.report_tool_bar && this.report_tool_bar.visibility){
            this.hide_image_picker();
        }
        else if(view === this.image_picker && this.image_picker.visibility){
            this.hide_report_tool_bar();
        }
    },
    hide_report_tool_bar: function(){
        if(this.report_tool_bar.visibility){
          this.report_tool_bar.visibility_change();
        }
    },
    show_report_tool_bar: function(){
        if(!this.report_tool_bar.visibility){
          this.report_tool_bar.visibility_change();
        }
    },
    hide_image_picker: function(){
        if(this.image_picker.visibility){
          this.image_picker.visibility_change();
        }
    },
    show_image_picker: function(){
        if(!this.image_picker.visibility){
          this.image_picker.visibility_change();
        }
    },
    visibility_change: function(){
        if(this.visibility){
            $(this.el).css("background-color", "rgba(0, 0, 0, 0)");
            this.$("#baseline_select h3").css("color", "#999999");
            this.$("#baseline_content").hide();
            this.visibility = false;
        }
        else{
            $(this.el).css("background-color", "rgba(0, 0, 0, 1)");
            this.$("#baseline_select h3").css("color", "white");
            this.$("#baseline_content").show();
            this.visibility = true;
            this.callerView.callback(this);
        }

    }
});

var TimeSeries = Toolbar.extend({
    el: $("#time_series"),
     events:{
        'click #time_series_select': 'visibility_change'
    },
    initialize: function(){
        _.bindAll(this, 'visibility_change');
        this.callerView = this.options.callerView;
        this.visibility = false;
    },
    visibility_change: function(){
        if(this.visibility){
            $(this.el).css("background-color", "rgba(0, 0, 0, 0)");
            this.$("#time_series_select h3").css("color", "#999999");
            this.visibility = false;
        }
        else{
             $(this.el).css("background-color", "rgba(0, 0, 0, 1)");
            this.$("#time_series_select h3").css("color", "white");
            this.visibility = true;
            this.callerView.callback(this);
        }
    }

});

var MainOperations = Backbone.View.extend({
    initialize: function(){
        _.bindAll(this, 'hide_monthly_sad', 'show_monthly_sad', 'hide_baseline', 'show_baseline', 'hide_time_series', 'show_time_series', 'hide_all', 'show_all','callback');
        this.monthly_sad = new MonthlySAD({report: this.options.report, callerView: this});
        this.baseline    = new Baseline({report: this.options.report, callerView: this});
        this.time_series = new TimeSeries({callerView: this});

    },
    callback: function(view){
        if(view === this.monthly_sad && this.monthly_sad.visibility){
            this.hide_baseline();
            this.hide_time_series();
        }
        else if(view === this.baseline && this.baseline.visibility){
            this.hide_monthly_sad();
            this.hide_time_series();
        }
        else if(view === this.time_series && this.time_series.visibility){
            this.hide_monthly_sad();
            this.hide_baseline();
        }
    },
    hide_monthly_sad: function(){
        if(this.monthly_sad.visibility){
          this.monthly_sad.visibility_change();
        }
    },
    show_monthly_sad: function(){
        if(!this.monthly_sad.visibility){
          this.monthly_sad.visibility_change();
        }
    },
    hide_baseline: function(){
        if(this.baseline.visibility){
          this.baseline.visibility_change();
        }
    },
    show_baseline: function(){
        if(!this.baseline.visibility){
          this.baseline.visibility_change();
        }
    },
    hide_time_series: function(){
        if(this.time_series.visibility){
          this.time_series.visibility_change();
        }
    },
    show_time_series: function(){
        if(!this.time_series.visibility){
          this.time_series.visibility_change();
        }
    },

    hide_all: function(){
        this.monthly_sad.hide();
        this.baseline.hide();
        this.time_series.hide();
    },
    show_all: function(){
        this.monthly_sad.show();
        this.baseline.show();
        this.time_series.show();
    }
});

var ButtonGroup = Backbone.View.extend({

    initialize: function() {
        _.bindAll(this, 'show', 'hide', 'select','unselect_all');
        var self = this;
        this.buttons = this.$('.button').click(function(e) { self.click($(this), e); });
    },

    click: function(button, event) {
        this.buttons.removeClass('selected');
        button.addClass('selected');
        event.preventDefault();
        this.trigger('state', button.attr('id'));
        this.trigger('state:' + button.attr('id'));
    },

    select: function(opt) {
        var button = this.$("#" + opt);
        this.buttons.removeClass('selected');
        button.addClass('selected');
        this.trigger('state', button.attr('id'));
        this.trigger('state:' + button.attr('id'));
    },

    show: function() {
        this.el.show();
    },

    hide: function() {
        this.el.hide();
    },

    unselect_all: function() {
        this.buttons.removeClass('selected');
    }
});

var PolygonToolbar = Toolbar.extend({

    el: $("#work_toolbar"),

    events: {
        'click #compare': 'none',
        'click #ndfirange': 'none',
        'click .class_selector': 'visibility_change'
    },

    initialize: function() {
        _.bindAll(this, 'change_state', 'reset', 'visibility_change');
        this.buttons = new ButtonGroup({el: this.$('#selection')});
        this.polytype = new ButtonGroup({el: this.$('#polytype')});
        this.ndfi_range = new RangeSlider({el: this.$("#ndfi_slider")});
        this.compare = new ButtonGroup({el: this.$("#compare_buttons")});
        this.polytype.hide();
        this.buttons.bind('state', this.change_state);
    },

    visibility_change: function(e) {
        var el = $(e.target);
        var what = $(e.target).attr('id');
        var selected = false;
        if(el.hasClass('check_selected')) {
            el.removeClass('check_selected');
        } else {
            el.addClass('check_selected');
            selected = true;
        }
        this.trigger('visibility_change', what, selected);
        e.preventDefault();
    },

    none: function(e) { e.preventDefault();},

    change_state: function(st) {
        this.trigger('state', st);
    },

    reset: function() {
        this.polytype.unselect_all();
        this.buttons.unselect_all();
    }

});

var Overview = Backbone.View.extend({

    el: $("#overview"),

    finished: false,

    events: {
        'click #done': 'done',
        'click #go_back': 'go_back',
        'click .notes': 'open_notes',
        'click #report_done': 'confirm_generation',
        'click #cancel': 'cancel_report',
        'click #confirm': 'close_report',
        'click #cancel_done': 'cancel_done',
        'click #confirm_done': 'cell_done',
        'click #go_setting': 'open_settings'
    },

    initialize: function() {
        _.bindAll(this, 'done', 'on_cell', 'select_mode', 'go_back', 'set_note_count', 'report_changed', 'cancel_report', 'change_user_cells', 'close_report', 'cancel_done', 'cell_done', 'open_settings');
        this.report = this.options.report;
        this.analysed= this.$('#cell_analisys');
        this.$("#analysed_global_final").hide();
        this.$("#confirmation_dialog").hide();
        this.$("#done_confirmation_dialog").hide();
        this.$("#analysed_global_progress").hide();
        this.report.bind('change', this.report_changed);
        this.report_changed();
        this.el.fadeIn();
    },


    set_note_count: function(c) {
        this.$('.notes').html( c + " NOTE" + (c==1?'':'S'));
    },

    done: function(e) {
        e.preventDefault();
        this.$("#done_confirmation_dialog").fadeIn();
        //this.trigger('done');
    },

    open_notes: function(e) {
        e.preventDefault();
        this.trigger('open_notes');
    },

    open_settings: function(e) {
        e.preventDefault();
        this.trigger('open_settings');
    },

    go_back: function(e) {
        e.preventDefault();
        this.trigger('go_back');
    },

    on_cell: function(x, y, z) {
        if(z == 2) {
            this.analysed.show();
            this.$('.notes').show();
        } else {
            this.$('.notes').hide();
        }
        var text = "Global map";
        if(z > 0) {
            text = "Cell " + z + "/" + x + "/" + y + " - ";
            this.$("#go_back").show();
            this.$("#analysed_global_final").hide();
        } else {
            if(!this.finished) {
                //this.$("#analysed_global_progress").show();
            } else {
                //this.$("#analysed_global_progress").hide();
            }
            this.$("#analysed_global_final").show();
            this.$("#go_back").hide();
        }
        this.$("#current_cell").html(text);
    },

    select_mode: function() {
        this.analysed.hide();
    },

    set_ndfi: function(n) {
        this.$('#ndfi_change_value').html("ndfi change: " + n.toFixed(2));
    },

    report_changed: function() {
        var total = this.report.escape('total_cells');
        var current = this.report.escape('cells_finished');
        var percent = 100*Math.floor(current/total);
        var text = current + '/' + total + " (" + percent + "%)";
        this.$("#progress_number").html(text);
        this.$(".stats_progress").html(text);
        this.$("#progress").css({width: percent + "%"});
        if(percent == 100) {
            this.finished = true;
            //time to show generate button
            //this.$("#analysed_global_progress").hide();
            //this.$("#analysed_global_final").show();
        }
    },

    confirm_generation: function(e) {
        e.preventDefault();
        this.$("#confirmation_dialog").fadeIn();
    },

    cancel_report: function(e) {
        e.preventDefault();
        this.$("#confirmation_dialog").fadeOut(0.2);
    },

    change_user_cells: function(user, count) {
        this.$("#cells").html(count + " cells closed");
    },

    close_report: function(e) {
        this.trigger('close_report');
        e.preventDefault();
    },

    cancel_done: function(e) {
        this.$("#done_confirmation_dialog").fadeOut(0.2);
        e.preventDefault();
    },

    cell_done: function(e) {
        this.$("#done_confirmation_dialog").fadeOut(0.2);
        this.trigger('done');
        e.preventDefault();
    }



});

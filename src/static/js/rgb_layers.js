

var RGB_layers =  [
    {
        r: 1,
        g: 4,
        b: 1, /*3,*/
        sensor: 'modis',
        description: 'True color RGB141'
    },
    {
        r: 4, /*5,*/
        g: 2,
        b: 1,
        sensor: 'modis',
        description: 'False color RGB421'
    },
    {
        r: 1,
        g: 2,
        b: 1,
        sensor: 'modis',
        description: 'False color RGB121'
    },
    {
        r: 2,
        g: 1,
        b: 4,
        sensor: 'modis',
        description: 'F color infrared RGB214'
    },
    {
        r: 3,
        g: 2,
        b: 1,
        sensor: 'landsat',
        description: 'Landsat Stretch RGB321'
    },
    {
        r: 5,
        g: 4,
        b: 3,
        sensor: 'landsat',
        description: 'Landsat Stretch RGB543'
    },
    {
        r: 4,
        g: 3,
        b: 2,
        sensor: 'landsat',
        description: 'Landsat Stretch RGB432'
    },
    {
        r: 1,
        g: 2,
        b: 1,
        sensor: 'landsat',
        description: 'Landsat Stretch RGB121'
    }
];

/*
 ==========================================
 helper to add rgb layers to maps
 ==========================================
*/
function add_rgb_layers(layers, gridstack, report_id) {
    _(RGB_layers).each(function(layer) {
        var rgb = new RGBStrechLayer({
            r: layer.r,
            g: layer.g,
            b: layer.b,
            sensor: layer.sensor,
            report_id: report_id,
            description: layer.description
        });

        layers.add(rgb);
        gridstack.bind('work_mode', rgb.on_cell);
        var c = gridstack.current_cell;
        if(c) {
            rgb.on_cell(c.get('x'), c.get('y'), c.get('z'));
        }
    });
}


/*
 ==========================================
 unbind rgb layers for map
 ==========================================
*/
function unbind_rgb_layers(layers, gridstack) {
    _(RGB_layers).each(function(layer) {
        var lyr = layers.get_by_name(layer.description);
        if(lyr){
        	gridstack.unbind('work_mode', lyr.on_cell);
        }
    });
}

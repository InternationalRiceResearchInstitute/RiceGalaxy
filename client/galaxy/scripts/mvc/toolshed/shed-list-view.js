define(['mvc/toolshed/toolshed-model', 'mvc/toolshed/util'], function(toolshed_model, toolshed_util) {

    var View = Backbone.View.extend({

        defaults: {
            tool_sheds: [{"url": "https://toolshed.g2.bx.psu.edu/", "name": "Galaxy Main Tool Shed"}]
        },

        initialize: function(options) {
            var self = this;
            this.options = _.defaults(this.options || {}, this.defaults);
            this.model = new toolshed_model.ShedsCollection();
            this.listenTo(this.model, 'sync', this.render);
            this.model.fetch();
        },

        el: '#center',

        render: function(options) {
            this.options = _.defaults(this.options || {}, options, this.defaults);
            var toolshed_list_template = this.templateToolshedList;
            this.$el.html(toolshed_list_template({title: 'Configured Galaxy Tool Sheds', tool_sheds: this.model.models, queue: toolshed_util.queueLength()}));
        },

        reDraw: function(options){
            this.$el.empty();
            this.render(options);
        },

        templateToolshedList: _.template([
            '<div class="unified-panel-header" id="panel_header" unselectable="on">',
                '<div class="unified-panel-header-inner"><%= title %></div>',
                '<div class="unified-panel-header-inner" style="position: absolute; right: 5px; top: 0px;"><a href="#/queue">Repository Queue (<%= queue %>)</a></div>',
            '</div>',
            '<div class="unified-panel-body" id="list_toolsheds">',
                '<div class="form-row">',
                    '<table class="grid">',
                        '<% _.each(tool_sheds, function(shed) { %>',
                            '<tr class="libraryTitle">',
                                '<td>',
                                    '<div style="float: left; margin-left: 1px;" class="menubutton split">',
                                        '<a class="view-info shed-selector" href="#/categories/s/<%= shed.get("url") %>"><%= shed.get("name") %></a>',
                                    '</div>',
                                '</td>',
                            '</tr>',
                        '<% }); %>',
                    '</table>',
                '</div>',
                '<div style="clear: both"></div>',
            '</div>',
        ].join(''))

    });

    return {
        ShedListView: View,
    };

});